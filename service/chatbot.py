"""
Connect to w remote socket and chat.
"""

from   dexter.core      import Notifier
from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz

import socket


class _Handler(Handler):
    """
    The handler for Wikipedia queries.
    """
    def __init__(self, service, tokens, belief, host, port, thing, max_chars):
        """
        @see Handler.__init__()

        :type  thing: str
        :param thing:
            What, or who, is being asked about.
        """
        super().__init__(service, tokens, belief, True)
        self._host      = host
        self._port      = port
        self._thing     = str(thing)
        self._max_chars = max_chars


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            LOG.info("Sending '%s'" % (self._thing,))
            sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sckt.connect((self._host, self._port))
            sckt.sendall(self._thing.encode())
            sckt.send(b'\0')

            LOG.info("Waiting for result...")
            result = b''
            while True:
                got = sckt.recv(1)
                if len(got) == 0 or got == b'\0':
                    break
                result += got
            result = result.decode()
            LOG.info("Got '%s'", result)

            # Trim it, in case it's huge
            result = result[:result[:self._max_chars].rindex('.')+1]
            LOG.info("Trimmed to '%s'", result)

            # And give it back
            return Result(self, result, False, True)

        except Exception as e:
            LOG.error("Failed to send '%s': %s", self._thing, e)
            return Result(
                self,
                "Sorry, there was a problem chatting about %s" % (
                    self._thing,
                ),
                False,
                True
            )
        finally:
            try:
                sckt.close()
            except Exception:
                pass


class ChatService(Service):
    """
    A service which talks to a remote chat bot.
    """
    # Look for these types of queston
    _PREFIXES = ('what is',
                 'whats',
                 "what's",
                 'who is',
                 'tell me')

    def __init__(self,
                 state,
                 host      =None,
                 port      =None,
                 prefixes  =_PREFIXES,
                 max_belief=0.75,
                 max_chars =250):
        """
        @see Service.__init__()
        """
        super().__init__("ChatBot", state)

        if host is None:
            raise ValueError("Not given a host")
        if port is None:
            raise ValueError("Not given a port")

        self._host       = str(host)
        self._port       = int(port)
        self._prefixes   = tuple(prefix.split() for prefix in prefixes)
        self._max_belief = min(1.0, float(max_belief))
        self._max_chars  = int(max_chars)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Render to lower-case, for matching purposes.
        words = self._words(tokens)

        LOG.debug("Matching %s against %s", words, self._prefixes)
        for prefix in self._prefixes:
            try:
                # Look for the prefix in the words
                LOG.debug("Matching %s against %s", words, prefix)
                (start, end, score) = fuzzy_list_range(words, prefix)
                LOG.debug("%s matches %s with from %d to %d with score %d",
                          prefix, words, start, end, score)
                if start == 0:
                    # We always have a capped belief so that other services
                    # which begin with "What's blah blah" can overrule us.
                    thing = ' '.join(words).strip().lower()
                    return _Handler(self,
                                    tokens,
                                    min(self._max_belief, score / 100),
                                    self._host,
                                    self._port,
                                    thing,
                                    self._max_chars)
            except ValueError:
                pass

        # If we got here then it didn't look like a query for us
        return None
