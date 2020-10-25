#!/usr/bin/env python3

import argh
import logging
import json
import os
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
    """
    Main entry point.
    """
    # Load in any configuration
    if config is not None:
        try:
            with open(config) as fh:
                configuration = json.load(fh)
        except Exception as e:
            LOG.fatal("Failed to parse config file '%s': %s" % (config, e))
            sys.exit(1)
    else:
        configuration = CONFIG

    # Handle environment variables in the component kwargs, in the form of
    # "${VARNAME}". This isn't overly pretty, but it works.
    for typ in configuration['components']:
        # We might have kwargs for all the components
        for component in configuration['components'][typ]:
            (which, kwargs) = component
            if kwargs is None:
                continue

            # Look at all the kwargs which we have and check for environment
            # variables in the value names.
            for name in kwargs:
                value = kwargs[name]
                try:
                    while True:
                        start   = value.index('${')
                        end     = value.index('}', start)
                        varname = value[start+2:end]
                        value   = (value[:start] +
                                   os.environ.get(varname, '') +
                                   value[end+1:])
                except:
                    # This means we failed to find the opening or closing
                    # varname container in the string, so we're done
                    pass

                # If we changed it then save it back in
                if value != kwargs[name]:
                    LOG.info(
                        "Expanded component %s:%s:%s argument from '%s' to '%s'" %
                        (typ, which, name, kwargs[name], value)
                    )
                    kwargs[name] = value

    # And spawn it
    dexter = Dexter(configuration)
    dexter.run()


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        argh.dispatch_command(main)
    except Exception as e:
        print("%s" % e)
