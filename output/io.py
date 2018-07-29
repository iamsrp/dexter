'''
Simple IO-based output.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import logging

from   dexter.core   import LOG
from   dexter.output import Output

# ------------------------------------------------------------------------------

class _FileOutput(Output):
    '''
    An L{Output} which just writes to a file handle.
    '''
    def __init__(self, notifier, handle):
        '''
        @type  notifier: L{Notifier}
        @param notifier:
            The Notifier instance.
        @type  handle: file
        @param handle:
            The file handle to write to.
        '''
        super(_FileOutput, self).__init__(notifier)
        assert handle is None or (hasattr(handle, 'write') and
                                  hasattr(handle, 'flush') and
                                  hasattr(handle, 'closed')), (
            "Given handle was not file-like: %s" % type(handle)
        )
        self._handle = handle


    def write(self, text):
        '''
        @see Output.write
        '''
        if text         is not None and \
           self._handle is not None and \
           not self._handle.closed:
            self._handle.write(str(text))
            self._handle.flush()


class StdoutOutput(_FileOutput):
    '''
    An output to C{stdout}.
    '''
    def __init__(self, notifier):
        '''
        @see Output.__init__()
        '''
        super(Stdout, self).__init__(notifier, sys.stdout)


class StderrOutput(_FileOutput):
    '''
    An output to C{stderr}.
    '''
    def __init__(self, notifier):
        '''
        @see Output.__init__()
        '''
        super(Stderr, self).__init__(notifier, sys.stderr)


class LogOutput(Output):
    '''
    An output which logs as a particular level to the system's log.
    '''
    def __init__(self, notifier, level=logging.INFO):
        '''
        @see Output.__init__()
        @type  level: int or str
        @param level:
            The level to log at.
        '''
        super(LogOutput, self).__init__(notifier)
        try:
            self._level = int(level)
        except:
            try:
                self._level = getattr(logging, level)
            except:
                raise ValueError("Bad log level: '%s'" % (level,))


    def write(self, text):
        '''
        @see Output.write
        '''
        LOG.log(self._level, str(text))
    
