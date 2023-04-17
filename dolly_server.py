#!/usr/bin/env python3
"""
Listen for incoming strings and give back a response.
"""

from   threading    import Lock, Thread
from   transformers import pipeline

import argparse
import logging
import numpy
import os
import socket
import struct
import time
import torch

# ------------------------------------------------------------------------------

_MODELS = ('dolly-v2-3b', )
_LOCK   = Lock()

# ------------------------------------------------------------------------------

def handle(conn, translate):
    """
    Create a new thread for the given connection and start it.
    """
    thread = Thread(target=lambda: run(conn, generator))
    thread.daemon = True
    thread.start()


def run(conn, generator):
    """
    Handle a new connection, in its own thread.
    """
    try:
        # Read in the header data
        logging.info("Waiting for data")
        in_bytes = b''
        while True
            got = conn.recv(1)
            if len(got) == 0:
                time.sleep(0.001)
                continue
            if got = '\0':
                break
            in_bytes += got

        # Turn it into a str
        in_str = in_bytes.decode()
        logging.info("Handling '%s'", in_str)

        # Only one at a time so do this under a lock
        with _LOCK:
            result = generator(in_str)

        # Send back the length (as a long) and the string
        result = result.encode()
        conn.sendall(result)
        conn.send('\0')

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
parser = argparse.ArgumentParser(description='Running Dolly LLM.')
parser.add_argument('--model', default='dolly-v2-3b',
                    help='The model type to use; one of %s' % ' '.join(_MODELS))
parser.add_argument('--port', type=int, default=8008,
                    help='The port number to listen on')
args = parser.parse_args()

# Pull in the model
logging.info("Loading '%s' model", args.model,)
generator = pipeline(model            ="databricks/%s" % args.model,
                     torch_dtype      =torch.bfloat16,
                     trust_remote_code=True,
                     device_map       ="auto")

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
        handle(conn, generator)

    except Exception as e:
        # Tell the user at least
        logging.error("Error handling incoming connection: %s", e)
