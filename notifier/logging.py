'''
A simple notifer which logs.
'''

from dexter.core     import Notifier
from dexter.core.log import LOG

# ------------------------------------------------------------------------------

class LogNotifier(Notifier):
    '''
    A notifier which just logs status changes.
    '''
    def update_status(self, component, status):
        '''
        @see Notifier.update_status()
        '''
        # Sanity
        if component is None or status is None:
            return

        LOG.info("Component %s is now %s", component, status)
