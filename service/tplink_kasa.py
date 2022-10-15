"""
Functions for the TP Link Kasa smart home appliances.

This is very basic right now.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz
from   kasa             import SmartBulb, SmartPlug

import asyncio

# ------------------------------------------------------------------------------

class _KasaHandler(Handler):
    def __init__(self, service, tokens, score, coroutine):
        """
        @see Handler.__init__()

        :param coroutine: The coroutine to execute.
        """
        super(_KasaHandler, self).__init__(service, tokens, score, True)

        self._coroutine = coroutine


    def handle(self):
        """
        @see Handler.handle()
        """

        # This might fail (because "cannot reuse already awaited coroutine") so
        # we assume that it's idempotent and do it a few times until it succeeds
        for _ in range(5):
            try:
                # If this work, then we're done, with no response needed
                asyncio.run(self._coroutine)
                return None
            except:
                pass


class KasaService(Service):
    """
    A service which controls Kasa smart devices.
    """
    # Actions that we support
    _TURN_ON  = 'turn_on'
    _TURN_OFF = 'turn_off'

    def __init__(self,
                 state,
                 bulbs={},
                 plugs={}):
        """
        @see Service.__init__()

        :param bulbs: The dict of bulb names to IP addresses.
        :param plugs: The dict of plug names to IP addresses.
        """
        super(KasaService, self).__init__("Kasa", state)

        self._bulbs = { name : SmartBulb(ip) for (name, ip) in bulbs.items() }
        self._plugs = { name : SmartPlug(ip) for (name, ip) in plugs.items() }


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Look to match what we were given on a number of different phrasings
        words = self._words(tokens)
        for action in (self._TURN_OFF,
                       self._TURN_ON):
            try:
                # Match the different actions on the input
                (start, end, action_score) = fuzzy_list_range(words, action.split())

                # Did we match? The end has to be smaller than the number of
                # words since we want to know what we're acting on.
                if start == 0 and end < len(words):
                    LOG.info("Matched '%s' on '%s'", action, words)
                    # Now we look for the device
                    pair = self._find_device(' '.join(words[end:]))

                    # If we got anything then we figure out what we want to do
                    coroutine = None
                    if pair is not None:
                        # Pull out the bits
                        (device_score, device) = pair
                        try:
                            if action == self._TURN_ON:
                                coroutine = device.turn_on()
                            elif action == self._TURN_OFF:
                                coroutine = device.turn_off()
                        except AttributeError:
                            pass

                    # Now we can give back a handler, if we know what we're doing
                    if coroutine is not None:
                        # Compute the combined score, and shift it to be in the
                        # range 0..1
                        score = (action_score + device_score) / 2 / 100
                        return _KasaHandler(self, tokens, score, coroutine)
            except ValueError:
                pass

        return None


    def _find_device(self, want, threshold=50):
        """
        Look for the device with the given name and return its object.

        :return: The ``(score, device)`` pair.
        """
        # Score all the devices by fuzzy matching
        choices = []
        for (name, device) in self._bulbs.items():
            score = fuzz.ratio(name, want)
            LOG.info('"%s" matches "%s" with score %d', want, name, score)
            if score > threshold:
                choices.append((score, device))
        for (name, device) in self._plugs.items():
            LOG.info('"%s" matches "%s" with score %d', want, name, score)
            score = fuzz.ratio(name, want)
            if score > threshold:
                choices.append((score, device))

        # If we have anything then give back the best one
        if len(choices) > 0:
            LOG.info("Choices are: %s", choices)
            return sorted(choices, key=lambda pair: -pair[0])[0]
        else:
            return None
