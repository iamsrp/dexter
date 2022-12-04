"""
The heart of the system.
"""

from dexter.core.audio  import get_volume, set_volume
from dexter.core.event  import TimerEvent
from dexter.core.log    import LOG
from dexter.core.util   import (to_alphanumeric,
                                to_letters,
                                list_index,
                                fuzzy_list_range)

from fuzzywuzzy.process import fuzz

import heapq
import queue
import sys
import time
import traceback

# ------------------------------------------------------------------------------

class _Startable(object):
    """
    A class which may be started and stopped.
    """
    def __init__(self):
        super(_Startable, self).__init__()
        self._running  = False


    def start(self):
        """
        Start running.
        """
        if not self._running:
            self._running = True
            self._start()


    def stop(self):
        """
        Stop running.
        """
        self._running = False
        self._stop()


    @property
    def is_running(self):
        """
        Whether we are currently running (i.e. it's been started, and not stopped).
        """
        return self._running


    def _start(self):
        """
        Start the subclass-specific parts.
        """
        pass


    def _stop(self):
        """
        Stop the subclass-specific parts.
        """
        pass


class Component(_Startable):
    """
    A part of the system.

    :type  state: L{State}
    :param state:
        The overall state of the system.
    """
    def __init__(self, state):
        super(Component, self).__init__()
        self._state      = state
        self._status     = None
        self._status_mod = 0


    @property
    def is_input(self):
        """
        Whether this component is an input.
        """
        return False


    @property
    def is_output(self):
        """
        Whether this component is an output.
        """
        return False


    @property
    def is_speech(self):
        """
        Whether this component is an output which delivers speech.
        """
        return False


    @property
    def is_service(self):
        """
        Whether this component is a service.
        """
        return False


    @property
    def status(self):
        """
        Get the status of this component.

        :etype: Notifier._Status
        """
        return self._status


    def interrupt(self):
        """
        Interrupt the component, stopping what it's doing.
        """
        # Not everything will support/need this so we make it a NOP for the
        # general case
        pass


    def _notify(self, status, expected_mod=None):
        """
        Notify of a status change.

        :type  status: Notifier._Status
        :param status:
            The new status of this component.
        :type  expected_mod: int
        :param expected_mod:
            If not ``None``, the expected modification value which the Component
            should have. If this does not match the current modification value
            then no change will be applied.

        :return: The new mod value, or ``None`` if no change was made.
        """
        # If we have a mod-check then perform it
        if expected_mod is not None and expected_mod != self._status_mod:
            return None

        # Good to make the change
        self._status      = status
        self._status_mod += 1
        if self._state is not None:
            self._state.update_status(self, status)

        # Give back the new mod value
        return self._status_mod


    def __str__(self):
        return type(self).__name__


class Notifier(_Startable):
    """
    How a Component tells the system about its status changes.
    """
    class _Status(object):
        def __init__(self, name):
            self._name = name

        def __str__(self):
            return self._name


    INIT    = _Status("<INITIALISING>")
    IDLE    = _Status("<IDLE>")
    ACTIVE  = _Status("<ACTIVE>")
    WORKING = _Status("<WORKING>")


    def update_status(self, component, status):
        """
        Tell the system of a status change for a component.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


    def __str__(self):
        return type(self).__name__


class State(Notifier):
    """
    The global state of the system.
    """
    def is_speaking(self):
        """
        Whether the system is currently outputing audible speech.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")

# ------------------------------------------------------------------------------


