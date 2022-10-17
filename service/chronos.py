"""
Chronos, the greek god of Thyme, and other select herbs.

Various services related to the ticking of the clock.
"""

from   datetime         import datetime
from   dexter.core.log  import LOG
from   dexter.core.util import (fuzzy_list_range,
                                get_pygame,
                                number_to_words,
                                parse_number,
                                to_alphanumeric,
                                to_letters)
from   dexter.service   import Service, Handler, Result
from   random           import random
from   threading        import Thread

import time
import traceback

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
    def __init__(self, service, tokens, what, easter_egg_prob):
        """
        @see Handler.__init__()

        :param easter_egg_prob: The probability of whether to have snarky
                                comments as potential replies.
        """
        super(_ClockHandler, self).__init__(service, tokens, 1.0, True)
        self._what = what
        self._easter_egg_prob = easter_egg_prob


    def handle(self):
        """
        @see Handler.handle()
        """
        # See if we need to do an easter egg
        if random() < self._easter_egg_prob:
            # Yes!
            choice = int(random() * 2)
            if choice == 0:
                result = "Time you got a watch"
            elif choice == 1:
                result = "Time is an illusion"
            else:
                result = "Sorry, I don't want to tell you"
        else:
            # Get the time in the local timezone and render the component parts that
            # we care about
            now = time.localtime(time.time())

            if self._what == "time":
                hh  = time.strftime("%I", now)
                mm  = time.strftime("%M", now)
                p   = time.strftime("%p", now)
    
                # We strip any leading zero from the HH, which you expect for a HH:MM
                # format. For MM we replace it with 'oh' for a more natural response. AM
                # and PM need to be spelt out so that speech output doesn't say "am" (as
                # in "I am he!") instead of "ay em".
                if hh.startswith('0'):
                    hh = hh.lstrip('0')
                hh = number_to_words(int(hh))
                if mm == '00':
                    mm = ''
                elif mm.startswith('0'):
                    mm = 'oh %s' % number_to_words(int(mm))
                else:
                    mm = number_to_words(int(mm))
                if p == "AM":
                    p = "ay em"
                elif p == "PM":
                    p = "pee em"
                result = "The current time is %s %s %s" % (hh, mm, p)

            elif self._what == "date":
                # Get the parts
                day   = time.strftime("%A", now)
                month = time.strftime("%B", now)
                dom   = time.strftime("%d", now)
                year  = time.strftime("%Y", now)

                # Append a 'st', 'nd', 'rd', 'th' to the day
                if   dom.endswith('1') and dom != '11':
                    dom += 'st'
                elif dom.endswith('2') and dom != '12':
                    dom += 'nd'
                elif dom.endswith('3') and dom != '13':
                    dom += 'rd'
                else:
                    dom += 'th'
    
                result = "The date is %s %s %s %s" % (day, month, dom, year)

            else:
                result = "I'm sorry, I don't know what the %s is" % (self._what)

        # Now we can hand it back
        return Result(self, result, False, True)


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
    def __init__(self,
                 state,
                 easter_egg_prob=0.0):
        """
        @see Service.__init__()

        :param easter_egg_prob: The probability of whether to have snarky
                                comments as potential replies.
        """
        super(ClockService, self).__init__("Clock", state)
        self._easter_egg_prob = max(0.0, min(1.0, float(easter_egg_prob)))


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Look to match what we were given on a number of different phrasings
        words = self._words(tokens)
        handler = None
        score   = 0
        for what in ('time', 'date'):
            for want in (('whats', 'the', what),
                         ('what', 'is', 'the', what),
                         ('what', what, 'is', 'it')):
                try:
                    # Match the different pharses on the input
                    (start, end, score_) = fuzzy_list_range(words, want)
    
                    # We want to match the full input, since we want to avoid people
                    # asking for the time with caveats
                    if start == 0 and end == len(words) and score_ > score:
                        score = score_
                        LOG.info("Matched '%s' on '%s' with score %d",
                                 want, words, score_)
                        handler = _ClockHandler(self,
                                                tokens,
                                                what,
                                                self._easter_egg_prob)
                except ValueError:
                    pass

        # Give back what we had, if anything
        return handler

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

                # Now try to turn it into a value
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
                      (self._times, traceback.format_exc()))
            return Result(
                self,
                "Sorry, I don't know how to set the timer for %s" %
                (' '.join(self._times),),
                False,
                True
            )


