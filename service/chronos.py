"""
Chronos, the greek god of Thyme, and other select herbs.

Various services related to the ticking of the clock.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import (fuzzy_list_range,
                                number_to_words,
                                parse_number,
                                to_letters)
from   dexter.service   import Service, Handler, Result
from   threading        import Thread

import pyaudio
import time
import traceback
import wave

# ------------------------------------------------------------------------------

# All the time units which we know about. The number of seconds in a month or
# eon is ambiguously defined so we pick something reasonable. We don't handle
# anything below a second.
#             PLURAL        SINGULAR      NUMBER OF SECONDS
_PERIODS = ((('eons',       'eon'      ), 1000000000 * 365.24 * 24 * 60 * 60),
            (('millenia',   'millenium'),       1000 * 365.24 * 24 * 60 * 60),
            (('centuries',  'century'  ),        100 * 365.24 * 24 * 60 * 60),
            (('decades',    'decade'   ),         10 * 365.24 * 24 * 60 * 60),
            (('years',      'year'     ),          1 * 365.24 * 24 * 60 * 60),
            (('months',     'month'    ),                  30 * 24 * 60 * 60),
            (('fortnights', 'fortnight'),                  14 * 24 * 60 * 60),
            (('weeks',      'week'     ),                   7 * 24 * 60 * 60),
            (('days',       'day'      ),                       24 * 60 * 60),
            (('hours',      'hour'     ),                            60 * 60),
            (('minutes',    'minute'   ),                                 60),
            (('seconds',    'second'   ),                                  1),)

# ------------------------------------------------------------------------------

class _ClockHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_ClockHandler, self).__init__(service, tokens, 1.0, True)


    def handle(self):
        """
        @see Handler.handle()
        """
        # Get the time in the local timezone and render the component parts that
        # we care about
        now = time.localtime(time.time())
        hh  = time.strftime("%I", now)
        mm  = time.strftime("%M", now)
        p   = time.strftime("%p", now)

        # We strip any leading zero from the HH, which you expect for a HH:MM
        # format. For MM we replace it with 'oh' for a more natural response.
        if hh.startswith('0'):
            hh = hh.lstrip('0')
        hh = number_to_words(int(hh))
        if mm == '00':
            mm = ''
        elif mm.startswith('0'):
            mm = 'oh %s' % number_to_words(int(mm))
        else:
            mm = number_to_words(int(mm))

        # Now we can hand it back
        return Result(
            self,
            "The current time is %s %s %s" % (hh, mm, p),
            False,
            True
        )


class ClockService(Service):
    """
    A service which tells the time.

    >>> from dexter.test import NOTIFIER, tokenise
    >>> s = ClockService(NOTIFIER)
    >>> handler = s.evaluate(tokenise('What\\'s the time?'))
    >>> result = handler.handle()
    >>> result.text.startswith('The current time is')
    True
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(ClockService, self).__init__("Clock", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Look to match what we were given on a number of different phrasings
        words = self._words(tokens)
        for want in (('whats', 'the', 'time'),
                     ('what', 'is', 'the', 'time'),
                     ('what', 'time', 'is', 'it')):
            try:
                # Match the different pharses on the input
                (start, end, score) = fuzzy_list_range(words, want)

                # We want to match the full input, since we want to avoid people
                # asking for the time with caveats
                if start == 0 and end == len(words):
                    LOG.info("Matched '%s' on '%s'" % (want, words))
                    return _ClockHandler(self, tokens)
            except ValueError:
                pass

        return None

# ------------------------------------------------------------------------------

class _SetTimerHandler(Handler):
    def __init__(self, service, tokens, times):
        """
        @see Handler.__init__()
        """
        super(_SetTimerHandler, self).__init__(service, tokens, 1.0, True)
        self._times = times


    def handle(self):
        """
        @see Handler.handle()
        """
        # If we got nothing then grumble in a vaguely (un)helpful way
        if len(self._times) == 0:
            return Result(
                self,
                "I'm sorry, I didn't catch that",
                False,
                True
            )

        # Look for the times in the words
        try:
            # Try to find the various units of time in something like:
            #   seven hours and fifteen days
            indices = []
            for (words, seconds) in _PERIODS:
                for word in words:
                    if word in self._times:
                        index = self._times.index(word)
                        LOG.info("Found '%s' at index %d" % (word, index))
                        indices.append((index, seconds))

            # Anything?
            if len(indices) == 0:
                raise ValueError("Found no units in %s" % ' '.join(self._times))

            # Put them in order and look for the numbers, accumulating into the
            # total
            total = 0
            indices = sorted(indices, key=lambda pair: pair[0])
            prev = 0
            for (index, seconds) in indices:
                # Get the words leading up to the time unit, these should be the
                # number (possibly with other bits)
                value = self._times[prev:index]

                # Strip off any "and"s
                while value[0] == "and":
                    value = value[1:]

                # Now try to parse it
                LOG.info("Parsing %s" % (value,))
                amount = parse_number(' '.join(value))

                # Accumulate
                total = amount * seconds

            LOG.info("Got value of %s seconds from %s" % (total, self._times))

            # Handle accordingly
            if total > 0:
                # That's a valid timer value. Set the timer and say we did it.
                self.service.add_timer(total)
                return Result(
                    self,
                    "Okay, timer set for %s" % (' '.join(self._times),),
                    False,
                    True
                )
            else:
                # We can't have an alarm in the past
                return Result(
                    self,
                    "%s was not a time in the future" %
                    (' '.join(self._times),),
                    False,
                    True
                )

        except Exception:
            LOG.error("Problem parsing timer '%s':\n%s" %
                      (self._timer, traceback.format_exc()))
            return Result(
                self,
                "Sorry, I don't know how to set the timer for %s" %
                (' '.join(self._times),),
                False,
                True
            )


class _CancelHandler(Handler):
    def __init__(self, service, tokens, words):
        """
        @see Handler.__init__()
        """
        super(_CancelHandler, self).__init__(service, tokens, 1.0, False)
        self._words = words


    def handle(self):
        """
        @see Handler.handle()
        """
        # Just cancel them all for now
        try:
            self.service.cancel_timer()
            return Result(
                self,
                "All timers cancelled",
                False,
                True
            )
        except Exception as e:
            return Result(
                self,
                "Sorry, I don't know how to cancel that timer",
                False,
                True
            )


class Timer(object):
    """
    A timer.
    """
    def __init__(self, service, seconds):
        self._service   = service
        self._seconds   = seconds
        self._when      = time.time() + seconds
        self._cancelled = False


    def start(self):
        """
        Start this timer.
        """
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


    def cancel(self):
        """
        Cancel this timer.
        """
        self._cancelled = True


    def _run(self):
        """
        How we run.
        """
        while not self._cancelled:
            if time.time() > self._when:
                self._service.sound_alarm(self)
                break
            time.sleep(0.1)


    def __str__(self):
        return "Timer for %d seconds" % self._seconds


class TimerService(Service):
    """
    A service for setting timers and alarms.
    """
    def __init__(self, state, timer_wave=None):
        """
        @see Service.__init__()
        """
        super(TimerService, self).__init__("Timer", state)

        self._timers  = []
        self._pyaudio = pyaudio.PyAudio()

        if timer_wave is not None:
            with wave.open(timer_wave, 'rb') as wf:
                self._timer_audio = {
                    'channels' : wf.getnchannels(),
                    'width'    : wf.getsampwidth(),
                    'rate'     : wf.getframerate(),
                    'data'     : wf.readframes(-1)
                }
        else:
            self._timer_audio = None


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # We use a number of different prefices here since the word "for" has a
        # homonyms of "four" and "set" apparently sounds like "said". Yes, I
        # know I could do a cross product here but...
        words  = self._words(tokens)
        phrase = ('set', 'a', 'timer', 'for')
        try:
            (start, end, score) = fuzzy_list_range(words, phrase)
            return _SetTimerHandler(self, tokens, words[end:])
        except Exception as e:
            pass

        # And now for cancelling
        phrase = ('cancel', 'timer')
        try:
            index = fuzzy_list_range(words, prefix)
            return _CancelHandler(self, tokens, words)
        except Exception as e:
            pass

        # Didn't find any of the prefices
        return None


    def add_timer(self, seconds):
        """
        Set a timer for the given number of seconds and set it running.
        """
        timer = Timer(self, seconds)
        self._timers.append(timer)
        timer.start()


    def cancel_timer(self, which=None):
        """
        Cancel a timer, possibly all of them
        """
        if which is None:
            for timer in self._timers:
                timer.cancel
            self._timers = []
        elif 0 <= which < len(self._timers):
            timer = self._timers[which]
            timer.cancel()
            self._timers.remove(timer)
        else:
            raise ValueError("No timer for index %d" % (which,))


    def sound_alarm(self, timer):
        """
        Ring the alarm for the given timer.
        """
        # Let the terminal know
        LOG.info("DING DING DING!!! Timer %s has expired..." % (timer,))

        # Play any sound...
        if self._timer_audio is not None:
            # ...for about 5 seconds
            end = time.time() + 5
            while time.time() < end:
                try:
                    stream = self._pyaudio.open(
                        format  =self._pyaudio.get_format_from_width(
                            self._timer_audio['width']
                        ),
                        channels=self._timer_audio['channels'],
                        rate    =self._timer_audio['rate'],
                        output  =True
                    )
                    stream.write(self._timer_audio['data'])
                    stream.close()
                except Exception as e:
                    LOG.warning("Failed to play timer sound: %s" % e)

        # And remove the timer (this should not fail but...)
        try:
            self._timers.remove(timer)
        except:
            pass
