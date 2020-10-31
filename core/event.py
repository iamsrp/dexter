"""
Events within the system.
"""

from dexter.core.log import LOG

import sys
import time

# ------------------------------------------------------------------------------

class Event(object):
    """
    The event base type.
    """
    def __init__(self, creation_time=None, runnable=None):
        """
        :type  creation_time: float, or None
        :param creation_time:
            The time at which this event was created, or None if it should be
            now. In seconds since epoch.
        :type  runnable: function () -> L{Event}
        :param runnable:
            A lambda to invoke when this event is handled. It may return another
            L{Event} instance, or C{None}.
        """
        self._creation_time = \
            float(creation_time) if creation_time is not None else time.time()
        self._runnable = runnable


        @property
        def creation_time(self):
            """
            The time at which this event was created, in seconds since epoch.
            """
            return self._creation_time


        def invoke(self):
            """
            Invoke this event.

            :rtype: Event, or None
            :return:
                Invoke this event to do its job. It may return another event as
                a result, which will be scheduled for handling.
            """
            if self._runnable is not None:
                return self._runnable()
            else:
                return None


class TimerEvent(Event):
    """
    An event which is set to fire at a given time.
    """
    def __init__(self, schedule_time, runnable=None):
        """
        @see L{Event.__init__}

        :type  schedule_time: float
        @parse schedule_time:
            The time at which this event should fire. In seconds since epoch.
        """
        super(Event, self).__init__(runnable=runnable)
        self._schedule_time = float(schedule_time)


        @property
        def schedule_time(self):
            """
            The time at which this event should be scheduled, in seconds since
            epoch.
            """
            return self._schedule_time