class _CancelTimerHandler(Handler):
    def __init__(self, service, tokens, words):
        """
        @see Handler.__init__()
        """
        super(_CancelTimerHandler, self).__init__(service, tokens, 1.0, True)
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


    def cancel(self):
        """
        Cancel this timer.
        """
        self._cancelled = True


    def start(self):
        """
        Start this timer.
        """
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


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
    def __init__(self, state, timer_sound=None):
        """
        @see Service.__init__()

        :type  timer_sound: str
        :param timer_sound:
            The path to the sound to play when the timer goes off.
        """
        super(TimerService, self).__init__("Timer", state)

        self._timers  = []

        if timer_sound is not None:
            self._timer_audio = get_pygame().mixer.Sound(timer_sound)
        else:
            self._timer_audio = None


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # We use a number of different prefices here since the word "for" has a
        # homonyms of "four" and "set" apparently sounds like "said". Yes, I
        # know I could do a cross product here but...
        words  = tuple(to_alphanumeric(word)
                       for word in self._words(tokens))
        phrase = ('set', 'a', 'timer', 'for')
        try:
            (start, end, score) = fuzzy_list_range(words, phrase)
            return _SetTimerHandler(self, tokens, words[end:])
        except Exception as e:
            pass

        # And now for cancelling
        phrase = ('cancel', 'timer')
        try:
            index = fuzzy_list_range(words, phrase)
            return _CancelTimerHandler(self, tokens, words)
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
        LOG.info("DING DING DING!!! Timer '%s' has expired..." % (timer,))

        # Play any sound...
        if self._timer_audio is not None:
            LOG.info("Playing timer sound")

            # ...for about 5 seconds
            end = time.time() + 5
            while time.time() < end:
                try:
                    self._timer_audio.play()
                except Exception as e:
                    LOG.warning("Failed to play timer sound: %s", e)

        # And remove the timer (this should not fail but...)
        try:
            self._timers.remove(timer)
        except:
            pass

# ------------------------------------------------------------------------------

