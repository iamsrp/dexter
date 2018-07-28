#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function, with_statement)

import logging
import sys

sys.path[0] += '/..'

from dexter.core import LOG, Dexter

# ------------------------------------------------------------------------------

# WIP
CONFIG = {
    'inputs' : (
        ('dexter.input.socket.SocketInput', {'port' : '8008'}),
    ),
    'outputs' : (
        ('dexter.output.io.LogOutput', {'level' : 'INFO'}),
    ),
    'services' : (
        ('dexter.service.echo.EchoService', {}),
    )
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
    return klass(**kwargs)

# ------------------------------------------------------------------------------

LOG.basicConfig(
    format='[%(asctime)s %(threadName)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
    level=logging.INFO
)

inputs   = [get_component(classname, kwargs)
            for (classname, kwargs) in CONFIG['inputs']]
outputs  = [get_component(classname, kwargs)
            for (classname, kwargs) in CONFIG['outputs']]
services = [get_component(classname, kwargs)
            for (classname, kwargs) in CONFIG['services']]

dexter = Dexter(inputs, outputs, services)
dexter.run()
