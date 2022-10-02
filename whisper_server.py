#!/usr/bin/env python3
"""
Listen for incoming data and give back parsed results.

This can be run a machine with a decent amount of oomph and the L{RemoteService}
can talk to it instead of doing the speech-to-text locally. This is handy for
when your client machine is just a Raspberry Pi.

And, if other Home Hub providers can ship audio off from their Home Hub to the
cloud to process, then it seems only fair that we can do something like that
too.
"""

from   threading  import Thread

import argparse
import logging
import numpy
import os
import socket
import struct
import time
import whisper

# ------------------------------------------------------------------------------

_MODELS = ('tiny', 'base', 'small', 'medium', 'large')

# ------------------------------------------------------------------------------

def handle(conn, translate):
    """
    Create a new thread for the given connection and start it.
    """
    thread = Thread(target=lambda: run(conn, translate))
    thread.daemon = True
    thread.start()


def run(conn, translate):
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
        logging.info("%d channel(s), %d byte(s) wide, %dHz",
                     channels, width, rate)

        # We only handle 16kHz mono right now
        if rate != 16000:
            raise ValueError("Can only decode 16000Hz but had %dHz", rate)
        if channels != 1:
            raise ValueError("Can only decode 1 channel but had %d", channels)

        # Keep pulling in the data until we get an empty chunk
        data = b''
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
                logging.debug("Got end of data")
                break

            # Pull in the chunk
            logging.debug("Reading %d bytes of data", length)
            start = len(data)
            while len(data) - start < length:
                got = conn.recv(length - (len(data) - start))
                if len(got) == 0:
                    time.sleep(0.001)
                    continue
                data += got

        # Convert to a numpy array. Whisper expects a numpy float array
        # normalised between +/-1.0..
        if   width == 1:
            audio = numpy.frombuffer(data, numpy.int8 ).astype(numpy.float32) / 2.0**7
        elif width == 2:
            audio = numpy.frombuffer(data, numpy.int16).astype(numpy.float32) / 2.0**15
        elif width == 4:
            audio = numpy.frombuffer(data, numpy.int32).astype(numpy.float32) / 2.0**31
        elif width == 8:
            audio = numpy.frombuffer(data, numpy.int64).astype(numpy.float32) / 2.0**63

        # Finally, decode it
        logging.info("Decoding %0.2f seconds of audio",
                     len(data) / rate / width / channels)
        result = model.transcribe(audio,
                                  task='translate' if translate else 'transcribe')
        words = result['text'].strip()
        logging.info("Got: '%s'", words)

        # Send back the length (as a long) and the string
        words = words.encode()
        conn.sendall(struct.pack('!q', len(words)))
        conn.sendall(words)

    except Exception as e:
        # Tell the user at least
        logging.error("Error handling incoming data: %s", e)

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
parser = argparse.ArgumentParser(description='Running Whisper inference.')
parser.add_argument('--model', default='base',
                    help='The model type to use; one of %s' % ' '.join(_MODELS))
parser.add_argument('--port', type=int, default=8008,
                    help='The port number to listen on')
parser.add_argument('--translate', default=False, action='store_true',
                    help='Whether to translate to English')
args = parser.parse_args()

# Pull in the model
logging.info("Loading '%s' model", args.model,)
model = whisper.load_model(args.model)

# Set up the server socket
logging.info("Opening socket on port %d", args.port)
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
        handle(conn, args.translate)

    except Exception as e:
        # Tell the user at least
        logging.error("Error handling incoming connection: %s", e)
