from __future__ import (absolute_import, division, print_function, with_statement)

import logging
import time

# The log used by all of the system
LOG = logging

# ------------------------------------------------------------------------------

class Component(object):
    '''
    A part of the system.
    '''
    def __init__(self):
        super(Component, self).__init__()


    def start(self):
        '''
        Start this component going.
        '''
        pass


    def stop(self):
        '''
        Stop this component.
        '''
        pass


# ------------------------------------------------------------------------------

class Dexter(object):
    '''
    The main class which drives the system.
    '''
    def __init__(self, inputs, outputs, services):
        '''
        @type  inputs: tuple(L{Inputs})
        @param inputs:
            The L{Inputs}s to the system.
        @type  outputs: tuple(L{Outputs})
        @param outputs:
            The L{Outputs}s from the system.
        @type  services: tuple(L{Service})
        @param services:
            The L{Service}s which this instance will provide. 
        '''
        self._inputs   = inputs
        self._outputs  = outputs
        self._services = services
        self._running  = True


    def run(self):
        '''
        The main worker.
        '''
        LOG.info("Starting the system")
        self._start()

        LOG.info("Entering main loop")
        while self._running:
            try:
                # Loop over all the inputs and see if they have anything pending
                for input in self._inputs:
                    # Attempt a read, this will return None if there's nothing
                    # available
                    tokens = input.read()
                    if tokens is not None:
                        # Okay, we read something, attempt to handle it
                        LOG.info("Read from %s: %s" % (input, tokens))
                        result = self._handle(tokens)

                        # If we got something back then give it back to the user
                        if result is not None:
                            self._respond(result)

                # Wait for a bit before going around again
                time.sleep(0.1)

            except KeyboardInterrupt:
                LOG.warning("KeyboardInterrupt received")
                break

        # We're out of the main loop, shut things down
        LOG.info("Stopping the system")
        self._stop()


    def _start(self):
        '''
        Start the system going.
        '''
        for component in self._inputs + self._outputs + self._services:
            # If these throw then it's fatal
            LOG.info("Starting %s" % (component,))
            component.start()


    def _stop(self):
        '''
        Stop the system.
        '''
        for component in self._inputs + self._outputs + self._services:
            # Best effort, since we're likely shutting down
            try:
                LOG.info("Stopping %s" % (component,))
                component.stop()
            except Exception as e:
                LOG.error("Failed to stop %s: %$s" % (component, e))


    def _handle(self, tokens):
        '''
        Handle a list of L{Token}s from the input.
        '''
        # Give back nothing if we have no tokens
        if tokens is None:
            return None

        # See which services want them
        handlers = []
        for service in self._services:
            handler = service.evaluate(tokens)
            if handler is not None:
                handlers.append(handler)

        # Anything?
        if len(handlers) == 0:
            return "I'm sorry, I don't know how to help with that"

        # Okay, put the handlers into order of belief and try them. Notice that
        # we want the higher beliefs first so we flip the pair in the cmp call.
        handlers = sorted(handlers, cmp=lambda a, b: cmp(b.belief, a.belief))

        # Now try each of the handlers
        response = ''
        error    = False
        for handler in handlers:
            try:
                # Invoked the handler and see what we get back
                result = handler.handle()
                if result is None:
                    continue

                # Accumulate into the resultant text
                if result.text is not None:
                    response += result.text

                # Stop here?
                if result.is_exclusive:
                    break
                
            except Exception as e:
                error = True
                LOG.error(
                    "Handler %s with tokens %s for service %s yielded: %s" %
                    (handler, handler.tokens, handler.service, e)
                )

        # Give back whatever we had, if anything
        if len(response) > 0:
            return response
        else:
            return None


    def _respond(self, response):
        '''
        Given back the response to the user via the outputs.
        '''
        # Give back nothing if we have no response
        if response is None:
            return None

        # Simply hand it to all the outputs
        for output in self._outputs:
            try:
                output.write(response)
            except Exception as e:
                LOG.error("Failed to respond with %s: %s" % (output, e))
        