class Dexter(object):
    """
    The main class which drives the system.
    """
    class _State(State):
        """
        Tell the system overall that we're busy.
        """
        def __init__(self, notifiers):
            """
            :type  notifiers: list(Notifier)
            :param notifiers:
                The other notifiers that we hold.
            """
            self._notifiers     = tuple(notifiers)
            self._speakers      = set()
            self._last_response = None


        def start(self):
            """
            Start all the notifiers going.
            """
            for notifier in self._notifiers:
                try:
                    LOG.info("Starting %s" % notifier)
                    notifier.start()
                except Exception as e:
                    LOG.error("Failed to start %s: %s" % (notifier, e))


        def stop(self):
            """
            Stop all the notifiers.
            """
            for notifier in self._notifiers:
                try:
                    LOG.info("Stopping %s" % notifier)
                    notifier.stop()
                except Exception as e:
                    LOG.error("Failed to stop %s: %s" % (notifier, e))


        def update_status(self, component, status):
            """
            @see Notifier.update_status()
            """
            # See if this is a speaker, if so then we have to account for that
            if component.is_speech:
                if status in (Notifier.IDLE, Notifier.INIT):
                    if component in self._speakers:
                        self._speakers.remove(component)
                        LOG.info("%s is no longer speaking" % (component,))
                else:
                    self._speakers.add(component)
                    LOG.info("%s is speaking" % (component,))

            # And tell the notifiers
            for notifier in self._notifiers:
                try:
                    notifier.update_status(component, status)
                except Exception as e:
                    LOG.error("Failed to update %s with (%s,%s): %s" %
                              (notifier, component, status, e))


        def is_speaking(self):
            """
            @see State.is_speaking()
            """
            return len(self._speakers) > 0


    # How long to wait for a command after being primed with just the keyphrase
    _KEY_PHRASE_ONLY_TIMEOUT = 10

    # The volume to set to when listening after being prompted by the keyphrase
    _LISTENING_VOLUME = 2


    @staticmethod
    def _get_notifier(full_classname, kwargs):
        """
        The the instance of the given L{Notifier}.

        :type  full_classname: str
        :param full_classname:
            The fully qualified classname, e.g. 'dexter.notifier.TheNotifier'
        :type  kwargs: dict
        :param kwargs:
            The keyword arguments to use when calling the constructor.
        """
        try:
            (module, classname) = full_classname.rsplit('.', 1)
            globals = {}
            exec('from %s import %s'  % (module, classname,), globals)
            exec('klass = %s'         % (        classname,), globals)
            klass = globals['klass']
            if kwargs is None:
                return klass()
            else:
                return klass(**kwargs)

        except Exception as e:
            raise ValueError("Failed to load notifier %s with kwargs %s: %s" %
                             (full_classname, kwargs, e))


    @staticmethod
    def _get_component(full_classname, kwargs, notifier):
        """
        The the instance of the given L{Component}.

        :type  full_classname: str
        :param full_classname:
            The fully qualified classname, e.g. 'dexter,input.AnInput'
        :type  kwargs: dict
        :param kwargs:
            The keyword arguments to use when calling the constructor.
        :type  notifier: L{Notifier}
        :param notifier:
            The notifier for the L{Component}.
        """
        try:
            (module, classname) = full_classname.rsplit('.', 1)
            globals = {}
            exec('from %s import %s'  % (module, classname,), globals)
            exec('klass = %s'         % (        classname,), globals)
            klass = globals['klass']
            if kwargs is None:
                return klass(notifier)
            else:
                return klass(notifier, **kwargs)

        except Exception as e:
            raise ValueError("Failed to load component %s with kwargs %s: %s" %
                             (full_classname, kwargs, e))


    @staticmethod
    def _parse_key_phrase(phrase):
        """
        Turn a string into a tuple, without punctuation, as lowercase.

        :type  phrase: str
        :param phrase:
            The key-phrase to sanitise.
        """
        result = []
        for word in phrase.split(' '):
            # Strip to non-letters and only append if it's not the empty string
            word = to_letters(word)
            if word != '':
                result.append(word.lower())

        # Safe to append
        return tuple(result)


    def __init__(self, config):
        """
        :type  config: configuration
        :param config:
            The configuration for the system.
        """
        # Set up the key-phrases, sanitising them
        self._key_phrases = tuple(Dexter._parse_key_phrase(p)
                                  for p in config['key_phrases'])

        # Create the notifiers
        notifiers = config.get('notifiers', [])
        self._state = Dexter._State(
            Dexter._get_notifier(classname, kwargs)
            for (classname, kwargs) in notifiers
        )

        # Create the components, using our notifier
        components = config.get('components', {})
        self._inputs = [
            Dexter._get_component(classname, kwargs, self._state)
            for (classname, kwargs) in components.get('inputs', [])
        ]
        self._outputs = [
            Dexter._get_component(classname, kwargs, self._state)
            for (classname, kwargs) in components.get('outputs', [])
        ]
        self._services = [
            Dexter._get_component(classname, kwargs, self._state)
            for (classname, kwargs) in components.get('services', [])
        ]

        # When we last heard just the keyphrase on its own, in seconds since
        # epoch
        self._last_keyphrase_only = 0

        # Our events
        self._events       = queue.Queue()
        self._timer_events = []

        # And we're off!
        self._running  = True


    def run(self):
        """
        The main worker.
        """
        LOG.info("Starting the system")
        self._start()

        LOG.info("Entering main loop")
        while self._running:
            try:
                # Handle any events. First check to see if any time events are
                # pending and need to be scheduled.
                LOG.debug("Timer event queue length is %d",
                          len(self._timer_events))
                while len(self._timer_events) > 0 and \
                      self._timer_events[0].schedule_time <= time.time():
                    self._events.put(heapq.heappop(self._timer_events))

                # Now handle the actual events
                while not self._events.empty():
                    event = self._events.get()
                    try:
                        result = event.invoke()
                        if result is not None:
                            self._events.put(result)
                    except Exception as e:
                        LOG.error("Event %s raised exception: %s", event, e)

                # Loop over all the inputs and see if they have anything pending
                for input in self._inputs:
                    # Attempt a read, this will return None if there's nothing
                    # available
                    tokens = input.read()
                    if tokens is not None:
                        # Okay, we read something, attempt to handle it
                        LOG.info("Read from %s: %s" %
                                 (input, [str(t) for t in tokens]))
                        result = self._handle(tokens)

                        # If we got something back then give it back to the user
                        if result is not None:
                            # Send it to the outputs
                            self._respond(result)

                            # And remember what was said in case the user asks
                            # for it to be repeated. We remember when we said it
                            # so that someone doesn't come along much later and
                            # ask for a repeat (which would be sketchy).
                            self._last_response = (time.time(), result)

                # Wait for a bit before going around again
                time.sleep(0.1)

            except KeyboardInterrupt:
                LOG.warning("KeyboardInterrupt received")
                break

        # We're out of the main loop, shut things down
        LOG.info("Stopping the system")
        self._stop()


    def _start(self):
        """
        Start the system going.
        """
        # Start the notifiers
        try:
            self._state.start()
        except Exception as e:
            LOG.fatal("Failed to start notifiers: %s" % (e,))
            sys.exit(1)

        # And the components
        for component in self._inputs + self._outputs + self._services:
            # If these throw then it's fatal
            LOG.info("Starting %s" % (component,))
            try:
                component.start()
            except Exception as e:
                LOG.fatal("Failed to start %s: %s" % (component, e))
                sys.exit(1)


    def _stop(self):
        """
        Stop the system.
        """
        # Stop the notifiers
        self._state.stop()

        # And the components
        for component in self._inputs + self._outputs + self._services:
            # Best effort, since we're likely shutting down
            try:
                LOG.info("Stopping %s" % (component,))
                component.stop()

            except Exception as e:
                LOG.error("Failed to stop %s: %$s" % (component, e))


    def _handle(self, tokens):
        """
        Handle a list of L{Token}s from the input.

        :type  tokens: list(L{Token})
        :param tokens:
            The tokens to handle.

        :rtype: str
        :return:
            The textual response, if any.
        """
        # Give back nothing if we have no tokens
        if tokens is None:
            return None

        # Get the words from this text, these could include numeric values
        words = [to_alphanumeric(token.element).lower()
                 for token in tokens
                 if token.verbal]
        LOG.info("Handling: \"%s\"" % ' '.join(words))

        # Anything?
        if len(words) == 0:
            LOG.info("Nothing to do")
            return None
            

        # See if the key-phrase is in the tokens and use it to determine the
        # offset of the command.
        offset = None
        for key_phrase in self._key_phrases:
            try:
                offset = (list_index(words, key_phrase) +
                          len(key_phrase))
                LOG.info("Found key-phrase %s at offset %d in %s" %
                         (key_phrase, offset - len(key_phrase), words))
            except ValueError:
                pass

        # If we don't have an offset then we haven't found a key-phrase. Try a
        # fuzzy match, but only if we are not waiting for someone to say
        # something after priming with the keypharse.
        now = time.time()
        if now - self._last_keyphrase_only < Dexter._KEY_PHRASE_ONLY_TIMEOUT:
            # Okay, treat what we got as the command, so we have no keypharse
            # and so the offset is zero.
            LOG.info("Treating %s as a command", (words,))
            offset = 0
        elif offset is None:
            # Not found, but if we got something which sounded like the key
            # phrase then set the offset this way too. This allows someone to
            # just say the keyphrase and we can handle it by waiting for them to
            # then say something else.
            LOG.info("Key pharses %s not found in %s" %
                     (self._key_phrases, words))

            # Check for it being _almost_ the key phrase
            ratio = 75
            what = ' '.join(words)
            for key_phrase in self._key_phrases:
                if fuzz.ratio(' '.join(key_phrase), what) > ratio:
                    offset = len(key_phrase)
                    LOG.info("Fuzzy-matched key-pharse %s in %s" %
                             (key_phrase, words))

        # Anything?
        if offset is None:
            return None

        # If we have the keyphrase and no more then we just got a priming
        # command, we should be ready for the rest of it to follow
        if offset == len(words):
            # Remember that we were primed
            LOG.info("Just got keyphrase")
            self._last_keyphrase_only = now

            # To drop the volume down so that we can hear what's coming. We'll
            # need a capturing function to do this.
            def make_fn(v):
                def fn():
                    set_volume(v)
                    return None
                return fn

            try:
                # Get the current volume
                volume = get_volume()

                # If the volume is too high then we will need to lower it
                if volume > Dexter._LISTENING_VOLUME:
                    # And schedule an event to bump it back up in a little while
                    LOG.info(
                        "Lowering volume from %d to %d while we wait for more",
                        volume, Dexter._LISTENING_VOLUME
                    )
                    set_volume(Dexter._LISTENING_VOLUME)
                    heapq.heappush(
                        self._timer_events,
                        TimerEvent(
                            now + Dexter._KEY_PHRASE_ONLY_TIMEOUT,
                            runnable=make_fn(volume)
                        )
                    )
            except Exception as e:
                LOG.warning("Failed to set listening volume: %s", e)

            # Nothing more to do until we hear the rest of the command
            return None

        # Special handling if we have active outputs and someone said "stop"
        if offset == len(words) - 1 and words[-1] == "stop":
            stopped = False
            for component in  self._inputs + self._outputs + self._services:
                # If this component is busy doing something then we tell it to stop
                # doing that thing with interrupt(). (stop() means shutdown.)
                if component.status in (Notifier.ACTIVE, Notifier.WORKING):
                    try:
                        # Best effort
                        LOG.info("Interrupting %s", component)
                        component.interrupt()
                        stopped = True
                    except:
                        pass

            # If we managed to stop one of the output components then we're
            # done. We don't want another component to pick up this command.
            if stopped:
                return None

        # See if we've been asked to repeat what was just said
        for phrase in (('what', 'did', 'you', 'say'),
                       ('say', 'that', 'again'),
                       ('repeat', 'that')):
            try:
                (start, end, score) = fuzzy_list_range(words[offset:], phrase)
                if start == 0 and end >= len(words[offset:]):
                    # See if we have something recent. Don't repeat things from
                    # more than a minute ago since that seems a little sketchy.
                    if (self._last_response is None or
                        self._last_response[0] < time.time() - 60):
                        return "I don't remember what I just said"
                    else:
                        return self._last_response[1]
            except ValueError:
                # No match
                LOG.debug("No match for %s with %s", words[offset:], phrase)

        # See which services want them
        handlers = []
        for service in self._services:
            try:
                # This service is being woken to so update the status
                self._state.update_status(service, Notifier.ACTIVE)

                # Get any handler from the service for the given tokens
                handler = service.evaluate(tokens[offset:])
                if handler is not None:
                    LOG.info("Service %s yields handler %s", service, handler)
                    handlers.append(handler)

            except:
                LOG.error("Failed to evaluate %s with %s:\n%s" %
                          ([str(token) for token in tokens],
                           service,
                           traceback.format_exc()))
                return "Sorry, there was a problem"

            finally:
                # This service is done working now
                self._state.update_status(service, Notifier.IDLE)

        # Anything?
        if len(handlers) == 0:
            return "I'm sorry, I don't know how to help with that"

        # Okay, put the handlers into order of belief and try them. Notice that
        # we want the higher beliefs first so we reverse the sign in the key.
        handlers = sorted(handlers, key=lambda h: -h.belief)
        LOG.info("Handlers matched: %s", ', '.join(str(h) for h in handlers))

        # If any of the handlers have marked themselves as exclusive then we
        # restrict the list to just them. Hopefully there will be just one but,
        # if there are more, then they should be in the order of belief so we'll
        # pick the "best" exclusive one first.
        if True in [h.exclusive for h in handlers]:
            handlers = [h
                        for h in handlers
                        if h.exclusive]

        # Now try each of the handlers
        response      = []
        error_service = None
        for handler in handlers:
            try:
                # Update the status of this handler's service to "working" while
                # we call it
                self._state.update_status(handler.service,
                                          Notifier.WORKING)

                # Invoked the handler and see what we get back
                result = handler.handle()
                if result is None:
                    continue

                # Accumulate into the resultant text
                if result.text is not None:
                    response.append(result.text)

                # Stop here?
                if handler.exclusive or result.exclusive:
                    break

            except:
                error_service = handler.service
                LOG.error(
                    "Handler %s with tokens %s for service %s yielded:\n%s" %
                    (handler,
                     [str(t) for t in handler.tokens],
                     handler.service,
                     traceback.format_exc())
                )

            finally:
                # This service is done working now
                self._state.update_status(handler.service,
                                          Notifier.IDLE)

        # Give back whatever we had, if anything
        if error_service:
            return "Sorry, there was a problem with %s" % (error_service,)
        elif len(response) > 0:
            return '\n'.join(response)
        else:
            return None


    def _respond(self, response):
        """
        Given back the response to the user via the outputs.

        :type  response: str
        :param response:
            The text to send off to the user in the real world.
        """
        # Give back nothing if we have no response
        if response is None:
            return None

        # Simply hand it to all the outputs
        for output in self._outputs:
            try:
                output.write(response)
            except:
                LOG.error("Failed to respond with %s:\n%s" %
                (output, traceback.format_exc()))
