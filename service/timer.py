"""
Simple timer service, for setting a timer!
"""

import pyaudio
import time
import traceback
import wave

from   dexter.core.log   import LOG
from   dexter.core.util  import list_index, parse_number
from   dexter.service    import Service, Handler, Result
from   threading         import Thread

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


class _SetHandler(Handler):
    def __init__(self, service, tokens, times):
        """
        @see Handler.__init__()
        """
        super(_SetHandler, self).__init__(service, tokens, 1.0, True)
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
        words    = self._words(tokens)
        prefices = (('set',  'a', 'timer', 'for' ),
                    ('set',  'a', 'timer', 'four'),
                    ('said', 'a', 'timer', 'for' ),
                    ('said', 'a', 'timer', 'four'),
                    ('set',  'a', 'time',  'for' ),
                    ('set',  'a', 'time',  'four'),
                    ('said', 'a', 'time',  'for' ),
                    ('said', 'a', 'time',  'four'),)
        for prefix in prefices:
            try:
                index = list_index(words, prefix)
                return _SetHandler(self,
                                   tokens,
                                   words[index + len(prefix):])
            except Exception as e:
                pass

        # And now for cancelling
        prefices = (('counsel', 'timers' ),
                    ('counsel', 'timer'  ),
                    ('counsel', 'time'   ),
                    ('cancel',  'timers' ),
                    ('cancel',  'timer'  ),
                    ('cancel',  'time'   ),)
        for prefix in prefices:
            try:
                index = list_index(words, prefix)
                return _CancelHandler(self,
                                      tokens,
                                      words)
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
