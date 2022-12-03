#!/usr/bin/env python3

import argh
import getpass
import logging
import pyjson5
import os
import socket
import sys

sys.path[0] += '/..'

from dexter.core     import Dexter
from dexter.core.log import LOG

# ------------------------------------------------------------------------------

# A very basic configuration which should work on most things if people have
# installed the various requirements. Not very exciting though.
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
        ),
        'outputs' : (
            (
                'dexter.output.io.LogOutput',
                {
                    'level' : 'INFO'
                }
            ),
            (
                'dexter.output.festvox.FestivalOutput',
                None
            ),
        ),
        'services' : (
            (
                'dexter.service.dev.EchoService',
                None
            ),
        ),
    }
}

# ------------------------------------------------------------------------------

def _replace_envvars(value):
    """
    Replace any environment variables in the given type.

    :return: A deep copy of the type with the values replaced.
    """
    if type(value) == str:
        return _replace_envvars_str(value)
    elif type(value) == tuple or type(value) == list:
        return _replace_envvars_list(value)
    elif type(value) == dict:
        return _replace_envvars_dict(value)
    else:
        return value


def _replace_envvars_str(value):
    """
    Look for environment variables in the form of ``${VARNAME}`` and replace them
    with their values. This isn't overly pretty, but it works.
    """
    try:
        while True:
            # Pull out the variable name, if it exists
            start    = value.index('${')
            end      = value.index('}', start)
            varname  = value[start+2:end]
            varvalue = os.environ.get(varname, '')

            # Special handling for some variables
            if not varvalue:
                # These are not always set in the environment but
                # people tend to expect it to be, so we are nice and
                # provide them
                if varname == "HOSTNAME":
                    varvalue = socket.gethostname()
                elif varname == "USER":
                    varvalue = getpass.getuser()

            # And replace it
            value = (value[:start] + varvalue + value[end+1:])
    except:
        # This means we failed to find the opening or closing
        # varname container in the string, so we're done
        pass
    
    # Give it back
    return value


def _replace_envvars_list(value):
    try:
        return [_replace_envvars(v) for v in value]
    except:
        return value


def _replace_envvars_dict(value):
    try:
        return dict((k, _replace_envvars(v)) for (k,v) in value.items())
    except:
        return value


# ------------------------------------------------------------------------------

# Main entry point
@argh.arg('--log-level', '-L',
          help="The logging level to use")
@argh.arg('--config', '-c',
          help="The JSON configuration file to use")
def main(log_level=None, config=None):
    """
    Dexter is a personal assistant which responds to natural language for its
    commands.
    """
    # Set the log level, if supplied
    if log_level is not None:
        try:
            LOG.getLogger().setLevel(int(log_level))
        except:
            LOG.getLogger().setLevel(log_level.upper())

    # Load in any configuration
    if config is not None:
        try:
            with open(config) as fh:
                configuration = pyjson5.load(fh)
        except Exception as e:
            LOG.fatal("Failed to parse config file '%s': %s" % (config, e))
            sys.exit(1)
    else:
        configuration = CONFIG

    # Handle environment variables in the component kwargs
    for typ in configuration['components']:
        # We might have kwargs for all the components
        for component in configuration['components'][typ]:
            (which, kwargs) = component
            if kwargs is None:
                continue

            # Look at all the kwargs which we have and check for environment
            # variables in the value names.
            updated = _replace_envvars(kwargs)
            for name in kwargs:
                # If we changed it then save it back in
                if updated[name] != kwargs[name]:
                    LOG.info(
                        "Expanded component %s:%s:%s argument from '%s' to '%s'" %
                        (typ, which, name, kwargs[name], updated[name])
                    )
                    kwargs[name] = updated[name]

    # And spawn it
    dexter = Dexter(configuration)
    dexter.run()


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        argh.dispatch_command(main)
    except Exception as e:
        print("%s" % e)
