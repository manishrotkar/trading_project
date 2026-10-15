"""Offline guard for the test suite.

Importing this module and calling :func:`block_network` patches the
``socket`` layer so ANY attempt to open a connection (including a live
Fyers API request, or any other host) raises immediately instead of
succeeding.  The unit tests must never require network access, and this
makes violations fail loudly rather than silently depending on the
internet.

It is applied by scripts/run_checks.py before test discovery, and can be
used by any standalone runner:

    from tests._offline import block_network
    block_network()
"""

import socket
import urllib.request


class NetworkBlocked(AssertionError):
    """Raised when code under test attempts a network connection."""


def _deny(*args, **kwargs):
    raise NetworkBlocked(
        "network access attempted during tests -- tests must NOT require "
        "a live Fyers API request (or any other live request)")


def block_network():
    """Block every outbound connection and urllib shortcut in this process."""
    socket.socket.connect = _deny
    socket.socket.connect_ex = _deny
    socket.create_connection = _deny
    # urlopen would reach connect() anyway, but block it too so the error
    # message points at the guard rather than a raw socket traceback.
    urllib.request.urlopen = _deny
