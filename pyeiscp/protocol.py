"""Module to maintain AVR state information and network interface."""
import asyncio
import logging
import time
import struct
import re
from pyeiscp import commands
from pyeiscp.utils import ValueRange
from collections import namedtuple

__all__ = "AVR"

# In Python 3.4.4, `async` was renamed to `ensure_future`.
try:
    ensure_future = asyncio.ensure_future
except AttributeError:
    ensure_future = getattr(asyncio, "async")


class ISCPMessage(object):
    """Deals with formatting and parsing data wrapped in an ISCP
    containers. The docs say:
        ISCP (Integra Serial Control Protocol) consists of three
        command characters and parameter character(s) of variable
        length.
    It seems this was the original protocol used for communicating
    via a serial cable.
    """

    def __init__(self, data):
        self.data = data

    def __str__(self):
        # ! = start character
        # 1 = destination unit type, 1 means receiver
        # End character may be CR, LF or CR+LF, according to doc
        return "!1{}\r".format(self.data)

    @classmethod
    def parse(cls, data):
        EOF = "\x1a"
        TERMINATORS = ["\n", "\r"]
        assert data[:2] == "!1"
        eof_offset = -1
        # EOF can be followed by CR/LF/CR+LF
        if data[eof_offset] in TERMINATORS:
            eof_offset -= 1
            if data[eof_offset] in TERMINATORS:
                eof_offset -= 1
        assert data[eof_offset] == EOF
        return data[2:eof_offset]


class eISCPPacket(object):
    """For communicating over Ethernet, traditional ISCP messages are
    wrapped inside an eISCP package.
    """

    header = namedtuple("header", ("magic, header_size, data_size, version, reserved"))

    def __init__(self, iscp_message):
        iscp_message = str(iscp_message)
        # We attach data separately, because Python's struct module does
        # not support variable length strings,
        header = struct.pack(
            "! 4s I I b 3s",
            b"ISCP",  # magic
            16,  # header size (16 bytes)
            len(iscp_message),  # data size
            0x01,  # version
            b"\x00\x00\x00",  # reserved
        )

        self._bytes = header + iscp_message.encode("utf-8")
        # __new__, string subclass?

    def __str__(self):
        return self._bytes.decode("utf-8")

    def get_raw(self):
        return self._bytes

    @classmethod
    def parse(cls, bytes):
        """Parse the eISCP package given by ``bytes``.
        """
        h = cls.parse_header(bytes[:16])
        data = bytes[h.header_size : h.header_size + h.data_size].decode(errors='replace')
        assert len(data) == h.data_size
        return data

    @classmethod
    def parse_header(cls, bytes):
        """Parse the header of an eISCP package.
        This is useful when reading data in a streaming fashion,
        because you can subsequently know the number of bytes to
        expect in the packet.
        """
        # A header is always 16 bytes in length
        assert len(bytes) == 16

        # Parse the header
        magic, header_size, data_size, version, reserved = struct.unpack(
            "! 4s I I b 3s", bytes
        )

        magic = magic.decode()
        reserved = reserved.decode()

        # Strangly, the header contains a header_size field.
        assert magic == "ISCP"
        assert header_size == 16

        return eISCPPacket.header(magic, header_size, data_size, version, reserved)

    @classmethod
    def parse_info(cls, bytes):
        response = cls.parse(bytes)
        # Return string looks something like this:
        # !1ECNTX-NR609/60128/DX
        info = re.match(r'''
            !
            (?P<device_category>\d)
            ECN
            (?P<model_name>[^/]*)/
            (?P<iscp_port>\d{5})/
            (?P<area_code>\w{2})/
            (?P<identifier>.{0,12})
        ''', response.strip(), re.VERBOSE)

        if info:
            return info.groupdict()


def command_to_packet(command):
    """Convert an ascii command like (PVR00) to the binary data we
    need to send to the receiver.
    """
    return eISCPPacket(ISCPMessage(command)).get_raw()


def normalize_command(command):
    """Ensures that various ways to refer to a command can be used."""
    command = command.lower()
    command = command.replace("_", " ")
    command = command.replace("-", " ")
    return command


