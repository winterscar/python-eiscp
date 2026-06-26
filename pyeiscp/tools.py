"""Provides a raw console to test module and demonstrate usage."""
import argparse
import asyncio
import logging
import time

import pyeiscp

__all__ = ("console", "monitor")


async def console(loop, log, timeout=False):
    """Connect to receiver and show events as they occur.

    Pulls the following arguments from the command line (not method arguments):

    :param host:
        Hostname or IP Address of the device.
    :param port:
        TCP port number of the device.
    :param verbose:
        Show debug logging.
    :param messages:
        A sequence of one or more messages to send to the device.
    """
    parser = argparse.ArgumentParser(description=console.__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="IP of AVR")
    parser.add_argument("--port", default="60128", help="Port of AVR")
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("messages", nargs="*")

    args = parser.parse_args()

    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(level=level)

    def log_callback(message, host):
        """Receives event callback from eISCP Protocol class."""
        zone, command, value = message
        log.info("Zone: %s | %s: %s" % (zone, command, value))

    def connect_callback(host):
        log.info("Successfully (re)connected to AVR")

    host = args.host
    port = int(args.port)

    conn = await pyeiscp.Connection.create(
        host=host, port=port, loop=loop, update_callback=log_callback, connect_callback=connect_callback
    )

    for message in args.messages:
        conn.send(message)
    if timeout:
        await asyncio.sleep(timeout)
        loop.stop()

def monitor():
    """Wrapper to call console with a loop."""
    log = logging.getLogger(__name__)
    async def main():
        loop = asyncio.get_running_loop()
        await console(loop, log)
    asyncio.run(main())

def sender():
    """Wrapper to call console with a loop that stops after 2 seconds"""
    log = logging.getLogger(__name__)
    async def main():
        loop = asyncio.get_running_loop()
        await console(loop, log, timeout=1)
    asyncio.run(main())
