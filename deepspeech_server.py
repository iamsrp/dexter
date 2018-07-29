#!/usr/bin/env python
'''
Listen for incoing data and give back parsed results.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

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
print("Loading %s" % model)
model = Model(model,
              _NUM_FEATURES,
              _NUM_CONTEXT,
              alphabet,
              _BEAM_WIDTH)

# Add the language model
print("Loading %s" % lm)
model.enableDecoderWithLM(alphabet,
                          lm,
                          trie,
                          _LM_WEIGHT,
                          _WORD_COUNT_WEIGHT,
                          _VALID_WORD_COUNT_WEIGHT)

# Set up the server socket
port = 8008
print("Opening socket on port %d" % (port,))
sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sckt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sckt.bind(('0.0.0.0', port))
sckt.listen(5)

# Do this forever
while True:
    try:
        # Get a connection
        print("Waiting for a connection")
        (conn, addr) = sckt.accept()
        print("Got connection from %s" % (addr,))

        # Read in the header data
        print("Reading header")
        header = ''
        while len(header) < (4 * 8):
            header += conn.recv((4 * 8) - len(header))

        # Unpack to variables
        (channels, width, rate, length) = struct.unpack('!qqqq', header)

        # Pull in the data
        print("Reading %d bytes of data" % (length,))
        data = ''
        while len(data) < length:
            data += conn.recv(length - len(data))

        # Actually decode it
        print("Decoding")
        audio = numpy.frombuffer(data, numpy.int16)
        words = model.stt(audio, rate)
        print("Got: %s" % (words,))

        # Send back the length (as a long) and the string
        conn.sendall(struct.pack('!q', len(words)))
        conn.sendall(words)

    except Exception as e:
        # Tell the user at least
        print("Error handling incoming data: %s" % e)

    finally:
        # We're done with this connection now, close in a best-effort fashion
        try:
            print("Closing connection")
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        except:
            pass

        
