"""
Services which get the weather.
"""

from   datetime         import date, timedelta
from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range, parse_number
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz
from   urllib.request   import Request, urlopen

import json

_HEADERS = {'User-Agent': 'Mozilla/5.0'}

class _UsHandler(Handler):
    """
    Get the weather from weather.gov via there RESTful API.
    """
    def __init__(self, service, tokens, words, start, end, coordinates):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, True)

        # The stuff after the end of the match is the day specifier (we hope)
        if end < len(words):
            self._when = words[end]
        else:
            self._when = None

        # See https://www.weather.gov/documentation/services-web-api
        self._url = f'https://api.weather.gov/points/{coordinates}'


    def handle(self):
        """
        @see Handler.handle()
        """
        # Start with the main URL request
        request = Request(self._url,
                          headers=_HEADERS)
        with urlopen(request) as handle:
            data = json.loads(''.join(l.decode('ASCII')
                                      for l in handle.readlines()))

        # Inside that there should be a "forecast" URL which we can read
        request = Request(data['properties']['forecast'],
                          headers=_HEADERS)
        with urlopen(request) as handle:
            fc_data = json.loads(''.join(l.decode('ASCII')
                                         for l in handle.readlines()))

        # The data comes in a number of periods
        periods = fc_data['properties']['periods']
        
        # Let's just choose the first for now. The name is the name of the
        # period, the first is "tonight" or "today" etc. but later ones are
        # names of days etc.
        which = 0
        if self._when is not None:
            LOG.info("Handling a 'when' of '%s'", self._when)
            if fuzz.ratio('tomorrow', self._when) > 75:
                # Tomorrow is today + 1day
                LOG.info("Matched as tomorrow")
                when = (date.today() + timedelta(days=1)).strftime('%A')
            else:
                when = self._when

            # Now look for it
            for (idx, p) in enumerate(periods):
                if fuzz.ratio(when, p['name'].lower()) > 75:
                    LOG.info("Found %s as %s at index %d",
                             when, p['name'], idx)
                    which = idx
                    break

        # Now look for the period which we want
        period   = periods[which]
        name     = period['name']
        forecast = period['detailedForecast']

        # Tweak some parts of the text to expand abbreviations etc.
        forecast = forecast.replace("mph", "miles per hour")

        # And put it together to give back
        return Result(
            self,
            f"The weather {name} will be {forecast}",
            False,
            True
        )


class WeatherService(Service):
    """
    A service which gets the weather.
    """
    def __init__(self,
                 state,
                 coordinates=None,
                 region="US"):
        """
        @see Service.__init__()

        :param coordinates: A comma-separated longditude and latitude pair, 
                            e.g. ``40.7858267,-74.0050447``.
        :param region:      The region for the forecast, currently only ``US``
                            is supported (sorry).
        """
        super().__init__("Random", state)

        if coordinates is None:
            raise ValueError("Not given coordinates")
        if region is None:
            raise ValueError("Not given a region")

        self._coordinates = coordinates
        if region == "US":
            self._handler_class = _UsHandler
        else:
            raise ValueError(f"Unhandled region: {region}")


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Turn the tokens into a set of words to match on
        words = self._words(tokens)
        try:
            prefix = ("whats", "the", "weather")
            (start, end, score) = fuzzy_list_range(words, prefix)
            if len(words) >= end:
                LOG.info("Matched on: %s", ' '.join(words))
                return self._handler_class(
                    self, tokens, words, start, end, self._coordinates
                )
        except Exception as e:
            LOG.debug("Failed to handle '%s': %s" % (words, e))

        # Not for us
        return None
