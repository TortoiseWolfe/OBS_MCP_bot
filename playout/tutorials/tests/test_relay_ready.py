"""relay_ready.py: an open port is not a ready relay; only a real RTMP handshake answer is."""
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from playout.tutorials import relay_ready  # noqa: E402


def serve(resets, port_holder, ready):
    """A stand-in for Docker's port proxy: resets the first `resets` connections, then answers the handshake."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port_holder.append(srv.getsockname()[1])
    ready.set()
    n = 0
    while n < resets + 1:
        c, _ = srv.accept()
        n += 1
        if n <= resets:
            c.close()                                      # accepted, then closed: "Cannot read RTMP handshake response"
        else:
            c.recv(1537)
            c.sendall(b"\x03" + b"\0" * 3072)
            c.close()
    srv.close()


def test_waits_through_resets_and_then_succeeds():
    port, ready = [], threading.Event()
    threading.Thread(target=serve, args=(2, port, ready), daemon=True).start()
    ready.wait(5)
    assert relay_ready.handshake_ok("127.0.0.1", port[0]) is False        # first connection is reset
    assert relay_ready.wait_ready("127.0.0.1", port[0], seconds=10, pause=0.05) is True


def test_gives_up_when_nothing_listens():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert relay_ready.wait_ready("127.0.0.1", port, seconds=0.5, pause=0.1) is False
