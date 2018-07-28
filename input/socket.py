'''
An input which listens from a socket.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import socket
import time

from dexter.input import Input, Token
from dexter.core  import LOG
from threading    import Thread

# ------------------------------------------------------------------------------

class SocketInput(Input):
    '''
    A way to get text from the outside world. 

    This creates an unsecured socket which anyone can connect to. Useful for
    testing but probably not advised for the real world.
    '''
    def __init__(self, port=8008):
        '''
        @type  port: int
        @param port:
            The port to listen on.
        '''
        super(Input, self).__init__()
        self._port    = int(port)
        self._socket  = None
        self._running = None
        self._output  = []


    def start(self):
        '''
        @see Input.start
        '''
        if self._running:
            return

        # Create the socket 
        LOG.info("Opening socket on port %d" % (self._port,))
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', self._port))
        self._socket.listen(5)

        # Start the acceptor thread
        def acceptor():
            while True:
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
       self._running = False


    def read(self):
        '''
        @see Input.read
        '''
        while True:
            if len(self._output) > 0:
                try:
                    return self._output.pop()
                except:
                    pass
            time.sleep(0.1)


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
                    tokens.append(Token(cur, 1.0, True))
                    cur = ''
                if c == '\n':
                    self._output.append(tokens)
                    tokens = []

            else:
                cur += c