def command_to_iscp(command, arguments=None, zone=None):
    """Transform the given given high-level command to a
    low-level ISCP message.
    Raises :class:`ValueError` if `command` is not valid.
    This exposes a system of human-readable, "pretty"
    commands, which is organized into three parts: the zone, the
    command, and arguments. For example::
        command('power', 'on')
        command('power', 'on', zone='main')
        command('volume', 66, zone='zone2')
    As you can see, if no zone is given, the main zone is assumed.
    Instead of passing three different parameters, you may put the
    whole thing in a single string, which is helpful when taking
    input from users::
        command('power on')
        command('zone2 volume 66')
    To further simplify things, for example when taking user input
    from a command line, where whitespace needs escaping, the
    following is also supported:
        command('power=on')
        command('zone2.volume=66')
    """
    default_zone = "main"
    command_sep = r"[. ]"
    norm = lambda s: s.strip().lower()

    # If parts are not explicitly given, parse the command
    if arguments is None and zone is None:
        # Separating command and args with colon allows multiple args
        if ":" in command or "=" in command:
            base, arguments = re.split(r"[:=]", command, 1)
            parts = [norm(c) for c in re.split(command_sep, base)]
            if len(parts) == 2:
                zone, command = parts
            else:
                zone = default_zone
                command = parts[0]
            # Split arguments by comma or space
            arguments = [norm(a) for a in re.split(r"[ ,]", arguments)]
        else:
            # Split command part by space or dot
            parts = [norm(c) for c in re.split(command_sep, command)]
            if len(parts) >= 3:
                zone, command = parts[:2]
                arguments = parts[3:]
            elif len(parts) == 2:
                zone = default_zone
                command = parts[0]
                arguments = parts[1:]
            else:
                raise ValueError("Need at least command and argument")

    # Find the command in our database, resolve to internal eISCP command
    group = commands.ZONE_MAPPINGS.get(zone, zone)
    if not zone in commands.COMMANDS:
        raise ValueError('"{}" is not a valid zone'.format(zone))

    prefix = commands.COMMAND_MAPPINGS[group].get(command, command)
    if not prefix in commands.COMMANDS[group]:
        raise ValueError(
            '"{}" is not a valid command in zone "{}"'.format(command, zone)
        )

    # Resolve the argument to the command. This is a bit more involved,
    # because some commands support ranges (volume) or patterns
    # (setting tuning frequency). In some cases, we might imagine
    # providing the user an API with multiple arguments (TODO: not
    # currently supported).
    argument = arguments[0]

    # 1. Consider if there is a alias, e.g. level-up for UP.
    try:
        value = commands.VALUE_MAPPINGS[group][prefix][argument]
    except KeyError:
        # 2. See if we can match a range or pattern
        for possible_arg in commands.VALUE_MAPPINGS[group][prefix]:
            if argument.isdigit():
                if isinstance(possible_arg, ValueRange):
                    if int(argument) in possible_arg:
                        # We need to send the format "FF", hex() gives us 0xff
                        value = hex(int(argument))[2:].zfill(2).upper()
                        break

            # TODO: patterns not yet supported
        else:
            raise ValueError(
                '"{}" is not a valid argument for command '
                '"{}" in zone "{}"'.format(argument, command, zone)
            )

    return "{}{}".format(prefix, value)


