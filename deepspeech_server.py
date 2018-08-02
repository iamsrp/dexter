#!/usr/bin/env python3
'''
Listen for incoming data and give back parsed results.

This can be run a machine with a decent amount of oomph and the L{RemoteService}
can talk to it instead of doing the speech-to-text locally. Thias is handy for
when your client machine is just a Raspberry Pi.

And, if Google can ship audio off from its Home device to the cloud to process,
then it seems only fair that we can do something like that too.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import logging
import numpy
import os
import socket
import struct

from deepspeech.model   import Model

# ------------------------------------------------------------------------------

# Typical installation location for deepspeech data
_MODEL_DIR = "/usr/local/share/deepspeech/models"

# Beam width used in the CTC decoder when building candidate transcriptions
_BEAM_WIDTH = 500

# These constants are tied to the shape of the graph used (changing them changes
# the geometry of the first layer), so make sure you use the same constants that
# were used during training

# Number of MFCC features to use
_NUM_FEATURES = 26

# Size of the context window used for producing timesteps in the input vector
_NUM_CONTEXT = 9

# The alpha hyperparameter of the CTC decoder. Language Model weight
_LM_WEIGHT = 1.75

# The beta hyperparameter of the CTC decoder. Word insertion weight (penalty)
_WORD_COUNT_WEIGHT = 1.00

# Valid word insertion weight. This is used to lessen the word insertion penalty
# when the inserted word is part of the vocabulary
_VALID_WORD_COUNT_WEIGHT = 1.00

# ------------------------------------------------------------------------------

# Set up the logger
logging.basicConfig(
    format='[%(asctime)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
    level=logging.INFO
)

# The files which we'll need from the model directory
alphabet = os.path.join(_MODEL_DIR, 'alphabet.txt')
model    = os.path.join(_MODEL_DIR, 'output_graph.pb')
lm       = os.path.join(_MODEL_DIR, 'lm.binary')
trie     = os.path.join(_MODEL_DIR, 'trie')

# If these don't exist then DeepSpeech will segfault when inferring!
if not os.path.exists(alphabet):
    raise IOError("Not found: %s" % alphabet)
if not os.path.exists(model):
    raise IOError("Not found: %s" % model)
if not os.path.exists(lm):
    raise IOError("Not found: %s" % lm)
if not os.path.exists(trie):
    raise IOError("Not found: %s" % trie)

# Load in the model
logging.info("Loading %s" % model)
model = Model(model,
              _NUM_FEATURES,
              _NUM_CONTEXT,
              alphabet,
              _BEAM_WIDTH)

# Add the language model
logging.info("Loading %s" % lm)
model.enableDecoderWithLM(alphabet,
                          lm,
                          trie,
                          _LM_WEIGHT,
                          _WORD_COUNT_WEIGHT,
                          _VALID_WORD_COUNT_WEIGHT)

# Set up the server socket
port = 8008
logging.info("Opening socket on port %d" % (port,))
sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sckt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sckt.bind(('0.0.0.0', port))
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
            header += conn.recv((4 * 8) - len(header))

        # Unpack to variables
        (channels, width, rate, length) = struct.unpack('!qqqq', header)

        # Pull in the data
        logging.info("Reading %d bytes of data" % (length,))
        data = b''
        while len(data) < length:
            data += conn.recv(length - len(data))

        # Actually decode it
        logging.info("Decoding")
        audio = numpy.frombuffer(data, numpy.int16)
        words = model.stt(audio, rate)
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

        
