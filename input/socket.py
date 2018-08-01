'''
An input which listens from a socket.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import socket
import time

from   dexter.input    import Input, Token
from   dexter.core.log import LOG
from   threading       import Thread

# ------------------------------------------------------------------------------

class SocketInput(Input):
    '''
    A way to get text from the outside world. 

    This creates an unsecured socket which anyone can connect to. Useful for
    testing but probably not advised for the real world.
    '''
    def __init__(self, notifier, port=8008):
        '''
        @type  notifier: L{Notifier}
        @param notifier:
            The Notifier instance.
        @type  port: int
        @param port:
            The port to listen on.
        '''
        super(SocketInput, self).__init__(notifier)
        self._port    = int(port)
        self._socket  = None
        self._running = False
        self._output  = []


    def start(self):
        '''
        @see Input.start
        '''
        if self._running:
            return

        # We're now running
        self._running = True

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


    def stop(self):
       '''
       @see Input.stop
       '''
       try:
           self._socket.close()
       except:
           pass
       self._running = False


    def read(self):
        '''
        @see Input.read
        '''
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass


    def _handle(self, sckt):
        '''
        Handle reading from a socket
        '''
        LOG.info("Started new socket handler")

        # We'll build these up
        tokens = []
        cur = ''

        # Loop until they go away
        while True:
            c = sckt.recv(1)
            if c is None or c == '':
                LOG.info("Peer closed connection")
                return

            if cur == '' and ord(c) == 4:
                LOG.info("Got EOT")
                try:
                    sckt.close()
                except:
                    pass
                return

            if c in ' \t\n':
                if len(cur) > 0:
                    tokens.append(Token(cur.strip(), 1.0, True))
                    cur = ''
                if c == '\n':
                    self._output.append(tokens)
                    tokens = []

            else:
                cur += c


    def __str__(self):
        return "%s[Listening on *:%d]" % (
            super(SocketInput, self).__str__(),
            self._port
        )