def iscp_to_command(iscp_message):
    for zone, zone_cmds in commands.COMMANDS.items():
        # For now, ISCP commands are always three characters, which
        # makes this easy.
        command, args = iscp_message[:3], iscp_message[3:]
        if command in zone_cmds:
            if args in zone_cmds[command]["values"]:
                if "," in zone_cmds[command]["values"][args]["name"]:
                    value = tuple(zone_cmds[command]["values"][args]["name"].split(","))
                else:
                    value = zone_cmds[command]["values"][args]["name"]

                return (
                    zone,
                    zone_cmds[command]["name"],
                    value
                )
            else:
                match = re.match("[+-]?[0-9a-f]+$", args, re.IGNORECASE)
                if match:
                    return zone, zone_cmds[command]["name"], int(args, 16)
                else:
                    if "," in args:
                        value = tuple(args.split(","))
                    else:
                        value = args

                    return zone, zone_cmds[command]["name"], value

    else:
        raise ValueError(
            "Cannot convert ISCP message to command: {}".format(iscp_message)
        )


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class AVR(asyncio.Protocol):
    """The Anthem AVR IP control protocol handler."""

    def __init__(self,
        update_callback=None,
        connect_callback=None,
        loop=None,
        connection_lost_callback=None,
    ):
        """Protocol handler that handles all status and changes on AVR.

        This class is expected to be wrapped inside a Connection class object
        which will maintain the socket and handle auto-reconnects.

            :param update_callback:
                called if any state information changes in device (optional)
            :param connection_lost_callback:
                called when connection is lost to device (optional)
            :param loop:
                asyncio event loop (optional)

            :type update_callback:
                callable
            :type: connection_lost_callback:
                callable
            :type loop:
                asyncio.loop
        """
        self._loop = loop
        self.log = logging.getLogger(__name__)
        self._connection_lost_callback = connection_lost_callback
        self._update_callback = update_callback
        self._connect_callback = connect_callback
        self.buffer = b""
        self._input_names = {}
        self._input_numbers = {}
        self.transport = None

    def command(self, command, arguments=None, zone=None):
        """Issue a formatted command to the device.

        This function sends a message to the device without waiting for a response.

            :param command: Any command as documented in the readme
            :param arguments: The value to send with the command
            :param zone: One of dock, main, zone1, zone2, zone3, zone4
            :type command: str
            :type arguments: str
            :type zone: str

        :Example:

        >>> command(volume, 55, main)
        or
        >>> command(main.volume=55)
        """
        try:
            iscp_message = command_to_iscp(command, arguments, zone)
        except ValueError as error:
            self.log.error(f"Invalid message. {error}")
            return

        self.log.debug("> %s", command)
        try:
            self.transport.write(command_to_packet(iscp_message))
        except:
            self.log.warning("No transport found, unable to send command")

    #
    # asyncio network functions
    #

    def connection_made(self, transport):
        """Called when asyncio.Protocol establishes the network connection."""
        self.transport = transport

        if self._connect_callback:
            self._loop.call_soon(self._connect_callback)

        # self.transport.set_write_buffer_limits(0)
        limit_low, limit_high = self.transport.get_write_buffer_limits()
        self.log.debug("Write buffer limits %d to %d", limit_low, limit_high)

    def data_received(self, data):
        """Called when asyncio.Protocol detects received data from network."""
        self.buffer += data
        self.log.debug("Received %d bytes from AVR: %s", len(self.buffer), self.buffer)
        self._assemble_buffer()

    def connection_lost(self, exc):
        """Called when asyncio.Protocol loses the network connection."""
        if exc is not None:
            self.log.warning("Lost connection to receiver: %s", exc)

        self.transport = None

        if self._connection_lost_callback:
            self._loop.call_soon(self._connection_lost_callback)

    def _assemble_buffer(self):
        """Data for a command may not arrive all in one go.
        First read the header to determin the total command size, then wait
        until we have that much data before decoding it.
        """
        self.transport.pause_reading()

        if len(self.buffer) >= 16:
            size = eISCPPacket.parse_header(self.buffer[:16]).data_size
            if len(self.buffer) - 16 >= size:
                data = self.buffer[16 : 16 + size]
                try:
                    message = iscp_to_command(ISCPMessage.parse(data.decode()))
                    if self._update_callback:
                        self._loop.call_soon(self._update_callback, message)
                except:
                    self.log.debug("Unable to parse recieved message: %s", data.decode('utf-8', 'backslashreplace').rstrip())

                self.buffer = self.buffer[16 + size :]  # shift data to start
                # If there is still data in the buffer,
                # don't wait for more, process it now!
                if len(self.buffer):
                    self._assemble_buffer()

        self.transport.resume_reading()
        return
