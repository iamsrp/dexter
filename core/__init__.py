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


    def __str__(self):
        return type(self).__name__

# ------------------------------------------------------------------------------

class Dexter(object):
    '''
    The main class which drives the system.
    '''
    @staticmethod
    def _to_letters(word):
        '''
        Remove non-letters from a word.
        '''
        return ''.join(char 
                       for char in word
                       if 'a' <= char.lower() <= 'z')
        

    @staticmethod
    def _parse_key_phrase(phrase):
        '''
        Turn a string into a tuple, without punctuation, as lowercase.
        '''
        result = []
        for word in phrase.split(' '):
            # Strip to non-letters and only append if it's not the empty string
            word = Dexter._to_letters(word)
            if word != '':
                result.append(word.lower())

        # Safe to append
        return tuple(result)


    @staticmethod
    def _list_index(list, sublist, start=0):
        '''
        Find the index of of a sublist in a list.
        '''
        # The empty list can't be in anything
        if len(sublist) == 0:
            raise ValuError("Empty sublist not in list")

        # Simple case
        if len(sublist) == 1:
            return list.index(sublist[0], start)

        # Okay, we have multiple elements in our sublist. Look for the first
        # one, and see that it's adjacent to the rest of the list. We 
        offset = start
        while True:
            try:
                first = Dexter._list_index(list, sublist[ :1], offset)
                rest  = Dexter._list_index(list, sublist[1: ], first + 1)
                if first + 1 == rest:
                    return first

            except ValueError:
                raise ValueError('%s not in %s' % (sublist, list))

            # Move the offset to be after the first instance of sublist[0], so
            # that we may find the next one, if any
            offset = first + 1


    def __init__(self,
                 key_phrase,
                 inputs,
                 outputs,
                 services):
        '''
        @type  key_phrase: str
        @param key_phrase:
            The words which will cause the system to pick up a command.
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
        self._key_phrase = Dexter._parse_key_phrase(key_phrase)
        self._inputs     = inputs
        self._outputs    = outputs
        self._services   = services

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

        # See if the key-phrase is in the tokens and use it to determine the
        # offset of the command.
        try:
            words = [Dexter._to_letters(token.element).lower()
                     for token in tokens]
            offset = (Dexter._list_index(words, self._key_phrase) +
                      len(self._key_phrase))

        except ValueError as e:
            LOG.info("Key pharse not found: %s" % e)
            return None

        # See which services want them
        handlers = []
        for service in self._services:
            handler = service.evaluate(tokens[offset:])
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
        
