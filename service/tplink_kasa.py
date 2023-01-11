"""
Functions for the TP Link Kasa smart home appliances.

This is very basic right now.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import (COLORS,
                                as_list,
                                fuzzy_list_range,
                                parse_number,
                                to_alphanumeric,
                                to_letters)
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz
from   kasa             import SmartBulb, SmartPlug
from   threading        import Thread

import asyncio

# ------------------------------------------------------------------------------

class _KasaHandler(Handler):
    def __init__(self, service, tokens, score, routines):
        """
        @see Handler.__init__()

        :param routines: The generators for coroutines to execute.
        """
        super(_KasaHandler, self).__init__(service, tokens, score, True)

        self._routines = routines


    def handle(self):
        """
        @see Handler.handle()
        """
        # Spawn a thread for each routine and wait for them all the complete. We
        # do this so that all the actions can happen in parallel, if we have a
        # lot of different things to do.
        threads = [self._spawn(routine) for routine in self._routines]
        for thread in threads:
            thread.join()


    def _spawn(self, routine):
        """
        Spawn a thread to run the given coroutine.
        """
        # What we run in the thread
        def target():
            # This might fail (because "cannot reuse already awaited coroutine") so
            # we assume that it's idempotent and do it a few times until it succeeds
            for _ in range(5):
                try:
                    # If this work, then we're done, with no response needed
                    coroutine = routine()
                    LOG.info("Calling %s", coroutine)
                    asyncio.run(coroutine)
                    return None
                except Exception as e:
                    LOG.warning("Failed to run coroutine: %s", e)

        # Spawn it and give it back
        thread = Thread(name='KasaWorker', target=target)
        thread.daemon = True
        thread.start()
        return thread


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

        self._bulbs = {
            name : [
                SmartBulb(ip) for ip in as_list(ips)
            ]
            for (name, ips) in bulbs.items()
        }
        self._plugs = {
            name : [
                SmartPlug(ip) for ip in as_list(ips)
            ]
            for (name, ips) in plugs.items()
        }


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
        score    = 0
        routines = None

        # Do the simpler commands first since they are more likely to match
        # correctly.
        if routines is None:
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
                        # Now we look for the devices
                        pair = self._find_devices(' '.join(words[end:]),
                                                  (self._bulbs, self._plugs))

                        # If we got anything then we figure out what we want to do
                        if pair is not None:
                            # Pull out the bits
                            (device_score, devices) = pair
                            new_score = (action_score + device_score) / 2 / 100
                            if new_score > score:
                                LOG.debug("New score is %0.2f", new_score)
                                self._update_devices(devices)
                                try:
                                    if action == self._TURN_ON:
                                        routines = [
                                            make_routine(device.turn_on)
                                            for device in devices
                                        ]
                                        score = new_score
                                    elif action == self._TURN_OFF:
                                        routines = [
                                            make_routine(device.turn_off)
                                            for device in devices
                                        ]
                                        score = new_score
                                except AttributeError:
                                    pass
                except ValueError:
                    pass

        # Now the more complex commands
        if (routines is None and
            len(words) >= 3 and
            (fuzz.ratio(words[0], "set" ) > 80 or
             fuzz.ratio(words[0], "turn") > 80)):
            # Looking at "turn <the something> <something>". Find the device
            # first.
            if words[-2] == "to":
                name = ' '.join(words[1:-2])
            else:
                name = ' '.join(words[1:-1])

            # We have something, so figure out the action
            action = to_alphanumeric(words[-1]).rstrip('.')
            if action in ("on", "off"):
                LOG.info("Matched 'set|turn <something> [to] %s' in '%s'", action, words)

                # Look at all devices
                pair = self._find_devices(name,
                                          (self._bulbs, self._plugs))

                # If we got anything then we figure out what we want to do
                if pair is not None:
                    # Pull out the bits
                    (device_score, devices) = pair
                    new_score = (100 + device_score) / 2 / 100
                    if new_score > score:
                        LOG.debug("New score is %0.2f", new_score)
                        self._update_devices(devices)
                        try:
                            if action == "off":
                                routines = [
                                    make_routine(device.turn_off)
                                    for device in devices
                                ]
                                score = new_score
                            elif action == "on":
                                routines = [
                                    make_routine(device.turn_on)
                                    for device in devices
                                ]
                                score = new_score
                            LOG.debug("Created action to turn %s %s", name, action)
                        except AttributeError:
                            pass

            elif (brightness := self._as_brightness(action)) is not None:
                LOG.info("Matched brightness 'set|turn <something> %s' in '%s' as %s",
                         action, words, brightness)
                # This is an exact match
                action_score = 100

                # Only bulbs can do this
                pair = self._find_devices(name, (self._bulbs,))
                if pair is not None:
                    # Pull out the bits
                    (device_score, devices) = pair
                    new_score = (action_score + device_score) / 2 / 100
                    if new_score > score:
                        LOG.debug("New score is %0.2f", new_score)
                        self._update_devices(devices)
                        try:
                            routines = [
                                make_routine(device.set_brightness,
                                             (brightness,))
                                for device in devices
                            ]
                            score = new_score
                            LOG.debug("Created action to set the brightness to %s",
                                      brightness)
                        except AttributeError:
                            pass

            elif (color := COLORS.match(action)) is not None:
                LOG.info("Matched color 'set|turn <something> %s' in '%s' as %s",
                         action, words, color)
                (action_score, (rgb, hsv)) = color

                # Only bulbs can do this
                pair = self._find_devices(name, (self._bulbs,))
                if pair is not None:
                    # Pull out the bits
                    (device_score, devices) = pair
                    new_score = (action_score + device_score) / 2 / 100
                    if new_score > score:
                        LOG.debug("New score is %0.2f", new_score)
                        self._update_devices(devices)
                        try:
                            routines = [
                                make_routine(device.set_hsv, hsv)
                                for device in devices
                            ]
                            score = new_score
                            LOG.debug("Created action to set the HSV to %s", hsv)
                        except AttributeError:
                            pass

        # Now we can give back a handler, if we know what we're doing
        if routines is not None:
            # Compute the combined score, and shift it to be in the
            # range 0..1
            return _KasaHandler(self, tokens, score, routines)
        else:
            return None


    def _find_devices(self, want, device_dicts, threshold=50):
        """
        Look for the devices with the given name and return their objects.

        :return: The ``(score, devices)`` pair.
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


    def _update_devices(self, devices):
        """
        Call update on the device, which might fail.
        """
        for device in devices:
            if device is not None:
                for _ in range(5):
                    try:
                        asyncio.run(device.update())
                    except Exception as e:
                        LOG.warning("Failed to update %s: %s", device, e)


    def _as_brightness(self, word):
        """
        Try to take the given word and turn it into a brightness value.
        """
        # Sanity
        if not isinstance(word, str):
            raise ValueError("Not a string: %s", word)

        # See if it's a number
        if number := parse_number(word) is not None:
            # We will say that the brightness goes from 0 to 10. Only volume
            # goes up to 11.
            return min(100, max(1, int(number) * 10))

        # Look for max and min phrases
        elif word in ('maximum', 'max', 'bright', 'brightest'):
            return 100
        elif word in ('minimum', 'min', 'dim', 'dimmest'):
            return 10

        # No match
        else:
            return None
