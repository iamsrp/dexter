"""
The different types of notifier in the system.
"""

from dexter.core import Notifier

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