class _SetAlarmHandler(Handler):
    def __init__(self, service, tokens, timespec):
        """
        @see Handler.__init__()
        """
        super(_SetAlarmHandler, self).__init__(service, tokens, 1.0, True)
        self._timespec = timespec


    def handle(self):
        """
        @see Handler.handle()
        """
        # If we got nothing then grumble in a vaguely (un)helpful way
        LOG.info("Parsing timespec: %s", self._timespec)
        timespec = list(self._timespec)
        if len(timespec) == 0:
            return Result(
                self,
                "I'm sorry, I didn't catch that",
                False,
                True
            )

        # Figure out the date today
        now = datetime.now()

        # See if it ends with "tomorrow" or "today"
        day_offset = 0
        dayspec   = ""
        if timespec[-1] == "today":
            # Just strip it
            timespec = timespec[:-1]
        elif timespec[-1] == "tomorrow":
            # Add an offset and strip it
            day_offset = 1
            timespec = timespec[:-1]
            dayspec  = "tomorrow"

        # Attempt to turn the time specification into seconds-since-epoch
        seconds = None
        try:
            # Try a few different formats to determine the time given, trh the
            # following formats:
            #   4 o'clock
            #   4 pm
            #   4 32 pm
            if timespec[-1] == "oclock":
                # Two choices, pick the one closest to now, which could be
                # tomorrow morning
                LOG.info("Parsing X o'clock time")
                hh_am = parse_number(timespec[-2])
                hh_pm = hh_am + 12
                dt_am = datetime(now.year, now.month, now.day, hh_am, 0)
                dt_pm = datetime(now.year, now.month, now.day, hh_pm, 0)
                if day_offset == 0:
                    if dt_am > now:
                        seconds = dt_am.timestamp()
                    elif dt_pm > now:
                        seconds = dt_pm.timestamp()
                    else:
                        seconds = dt_am.timestamp() + 24 * 60 * 60
                        dayspec = "tomorrow"
                else:
                    seconds = dt_am.timestamp() + 24 * 60 * 60 * day_offset

            elif timespec[-1].endswith('am') or timespec[-1].endswith('pm'):
                LOG.info("Parsing X am/pm time")

                # First handle "815pm"
                if len(timespec[-1]) > 2:
                    timespec = timespec[:-1] + [timespec[-1][:-2],
                                                timespec[-1][-2:]]

                # Might have a minutes value or not
                LOG.info("Parsing %s", timespec)
                mm = 0
                if len(timespec) == 2: # "4 pm" or "432 pm"
                    hh = parse_number(timespec[0])
                    # See if it's 432 pm
                    if hh >= 100:
                        (hh, mm) = divmod(hh, 100)
                elif len(timespec) == 3: # "4 32 pm"
                    hh = parse_number(timespec[0])
                    mm = parse_number(timespec[1])
                if timespec[-1] == 'pm':
                    hh += 12

                # Now construct the time
                dt = datetime(now.year, now.month, now.day, hh, mm)

                # And adjust
                if day_offset > 0:
                    seconds = dt.timestamp() + 24 * 60 * 60 * day_offset
                elif dt < now:
                    seconds = dt.timestamp() + 24 * 60 * 60
                    dayspec = "tomorrow"
                else:
                    seconds = dt.timestamp()

            elif len(timespec) == 1 or len(timespec) == 2:
                LOG.info("Parsing raw time")

                # Expect 4 or 4 32
                mm = 0
                if len(timespec) == 1: # "4" or "432"
                    hh = parse_number(timespec[0])
                    # See if it's 432 pm
                    if hh >= 100:
                        (hh, mm) = divmod(hh, 100)
                else: # 4 43
                    hh = parse_number(timespec[0])
                    mm = parse_number(timespec[1])

                # Same logic as above
                dt_am = datetime(now.year, now.month, now.day, hh,      mm)
                dt_pm = datetime(now.year, now.month, now.day, hh + 12, mm)
                if day_offset == 0:
                    if dt_am > now:
                        seconds = dt_am.timestamp()
                    elif dt_pm > now:
                        seconds = dt_pm.timestamp()
                    else:
                        seconds = dt_am.timestamp() + 24 * 60 * 60
                        dayspec = "tomorrow"
                else:
                    seconds = dt_am.timestamp() + 24 * 60 * 60 * day_offset

            # Handle accordingly
            LOG.info("Seconds value was %s", seconds)
            if seconds is not None:
                # As words
                dt = datetime.fromtimestamp(seconds)
                hh = dt.strftime('%I').lstrip('0')
                mm = dt.strftime('%M')
                if mm == '00':
                    mm = ''
                elif mm[0] == '0':
                    mm = 'oh %s' % mm[1]
                description = (
                    "%s %s %s %s" % (
                        hh,
                        mm,
                        dt.strftime('%p'),
                        dayspec
                    )
                ).strip()
                LOG.info("Got value of %s from %s" % (description, self._timespec))

                # That's a valid alarm value. Set the alarm and say we did it.
                self.service.add_alarm(seconds)
                return Result(
                    self,
                    "Okay, alarm set for %s" % description,
                    False,
                    True
                )

        except Exception:
            LOG.error("Problem parsing alarm '%s':\n%s" %
                      (self._timespec, traceback.format_exc()))

        # If we got here then we failed
        return Result(
            self,
            "Sorry, I don't know how to set an alarm for %s" %
            (' '.join(self._timespec),),
            False,
            True
        )


