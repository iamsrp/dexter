"""
Simple IO-based output.
"""

from   dexter.core.log import LOG
from   dexter.output   import Output

import logging
import socket

# ------------------------------------------------------------------------------

class _FileOutput(Output):
    """
    An L{Output} which just writes to a file handle.
    """
    def __init__(self, state, handle):
        """
        :type  notifier: L{Notifier}
        :param notifier:
            The Notifier instance.
        :type  handle: file
        :param handle:
            The file handle to write to.
        """
        super().__init__(state)
        assert handle is None or (hasattr(handle, 'write') and
                                  hasattr(handle, 'flush') and
                                  hasattr(handle, 'closed')), (
            "Given handle was not file-like: %s" % type(handle)
        )
        self._handle = handle


    def write(self, text):
        """
        @see Output.write
        """
        if text         is not None and \
           self._handle is not None and \
           not self._handle.closed:
            self._handle.write(str(text))
            self._handle.flush()


class StdoutOutput(_FileOutput):
    """
    An output to C{stdout}.
    """
    def __init__(self, state):
        """
        @see Output.__init__()
        """
        super(StdoutOutput, self).__init__(state, sys.stdout)


class StderrOutput(_FileOutput):
    """
    An output to C{stderr}.
    """
    def __init__(self, state):
        """
        @see Output.__init__()
        """
        super(StderrOutput, self).__init__(state, sys.stderr)


class LogOutput(Output):
    """
    An output which logs as a particular level to the system's log.
    """
    def __init__(self, state, level=logging.INFO):
        """
        @see Output.__init__()
        :type  level: int or str
        :param level:
            The level to log at.
        """
        super(LogOutput, self).__init__(state)
        try:
            self._level = int(level)
        except:
            try:
                self._level = getattr(logging, level)
            except:
                raise ValueError("Bad log level: '%s'" % (level,))


    def write(self, text):
        """
        @see Output.write
        """
        if text:
            LOG.log(self._level, str(text))


class SocketOutput(Output):
    """
    An output which sends text to a simple remote socket.

    Each block of text will be sent and terminated by a ``NUL`` char.
    """
    def __init__(self, state, host=None, port=None):
        """
        @see Output.__init__()
        :type  host: ste
        :param host:
            The remote host to connect to.
        :type  port: int
        :param port:
            The port to connect to on the remote host.
        """
        super(SocketOutput, self).__init__(state)
        self._host   = str(host)
        self._port   = int(port)
        self._socket = None


    def write(self, text):
        """
        @see Output.write
        """
        if text:
            self._socket.send(str(text + '\0').encode())


    def _start(self):
        """
        @see Startable._start()
        """
        # Create the socket
        LOG.info("Opening socket to %s:%d" % (self._host, self._port))
        self._socket = socket.socket()
        self._socket.connect((self._host, self._port))


    def _stop(self):
       """
       @see Startable._stop()
       """
       try:
           self._socket.close()
       except:
           pass
