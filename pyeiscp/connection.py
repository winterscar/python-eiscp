"""Module containing the connection wrapper for the AVR interface."""
import asyncio
import logging
import socket
import netifaces
from pyeiscp.protocol import AVR, eISCPPacket

__all__ = "Connection"

try:
    ensure_future = asyncio.ensure_future
except:
    ensure_future = getattr(asyncio, "async")


class DiscoveryProtocol(asyncio.DatagramProtocol):

    def __init__(self,
        target,
        discovered_callback=None,
        loop=None,
    ):
        """Protocol handler that handles AVR discovery by broadcasting a discovery packet.

            :param target:
                the target (host, port) to broadcast the discovery packet over
            :param discovered_callback:
                called when a device has been discovered (optional)
            :param loop:
                asyncio event loop (optional)

            :type target:
                tuple
            :type: discovered_callback:
                coroutine
            :type loop:
                asyncio.loop
        """
        self.log = logging.getLogger(__name__)
        self._target = target
        self._discovered_callback = discovered_callback
        self._loop = loop

        self.discovered = []
        self.transport = None

    def connection_made(self, transport):
        """Discovery connection created, broadcast discovery packet."""
        self.transport = transport
        self.broadcast_discovery_packet()

    def datagram_received(self, data, addr):
        """Received response from device."""
        info = eISCPPacket.parse_info(data)
        if info and info['identifier'] not in self.discovered:
            self.log.info(f"{info['model_name']} discovered at {addr}")
            self.discovered.append(info['identifier'])
            if self._discovered_callback:
                ensure_future(self._discovered_callback(addr[0], int(info['iscp_port']), info['model_name'], info['identifier']))

    def broadcast_discovery_packet(self):
        """Broadcast discovery packets over the target."""
        self.log.debug(f"Broadcast discovery packet to {self._target}")
        self.transport.sendto(eISCPPacket('!xECNQSTN').get_raw(), self._target)
        self.transport.sendto(eISCPPacket('!pECNQSTN').get_raw(), self._target)

    def close(self):
        """Close the discovery connection."""
        self.log.debug("Closing broadcast discovery connection")
        if self.transport:
            self.transport.close()

    async def async_close_delayed(self, delay):
        """Close the discovery connection after a certain delay."""
        await asyncio.sleep(delay)
        self.close()


