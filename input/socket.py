"""
An input which listens from a socket.
"""

import socket
import time

from   dexter.input    import Input, Token
from   dexter.core.log import LOG
from   threading       import Thread

# ------------------------------------------------------------------------------

class SocketInput(Input):
    """
    A way to get text from the outside world.

    This creates an unsecured socket which anyone can connect to. Useful for
    testing but probably not advised for the real world.
    """
    def __init__(self, state, port=8008, prefix=None):
        """
        @see Input.__init__()
        @type  port: int
        @param port:
            The port to listen on.
        @type  prefix: str
        @param prefix:
            What to prefix to the beginning of any input.
        """
        super(SocketInput, self).__init__(state)

        self._port = int(port)
        if prefix and str(prefix).strip():
            self._prefix = [Token(word.strip(), 1.0, True)
                            for word in str(prefix).strip().split()
                            if word]
        else:
            self._prefix = None

        self._socket = None
        self._output = []


    def read(self):
        """
        @see Input.read
        """
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass


    def _start(self):
        """
        @see Component.start()
        """
        # Create the socket
        LOG.info("Opening socket on port %d" % (self._port,))
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', self._port))
        self._socket.listen(5)

        # Start the acceptor thread
        def acceptor():
            while self._running:
                (sckt, addr) = self._socket.accept()
                LOG.info("Got connection from %s" % (addr,))
                thread = Thread(target=lambda: self._handle(sckt))
                thread.daemon = True
                thread.start()
        thread = Thread(target=acceptor)
        thread.daemon = True
        thread.start()


    def _stop(self):
       """
       @see Input.stop
       """
       try:
           self._socket.close()
       except:
           pass


    def _handle(self, sckt):
        """
        Handle reading from a socket
        """
        LOG.info("Started new socket handler")

        # We'll build these up
        tokens = []
        cur = b''

        # Loop until they go away
        while True:
            c = sckt.recv(1)
            if c is None or len(c) == 0:
                LOG.info("Peer closed connection")
                return

            if len(cur) == 0 and ord(c) == 4:
                LOG.info("Got EOT")
                try:
                    sckt.close()
                except:
                    pass
                return

            if c in b' \t\n':
                if len(cur.strip()) > 0:
                    tokens.append(Token(cur.strip().decode(), 1.0, True))
                    cur = b''

                if c == b'\n':
                    if len(tokens) > 0:
                        if self._prefix:
                            tokens = self._prefix + tokens
                        self._output.append(tokens)
                        tokens = []

            else:
                cur += c


    def __str__(self):
        return "%s[Listening on *:%d]" % (
            super(SocketInput, self).__str__(),
            self._port
        )
