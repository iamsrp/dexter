'''
How Dexter sends information to the outside world.

This might be via speech synthesis, a display, logging, etc.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import logging

from   dexter.core import LOG, Component

# ------------------------------------------------------------------------------

class Output(Component):
    '''
    A way to get information to the outside world.
    '''
    def __init__(self):
        super(Output, self).__init__()


    def write(self, text):
        '''
        Send the given text to the outside world.

        @type  text: str
        @param text:
            What to write.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")



class _FileOutput(Output):
    '''
    An L{Output} which just writes to a file handle.
    '''
    def __init__(self, handle):
        '''
        @type  handle: file
        @param handle:
            The file handle to write to.
        '''
        super(_FileOutput, self).__init__()
        assert handle is None or (hasattr(handle, 'write') and
                                  hasattr(handle, 'flush') and
                                  hasattr(handle, 'closed')), (
            "Given handle was not file-like: %s" % type(handle)
        )
        self._handle = handle


    def write(self, text):
        if text         is not None and \
           self._handle is not None and \
           not self._handle.closed:
            self._handle.write(str(text))
            self._handle.flush()


class StdoutOutput(_FileOutput):
    '''
    An output to C{stdout}.
    '''
    def __init__(self):
        super(Stdout, self).__init__(sys.stdout)


class StderrOutput(_FileOutput):
    '''
    An output to C{stderr}.
    '''
    def __init__(self):
        super(Stderr, self).__init__(sys.stderr)


class LogOutput(Output):
    '''
    An output which logs as a particular level to the system's log.
    '''
    def __init__(self, level=logging.INFO):
        '''
        @type  level: int or str
        @param level:
            The level to log at.
        '''
        super(LogOutput, self).__init__()
        try:
            self._level = int(level)
        except:
            try:
                self._level = getattr(logging, level)
            except:
                raise ValueError("Bad log level: '%s'" % (level,))


    def write(self, text):
        LOG.log(self._level, str(text))
    