class _CancelAlarmHandler(Handler):
    def __init__(self, service, tokens, words):
        """
        @see Handler.__init__()
        """
        super(_CancelAlarmHandler, self).__init__(service, tokens, 1.0, True)
        self._words = words


    def handle(self):
        """
        @see Handler.handle()
        """
        # Just cancel them all for now
        try:
            self.service.cancel_alarm()
            return Result(
                self,
                "All alarms cancelled",
                False,
                True
            )
        except ValueError as e:
            return Result(self, str(e), False, True)
        except Exception as e:
            return Result(
                self,
                "Sorry, I don't know how to cancel that alarm",
                False,
                True
            )


class Alarm(object):
    """
    An alarm.
    """
    def __init__(self, service, when):
        self._service   = service
        self._when      = when
        self._cancelled = False


    def cancel(self):
        """
        Cancel this alarm.
        """
        self._cancelled = True


    def start(self):
        """
        Start this alarm.
        """
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


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
        dt = datetime.fromtimestamp(self._when)
        return "Alarm for %s" % (dt.strftime('%Y-%m-%d %H:%M'),)


class AlarmService(Service):
    """
    A service for setting alarms and alarms.
    """
    def __init__(self, state, alarm_sound=None):
        """
        @see Service.__init__()

        :type  alarm_sound: str
        :param alarm_sound:
            The path to the sound to play when the alarm goes off.
        """
        super(AlarmService, self).__init__("Alarm", state)

        self._alarms  = []

        if alarm_sound is not None:
            self._alarm_audio = get_pygame().mixer.Sound(alarm_sound)
        else:
            self._alarm_audio = None


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # We use a number of different prefices here since the word "for" has a
        # homonyms of "four" and "set" apparently sounds like "said". Yes, I
        # know I could do a cross product here but...
        words  = self._words(tokens)
        phrase = ('set', 'an', 'alarm', 'for')
        try:
            # Attempt to match
            (start, end, score) = fuzzy_list_range(words, phrase)

            # We need to handle the STT giving us "3:32" or "3.32" instead of "3 32"
            words = words[end:]
            for char in ':.':
                new_words = []
                for word in words:
                    for w in word.split(char):
                        if len(w):
                            new_words.append(w)
                words = new_words

            # Now ensure the values are alphanumerical
            words = tuple(to_alphanumeric(word)
                          for word in words)

            # And we can hand them off
            return _SetAlarmHandler(self, tokens, words)

        except Exception as e:
            pass

        # And now for cancelling
        phrase = ('cancel', 'alarm')
        try:
            index = fuzzy_list_range(words, phrase)
            return _CancelAlarmHandler(self, tokens, words)
        except Exception as e:
            LOG.info("Didn't match on %s: %s", phrase, e)
            pass

        # Didn't find any of the prefices
        return None


    def add_alarm(self, when):
        """
        Set an alarm for the given number of seconds since epoch.
        """
        alarm = Alarm(self, when)
        self._alarms.append(alarm)
        alarm.start()


    def cancel_alarm(self, which=None):
        """
        Cancel an alarm, possibly all of them
        """
        if which is None:
            if len(self._alarms) == 0:
                raise ValueError("No alarms are set")
            for alarm in self._alarms:
                alarm.cancel
            self._alarms = []
        elif 0 <= which < len(self._alarms):
            alarm = self._alarms[which]
            alarm.cancel()
            self._alarms.remove(alarm)
        else:
            raise ValueError("No alarm for index %d" % (which,))


    def sound_alarm(self, alarm):
        """
        Ring the alarm for the given alarm.
        """
        # Let the terminal know
        LOG.info("DING DING DING!!! Alarm '%s' is ringing..." % (alarm,))

        # Play any sound...
        if self._alarm_audio is not None:
            LOG.info("Playing alarm sound")

            # ...for about 5 seconds
            end = time.time() + 5
            while time.time() < end:
                try:
                    self._alarm_audio.play()
                except Exception as e:
                    LOG.warning("Failed to play alarm sound: %s", e)

        # And remove the alarm (this should not fail but...)
        try:
            self._alarms.remove(alarm)
        except:
            pass
