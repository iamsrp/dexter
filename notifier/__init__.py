"""
The different types of notifier in the system.
"""

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   threading       import Thread

import time

# ------------------------------------------------------------------------------

class ByComponentNotifier(Notifier):
    """
    A notifier which can do different things depending on the type of component
    which is updating it.
    """
    def _is_input(self, component):
        """
        Whether this input type is an Input.
        """
        return component is not None and component.is_input


    def _is_output(self, component):
        """
        Whether this output type is an Output.
        """
        return component is not None and component.is_output


    def _is_service(self, component):
        """
        Whether this service type is a Service.
        """
        return component is not None and component.is_service


class PulsingNotifier(ByComponentNotifier):
    """
    A notifier which uses a display with one or more pulsers (e.g. LEDs), which
    we will drive.
    """
    def __init__(self):
        """
        @see ByComponentNotifier.__init__()
        """
        super().__init__()

        # The time, since epoch, when each component type stopped being active
        self._input_time   = 0
        self._service_time = 0
        self._output_time  = 0

        # The direction of the swirl
        self._input_dir   = 0
        self._service_dir = 0
        self._output_dir  = 0

        # The currently non-idle components
        self._inputs   = set()
        self._services = set()
        self._outputs  = set()


    def update_status(self, component, status):
        """
        @see Notifier.update_status()
        """
        # Do nothing for bad inputs
        if component is None or status is None:
            return

        # See if the component has become idle or not
        if status is Notifier.IDLE:
            # Gone idle, remove it from the appropriate group. If that group
            # goes empty then wipe out the time.
            if self._is_input(component):
                if component in self._inputs:
                    self._inputs.remove(component)
                if len(self._inputs)   == 0:
                    self._input_time    = 0
                    self._input_dir     = 0
            if self._is_service(component):
                if component in self._services:
                    self._services.remove(component)
                if len(self._services) == 0:
                    self._service_time  = 0
                    self._service_dir   = 0
            if self._is_output(component):
                if component in self._outputs:
                    self._outputs.remove(component)
                if len(self._outputs)  == 0:
                    self._output_time   = 0
                    self._output_dir    = 0
        else:
            # Gone non-idle, add it to the appropriate group and reset the time
            if self._is_input(component):
                self._inputs.add(component)
                self._input_time   = time.time()
                self._input_dir    = 1 if status is Notifier.ACTIVE else -1
            if self._is_service(component):
                self._services.add(component)
                self._service_time = time.time()
                self._service_dir  = 1 if status is Notifier.ACTIVE else -1
            if self._is_output(component):
                self._outputs.add(component)
                self._output_time  = time.time()
                self._output_dir   = 1 if status is Notifier.ACTIVE else -1


    def _start(self):
        """
        @see Notifier._start()
        """
        # The thread which will maintain the display
        thread = Thread(target=self._updater)
        thread.deamon = True
        thread.start()


    def _updater(self):
        """
        The method which will maintain the pulsers.
        """
        # Some state variables
        i_mult     = 0.0
        s_mult     = 0.0
        o_mult     = 0.0
        i_velocity = 0.0
        s_velocity = 0.0
        o_velocity = 0.0

        # And off we go!
        LOG.info("Started update thread")
        while self.is_running:
            # Don't busy-wait
            time.sleep(0.01)

            # What time is love?
            now = time.time()

            # How long since these components went non-idle
            i_since = now - self._input_time
            s_since = now - self._service_time
            o_since = now - self._output_time

            # See what state we want these guys to be in. After 30s we figure
            # that the component is hung and turn it off.
            i_state = 1.0 if i_since < 30.0 else 0.0
            s_state = 1.0 if s_since < 30.0 else 0.0
            o_state = 1.0 if o_since < 30.0 else 0.0

            # Slide the multiplier and direction accordingly
            f = 0.2
            i_mult = (1.0 - f) * i_mult + f * i_state
            s_mult = (1.0 - f) * s_mult + f * s_state
            o_mult = (1.0 - f) * o_mult + f * o_state
            f = 0.01
            i_velocity  = (1.0 - f) * i_velocity  + f * self._input_dir
            s_velocity  = (1.0 - f) * s_velocity  + f * self._service_dir
            o_velocity  = (1.0 - f) * o_velocity  + f * self._output_dir

            # And pass these to the updater function
            self._update(now,
                         (i_since, i_mult, self._input_dir,   i_velocity),
                         (s_since, s_mult, self._service_dir, s_velocity),
                         (o_since, o_mult, self._output_dir,  o_velocity))

        # And we're done
        LOG.info("Stopped update thread")


    def _update(self, now, input_state, service_state, output_state):
        """
        Update the notifier with the current state info. Each of the states is a
        tuple made up from the following values::
          since      -- How long it has been active for, in seconds.
          direction  -- +1 for "outgoing", -1 for "incoming", 0 for nothing.
          state_mult -- From 0.0 (off) to 1.0 (on).
          velocity   -- The directional speed of the current state.
        """
        pass
