"""
Functions for the TP Link Kasa smart home appliances.

This is very basic right now.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import COLORS, fuzzy_list_range, to_letters
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz
from   kasa             import SmartBulb, SmartPlug

import asyncio

# ------------------------------------------------------------------------------

class _KasaHandler(Handler):
    def __init__(self, service, tokens, score, routine):
        """
        @see Handler.__init__()

        :param routine: The generator for coroutine to execute.
        """
        super(_KasaHandler, self).__init__(service, tokens, score, True)

        self._routine = routine


    def handle(self):
        """
        @see Handler.handle()
        """

        # This might fail (because "cannot reuse already awaited coroutine") so
        # we assume that it's idempotent and do it a few times until it succeeds
        for _ in range(5):
            try:
                # If this work, then we're done, with no response needed
                coroutine = self._routine()
                LOG.info("Calling %s", coroutine)
                asyncio.run(coroutine)
                return None
            except Exception as e:
                LOG.warning("Failed to run coroutine: %s", e)


class KasaService(Service):
    """
    A service which controls Kasa smart devices.
    """
    # Actions that we support
    _TURN_ON  = 'turn on'
    _TURN_OFF = 'turn off'

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
        def make_routine(function, args=tuple()):
            return lambda: function(*args)

        # Match on these
        words = self._words(tokens)

        # Anything plausible?
        if len(words) < 2:
            # Nothing which we can match on
            return None

        # Look to match what we were given on a number of different phrasings
        score   = 0
        routine = None

        # Slightly complex commands first
        if (routine is None and
            len(words) >= 3 and
            fuzz.ratio(words[0], "turn") > 80):
            # Looking at "turn <the something> <something>". Find the device
            # first.
            name = ' '.join(words[1:-1])

            # We have something, so figure out the action
            action = to_letters(words[-1])
            if action in ("on", "off"):
                LOG.info("Matched 'turn <something> %s' in '%s'", action, words)

                # Look at all devices
                pair = self._find_device(name,
                                         (self._bulbs, self._plugs))

                # If we got anything then we figure out what we want to do
                if pair is not None:
                    # Pull out the bits
                    (device_score, device) = pair
                    new_score = (100 + device_score) / 2 / 100
                    if new_score > score:
                        LOG.debug("New score is %0.2f", new_score)
                        self._update_device(device)
                        try:
                            if action == "off":
                                routine = make_routine(device.turn_off)
                                score = new_score
                            elif action == "on":
                                routine = make_routine(device.turn_on)
                                score = new_score
                            LOG.debug("Created action to turn %s %s", name, action)
                        except AttributeError:
                            pass
            else:
                # Might be a colour
                color = COLORS.match(action)
                if color is not None:
                    LOG.info("Matched color 'turn <something> %s' in '%s' as %s",
                             action, words, color)
                    (action_score, (rgb, hsv)) = color

                    # Only bulbs can do this
                    pair = self._find_device(name, (self._bulbs,))
                    if pair is not None:
                        # Pull out the bits
                        (device_score, device) = pair
                        new_score = (action_score + device_score) / 2 / 100
                        if new_score > score:
                            LOG.debug("New score is %0.2f", new_score)
                            self._update_device(device)
                            try:
                                routine = make_routine(device.set_hsv, hsv)
                                score = new_score
                                LOG.debug("Created action to set the HSV to %s", hsv)
                            except AttributeError:
                                pass

        # Now try a different tack
        if routine is None:
            for action in (self._TURN_OFF,
                           self._TURN_ON):
                try:
                    # Match the different actions on the input
                    (start, end, action_score) = fuzzy_list_range(words,
                                                                  action.split())

                    # Did we match? The end has to be smaller than the number of
                    # words since we want to know what we're acting on.
                    if start == 0 and end < len(words):
                        LOG.info("Matched '%s' on '%s'", action, words)
                        # Now we look for the device
                        pair = self._find_device(' '.join(words[end:]),
                                                 (self._bulbs, self._plugs))

                        # If we got anything then we figure out what we want to do
                        if pair is not None:
                            # Pull out the bits
                            (device_score, device) = pair
                            new_score = (action_score + device_score) / 2 / 100
                            if new_score > score:
                                LOG.debug("New score is %0.2f", new_score)
                                self._update_device(device)
                                try:
                                    if action == self._TURN_ON:
                                        routine = make_routine(device.turn_on)
                                        score = new_score
                                    elif action == self._TURN_OFF:
                                        routine = make_routine(device.turn_off)
                                        score = new_score
                                except AttributeError:
                                    pass
                except ValueError:
                    pass

        # Now we can give back a handler, if we know what we're doing
        if routine is not None:
            # Compute the combined score, and shift it to be in the
            # range 0..1
            return _KasaHandler(self, tokens, score, routine)
        else:
            return None


    def _find_device(self, want, device_dicts, threshold=50):
        """
        Look for the device with the given name and return its object.

        :return: The ``(score, device)`` pair.
        """
        # Null breeds null
        if want is None or want == "":
            return None

        # Score all the devices by fuzzy matching
        choices = []
        for devices in device_dicts:
            for (name, device) in devices.items():
                score = fuzz.ratio(name, want)
                LOG.debug('"%s" matches "%s" with score %d', want, name, score)
                if score > threshold:
                    choices.append((score, device))

        # If we have anything then give back the best one
        if len(choices) > 0:
            LOG.debug("Choices are: %s", choices)
            return sorted(choices, key=lambda pair: -pair[0])[0]
        else:
            return None


    def _update_device(self, device):
        """
        Call update on the device, which might fail.
        """
        if device is not None:
            for _ in range(5):
                try:
                    asyncio.run(device.update())
                except Exception as e:
                    LOG.warning("Failed to update %s: %s", device, e)