class Connection:
    """Connection handler to maintain network connection for AVR Protocol."""

    def __init__(self):
        """Instantiate the Connection object."""
        self.log = logging.getLogger(__name__)

    @classmethod
    async def create(
        cls,
        host="localhost",
        port=60128,
        auto_reconnect=True,
        max_retry_interval=300,
        loop=None,
        protocol_class=AVR,
        update_callback=None,
        connect_callback=None,
        disconnect_callback=None,
        auto_connect=True
    ):
        """Initiate a connection to a specific device.

        Here is where we supply the host and port and callback callables we
        expect for this AVR class object.

        :param host:
            Hostname or IP address of the device
        :param port:
            TCP port number of the device
        :param auto_reconnect:
            Should the Connection try to automatically reconnect if needed?
        :param max_retry_interval:
            Maximum time between reconnects when auto reconnect is enabled
        :param loop:
            asyncio.loop for async operation
        :param update_callback
            This function is called whenever AVR state data changes
        :param connect_callback
            This function is called when the connection with the AVR is established
        :param disconnect_callback
            This function is called when the connection with the AVR is lost
        :param auto_connect
            Should the Connection try to automatically connect?

        :type host:
            str
        :type port:
            int
        :type auto_reconnect:
            boolean
        :param max_retry_interval:
            int
        :type loop:
            asyncio.loop
        :type update_callback:
            callable
        :type connect_callback:
            callable
        :param disconnect_callback
            callable
        :type auto_connect:
            boolean
        """
        assert port >= 0, "Invalid port value: %r" % (port)
        conn = cls()

        conn.host = host
        conn.port = port
        conn._loop = loop or asyncio.get_event_loop()
        conn._retry_interval = 1
        conn._closed = False
        conn._closing = False
        conn._halted = False
        conn._auto_reconnect = auto_reconnect
        conn._max_retry_interval = max_retry_interval
        conn._disconnect_callback = disconnect_callback
        conn._unexpected_disconnect = False

        def _disconnected_callback():
            """Function callback for Protocol class when connection is lost."""
            if conn._auto_reconnect and not conn._closing:
                # Don't call the disconnect callback, but try to reconnect first.
                conn._unexpected_disconnect = True
                ensure_future(conn._reconnect(), loop=conn._loop)

            elif disconnect_callback:
                # No auto reconnect, so call the disconnect callback directly.
                conn._loop.call_soon(disconnect_callback, conn.host)

        def _update_callback(message):
            """Function callback for Protocol class when the AVR sends updates."""
            if update_callback:
                conn._loop.call_soon(update_callback, message, conn.host)

        def _connect_callback():
            """Function callback for Protocoal class when connection is established."""
            conn._unexpected_disconnect = False
            if connect_callback:
                conn._loop.call_soon(connect_callback, conn.host)

        conn.protocol = protocol_class(
            loop=conn._loop,
            update_callback=_update_callback,
            connect_callback=_connect_callback,
            connection_lost_callback=_disconnected_callback,
        )

        if auto_connect:
            await conn._reconnect()

        return conn

    @classmethod
    async def discover(
        cls,
        host=None,
        port=60128,
        auto_reconnect=True,
        max_retry_interval=300,
        loop=None,
        protocol_class=AVR,
        update_callback=None,
        connect_callback=None,
        discovery_callback=None,
        disconnect_callback=None,
        timeout = 5
    ):
        """Discover Onkyo or Pioneer Network Receivers on the network.

        Here we discover devices on the available networks and for every
        discovered device, a Connection object is returned through the
        discovery callback coroutine. The connection is not yet established,
        this should be done manually by calling connect on the Connection

        :param host:
            If specified, a direct connection is made to discover the AVR.
            Else, the available broadcast addresses are used to disvoer AVRs.
        :param port:
            TCP port number of the device
        :param auto_reconnect:
            Should the Connection try to automatically reconnect if needed?
        :param max_retry_interval:
            Maximum time between reconnects when auto reconnect is enabled
        :param loop:
            asyncio.loop for async operation
        :param update_callback
            This function is called whenever discovered devices state data change
        :param connect_callback
            This function is called when the connection with discovered devices is established
        :param discovery_callback
            This function is called when a device has been discovered on the network
        :param disconnect_callback
            This function is called when the connection with the AVR is lost
        :param timeout
            Number of seconds to detect devices

        :type host:
            str
        :type port:
            int
        :type auto_reconnect:
            boolean
        :type max_retry_interval:
            int
        :type loop:
            asyncio.loop
        :type update_callback:
            callable
        :type connect_callback:
            callable
        :type discovery_callback:
            coroutine
        :param disconnect_callback
            coroutine
        :type timeout
            int
        """
        assert port >= 0, "Invalid port value: %r" % (port)

        _loop = loop or asyncio.get_event_loop()

        async def discovered_callback(discovered_host, port, name, identifier):
            """Async function callback for Discovery Protocol when an AVR is discovered"""

            # Create a Connection, but do not auto connect
            conn = await cls.create(
                host=discovered_host,
                port=port,
                auto_reconnect=auto_reconnect,
                max_retry_interval=max_retry_interval,
                loop=_loop,
                protocol_class=protocol_class,
                update_callback=update_callback,
                connect_callback=connect_callback,
                disconnect_callback=disconnect_callback,
                auto_connect=False
            )

            # Pass the created Connection to the discovery callback
            conn.name = name
            conn.identifier = identifier
            if discovery_callback:
                ensure_future(discovery_callback(conn))

        # Iterate over all network interfaces to find broadcast addresses
        ifaddrs = [
            ifaddr
            for interface in netifaces.interfaces()
            for ifaddr in netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
        ]

        for ifaddr in ifaddrs:
            if "addr" in ifaddr:
                if host:
                    # Set target to specified host
                    target = (host, port)
                elif "broadcast" in ifaddr:
                    # Use the broadcast address to send the discovery packets
                    target = (ifaddr["broadcast"], port)
                else:
                    # No host provided and no broadcast address available, so skip
                    continue

                try:
                    protocol = DiscoveryProtocol(
                        target=target,
                        discovered_callback=discovered_callback,
                        loop=_loop,
                    )

                    await _loop.create_datagram_endpoint(
                        lambda: protocol,
                        local_addr=(ifaddr["addr"], 0),
                        allow_broadcast=True,
                    )
                    # Close the DiscoveryProtocol connections after timeout seconds
                    ensure_future(protocol.async_close_delayed(timeout))
                except PermissionError:
                    continue

    def update_property(self, zone, propname, value):
        """Format an update message and send to the receiver."""
        self.send(f"{zone}.{propname}={value}")

    def query_property(self, zone, propname):
        """Format a query message and send to the receiver."""
        self.send(f"{zone}.{propname}=query")

    def send(self, msg):
        """Fire and forget data to the reciever."""
        self.protocol.command(msg)

    def _get_retry_interval(self):
        return self._retry_interval

    def _reset_retry_interval(self):
        self._retry_interval = 1

    def _increase_retry_interval(self):
        self._retry_interval = min(self._max_retry_interval, 1.5 * self._retry_interval)

    async def _connect(self):
        self.log.debug(
            "Connecting to Network Receiver at %s:%d", self.host, self.port
        )
        await self._loop.create_connection(
            lambda: self.protocol, self.host, self.port
        )

    async def _reconnect(self):
        while True:
            try:
                if self._halted:
                    await asyncio.sleep(2)
                else:
                    await self._connect()
                    self._reset_retry_interval()
                    return

            except OSError:
                if self._unexpected_disconnect:
                    # Reconnect started by a disconnect and connecting failed again,
                    # so call the disconnect callback if there is one.
                    # Also clear the unexpected disconnect flag to make sure we only
                    # call the disconnect callback once for this disconnect.
                    self._unexpected_disconnect = False
                    if self._disconnect_callback:
                        self._loop.call_soon(self._disconnect_callback, self.host)

                self._increase_retry_interval()
                interval = self._get_retry_interval()
                self.log.debug("Connecting failed, retrying in %i seconds", interval)
                await asyncio.sleep(interval)

    async def connect(self, retry=True):
        """Establish the AVR device connection"""
        if not self.protocol.transport:
            if retry:
                await self._reconnect()
            else:
                await self._connect()

    def close(self):
        """Close the AVR device connection and don't try to reconnect."""
        self.log.info("Closing connection to Network Receiver")
        self._closing = True
        if self.protocol.transport:
            self.protocol.transport.close()

    def halt(self):
        """Close the AVR device connection and wait for a resume() request."""
        self.log.info("Halting connection to Network Receiver")
        self._halted = True
        if self.protocol.transport:
            self.protocol.transport.close()

    def resume(self):
        """Resume the AVR device connection if we have been halted."""
        self.log.info("Resuming connection to Network Receiver")
        self._halted = False

    @property
    def dump_conndata(self):
        """Developer tool for debugging forensics."""
        attrs = vars(self)
        return ", ".join("%s: %s" % item for item in attrs.items())
