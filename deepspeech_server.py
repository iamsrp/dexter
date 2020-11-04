#!/usr/bin/env python3
"""
Listen for incoming data and give back parsed results.

This can be run a machine with a decent amount of oomph and the L{RemoteService}
can talk to it instead of doing the speech-to-text locally. Thias is handy for
when your client machine is just a Raspberry Pi.

And, if other Home Hub providers can ship audio off from their Home Hub to the
cloud to process, then it seems only fair that we can do something like that
too.
"""

from   deepspeech import Model
from   threading  import Thread

import argparse
import logging
import numpy
import os
import socket
import struct
import time

# ------------------------------------------------------------------------------

def handle(conn):
    """
    Create a new thread for the given connection and start it.
    """
    thread = Thread(target=lambda: run(conn))
    thread.daemon = True
    thread.start()


def run(conn):
    """
    Handle a new connection, in its own thread.
    """
    try:
        # Read in the header data
        logging.info("Reading header")
        header = b''
        while len(header) < (3 * 8):
            got = conn.recv((3 * 8) - len(header))
            if len(got) == 0:
                time.sleep(0.001)
                continue
            header += got

        # Unpack to variables
        (channels, width, rate) = struct.unpack('!qqq', header)
        logging.info("%d channel(s), %d byte(s) wide, %dHz" %
                     (channels, width, rate))

        if model.sampleRate() != rate:
            raise ValueError("Given sample rate, %d, differs from desired rate, %d" %
                             (rate, model.sampleRate()))
        if width not in (1, 2, 4, 8):
            raise ValueError("Unhandled width: %d" % width)

        # Decode as we go
        context = model.createStream()

        # Keep pulling in the data until we get an empty chunk
        total_size = 0
        while True:
            # How big is this incoming chunk?
            length_bytes = b''
            while len(length_bytes) < (8):
                got = conn.recv(8 - len(length_bytes))
                if len(got) == 0:
                    time.sleep(0.001)
                    continue
                length_bytes += got
            (length,) = struct.unpack('!q', length_bytes)

            # End marker?
            if length < 0:
                break

            # Pull in the chunk
            logging.debug("Reading %d bytes of data" % (length,))
            data = b''
            while len(data) < length:
                got = conn.recv(length - len(data))
                if len(got) == 0:
                    time.sleep(0.001)
                    continue
                data += got

            # Feed it in
            if   width == 1: audio = numpy.frombuffer(data, numpy.int8)
            elif width == 2: audio = numpy.frombuffer(data, numpy.int16)
            elif width == 4: audio = numpy.frombuffer(data, numpy.int32)
            elif width == 8: audio = numpy.frombuffer(data, numpy.int64)
            context.feedAudioContent(audio)
            total_size += len(data)

        # Finally, decode it
        logging.info("Decoding %0.2f seconds of audio",
                     total_size / rate / width / channels)
        words = context.finishStream()
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


# ------------------------------------------------------------------------------


# Set up the logger
logging.basicConfig(
    format='[%(asctime)s %(threadName)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
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
        handle(conn)

    except Exception as e:
        # Tell the user at least
        logging.error("Error handling incoming connection: %s" % e)
