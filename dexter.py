#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function, with_statement)

import logging
import sys

sys.path[0] += '/..'

from dexter.core import LOG, Dexter

# ------------------------------------------------------------------------------

# WIP
CONFIG = {
    'key_phrase' : "Hey Computer",
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

def get_component(full_classname, kwargs):
    '''
    The the instance of the given L{Component}.

    @type  full_classname: str
    @param full_classname:
        The fully qualified classname, e.g. 'dexter,input.AnInput'
    '''
    (module, classname) = full_classname.rsplit('.', 1)
    exec ('from %s import %s'  % (module, classname,))
    exec ('klass = %s'         % (        classname,))
    if kwargs is None:
        return klass()
    else:
        return klass(**kwargs)

# ------------------------------------------------------------------------------

LOG.basicConfig(
    format='[%(asctime)s %(threadName)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
    level=logging.INFO
)

components = CONFIG['components']

inputs   = [get_component(classname, kwargs)
            for (classname, kwargs) in components.get('inputs', [])]
outputs  = [get_component(classname, kwargs)
            for (classname, kwargs) in components.get('outputs', [])]
services = [get_component(classname, kwargs)
            for (classname, kwargs) in components.get('services', [])]

key_phrase = CONFIG.get('key_phrase', "Hey Computer")

dexter = Dexter(key_phrase, inputs, outputs, services)
dexter.run()
