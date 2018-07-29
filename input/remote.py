'''
Input using a remote server to to the decoding.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import numpy
import os
import pyaudio
import socket
import struct

from dexter.input              import Token
from dexter.input.audio        import AudioInput
from dexter.core               import LOG

# ------------------------------------------------------------------------------

class RemoteInput(AudioInput):
    '''
    Input from a remote server which will do the decoding for us.
    '''
    def __init__(self,
                 host='localhost',
                 port=8008,
                 pre_silence_limit=2.0,
                 mid_silence_limit=1.0,
                 prev_audio=1.5):
        super(RemoteInput, self).__init__(
            pre_silence_limit=pre_silence_limit,
            mid_silence_limit=mid_silence_limit,
            prev_audio=prev_audio
        )

        self._host = host
        self._port = int(port)
        

    def _decode_raw(self, data):
        '''
        @see L{AudioInput._decode_raw()}
        '''
        # Handle funy inputs
        if data is None or len(data) == 0:
            return []

        # Info in the header
        header = struct.pack('!qqqq',
                             self._channels, self._width, self._rate,
                             len(data))
        
        # Connect
        LOG.info("Opening connection to %s:%d" % (self._host, self._port,))
        try:
            # Connect
            sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sckt.connect((self._host, self._port))

            # Send off our query
            LOG.info("Sending %d bytes of data to %s" % (len(data), self._host))
            sckt.sendall(header)
            sckt.sendall(data)

            # Get back the result:
            #   8 bytes for the length
            #   data...
            LOG.info("Waiting for result...")
            length = ''
            while len(length) < 8:
                length += sckt.recv(8 - len(length))
            (count,) = struct.unpack("!q", length)

            # Read in the string
            LOG.info("Reading %d chars" % (count,))
            result = ''
            while len(result) < count:
                result += sckt.recv(count - len(result))
            LOG.info("Result is: %s" % (result,))

        except Exception as e:
            # Don't kill the thread by throwing an exception, just grumble
            LOG.info("Failed to do remote processing: %s" % e)
            return []

        finally:
            # Close it out, best effort
            try:
                LOG.info("Closing connection")
                sckt.shutdown(socket.SHUT_RDWR)
                sckt.close()
            except:
                pass
            
        # Convert to tokens
        tokens = [Token(word, 1.0, True)
                  for word in result.split(' ')]        
        return tokens
