#!/usr/bin/env python3
'''
Listen for incoming data and give back parsed results.

This can be run a machine with a decent amount of oomph and the L{RemoteService}
can talk to it instead of doing the speech-to-text locally. Thias is handy for
when your client machine is just a Raspberry Pi.

And, if other Home Hub providers can ship audio off from their Home Hub to the
cloud to process, then it seems only fair that we can do something like that
too.
'''

import argparse
import logging
import numpy
import os
import socket
import struct

from deepspeech import Model

# ------------------------------------------------------------------------------

# Set up the logger
logging.basicConfig(
    format='[%(asctime)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
    level=logging.INFO
)

# Parse the command line args
parser = argparse.ArgumentParser(description='Running DeepSpeech inference.')
parser.add_argument('--model', required=True,
                    help='Path to the .pbmm file')
parser.add_argument('--scorer', required=False,
                    help='Path to the .scorer file')
parser.add_argument('--beam_width', type=int, default=500,
                    help='Beam width for the CTC decoder')
parser.add_argument('--port', type=int, default=8008,
                    help='The port number to listen on')
args = parser.parse_args()

# Load in the model
logging.info("Loading model from %s" % args.model)
model = Model(args.model)

# Configure it
model.setBeamWidth(args.beam_width)
if args.scorer:
    logging.info("Loading scorer from %s" % (args.scorer,))
    model.enableExternalScorer(args.scorer)
 
# Set up the server socket
logging.info("Opening socket on port %d" % (args.port,))
sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sckt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sckt.bind(('0.0.0.0', args.port))
sckt.listen(5)

# Do this forever
while True:
    try:
        # Get a connection
        logging.info("Waiting for a connection")
        (conn, addr) = sckt.accept()
        logging.info("Got connection from %s" % (addr,))

        # Read in the header data
        logging.info("Reading header")
        header = b''
        while len(header) < (4 * 8):
            got = conn.recv((4 * 8) - len(header))
            if len(got) == 0:
                raise IOError("EOF in recv()")
            header += got

        # Unpack to variables
        (channels, width, rate, length) = struct.unpack('!qqqq', header)
        logging.info("%d channel(s), %d byte(s) wide, %dHz, %d bytes length" %
                     (channels, width, rate, length))

        if model.sampleRate() != rate:
            raise ValueError("Given sample rate, %d, differs from desired rate, %d" %
                             (rate, model.sampleRate()))

        # Pull in the data
        logging.info("Reading %d bytes of data" % (length,))
        data = b''
        while len(data) < length:            
            got = conn.recv(length - len(data))
            if len(got) == 0:
                raise IOError("EOF in recv()")
            data += got

        # Actually decode it
        logging.info("Decoding")
        audio = numpy.frombuffer(data, numpy.int16)
        words = model.stt(audio)
        logging.info("Got: '%s'" % (words,))

        # Send back the length (as a long) and the string
        words = words.encode()
        conn.sendall(struct.pack('!q', len(words)))
        conn.sendall(words)

    except Exception as e:
        # Tell the user at least
        logging.error("Error handling incoming data: %s" % e)

    finally:
        # We're done with this connection now, close in a best-effort fashion
        try:
            logging.info("Closing connection")
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        except:
            pass

        
