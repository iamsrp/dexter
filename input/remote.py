"""
Input using a remote server to to the decoding.

This can be used in conjunction with something like the C{deepspeech_server.py}
script in order to have a fast machine do the actual speech-to-text decoding.
"""

import numpy
import os
import pyaudio
import socket
import struct

from dexter.input       import Token
from dexter.input.audio import AudioInput
from dexter.core.log    import LOG

# ------------------------------------------------------------------------------

class RemoteInput(AudioInput):
    """
    Use a remote server to do the audio decoding for us.
    """
    def __init__(self,
                 state,
                 host='localhost',
                 port=8008,
                 wav_dir=None):
        """
        @see AudioInput.__init__()

        @type  host: str
        @param host:
            The host to connect to.
        @type  port: int
        @param port:
            The port to connect to.
        """
        super(RemoteInput, self).__init__(state,
                                          wav_dir=wav_dir)
        self._host   = host
        self._port   = int(port)
        self._sckt   = None
        self._header = struct.pack('!qqq',
                                    self._channels, self._width, self._rate)


    def _feed_raw(self, data):
        """
        @see AudioInput._feed_raw()
        """
        # Handle funy inputs
        if data is None or len(data) == 0:
            return

        # Don't let exceptions kill the thread
        try:
            # Connect?
            if self._sckt is None:
                # Connect and send the header information
                LOG.info("Opening connection to %s:%d" %
                         (self._host, self._port,))
                self._sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sckt.connect((self._host, self._port))
                self._sckt.sendall(self._header)

            # Send off the chunk
            LOG.debug("Sending %d bytes of data to %s" %
                      (len(data), self._host))
            self._sckt.sendall(struct.pack('!q', len(data)))
            self._sckt.sendall(data)

        except Exception as e:
            # Don't kill the thread by throwing an exception, just grumble
            LOG.info("Failed to send to remote side: %s" % e)
            try:
                self._sckt.shutdown(socket.SHUT_RDWR)
                self._sckt.close()
            except:
                pass
            finally:
                self._sckt = None
            return


    def _decode(self):
        """
        @see AudioInput._decode()
        """
        if self._sckt is None:
            # No context means no tokens
            LOG.warning("Had no stream context to close")
            return []

        try:
            # Send the EOD token
            self._sckt.sendall(struct.pack('!q', -1))

            # Get back the result:
            #   8 bytes for the length
            #   data...
            LOG.info("Waiting for result...")
            length = b''
            while len(length) < 8:
                got = self._sckt.recv(8 - len(length))
                if len(got) == 0:
                    raise IOError("EOF in recv()")
                length += got
            (count,) = struct.unpack("!q", length)

            # Read in the string
            LOG.info("Reading %d chars" % (count,))
            result = b''
            while len(result) < count:
                got = self._sckt.recv(count - len(result))
                if len(got) == 0:
                    raise IOError("EOF in recv()")
                result += got
            result = result.decode()
            LOG.info("Result is: '%s'" % (result,))

            # Convert to tokens
            tokens = [Token(word.strip(), 1.0, True)
                      for word in result.split(' ')
                      if word.strip() != '']
            return tokens

        except Exception as e:
            # Again, just grumble on exceptions
            LOG.info("Failed to do remote processing: %s" % e)
            return []

        finally:
            # Close it out, best effort
            try:
                LOG.info("Closing connection")
                self._sckt.shutdown(socket.SHUT_RDWR)
                self._sckt.close()
            except:
                pass
            finally:
                self._sckt = None
