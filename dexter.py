#!/usr/bin/env python3

from __future__ import (absolute_import, division, print_function, with_statement)

import argh
import logging
import json
import sys

sys.path[0] += '/..'

from dexter.core     import Dexter
from dexter.core.log import LOG

# ------------------------------------------------------------------------------

# WIP
CONFIG = {
    'key_phrases' : (
        "Hey Computer",
        "Hey Dexter",
    ),
    'components' : {
        'inputs' : (
            (
                'dexter.input.socket.SocketInput',
                {
                    'port' : '8008'
                }
            ),
            (
                'dexter.input.pocketsphinx.PocketSphinxInput',
                None
            ),
        ),
        'outputs' : (
            (
                'dexter.output.io.LogOutput',
                {
                    'level' : 'INFO'
                }
            ),
            (
                'dexter.output.espeak.EspeakOutput',
                None
            ),
        ),
        'services' : (
            (
                'dexter.service.echo.EchoService',
                None
            ),
        ),
    }
}

# ------------------------------------------------------------------------------

@argh.arg('--config', '-c',
          help="The JSON configuration file to use")
def main(config=None):
    '''
    Main entry point.
    '''
    if config is not None:
        try:
            with open(config) as fh:
                configuration = json.load(fh)
        except Exception as e:
            LOG.fatal("Failed to parse config file '%s': %s" % (config, e))
            sys.exit(1)
    else:
        configuration = _DEFAULT_CONFIG

    # And spawn it
    dexter = Dexter(configuration)
    dexter.run()


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        argh.dispatch_command(main)
    except Exception as e:
        print("%s" % e)
    
