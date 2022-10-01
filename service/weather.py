"""
Services which get the weather.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range, parse_number
from   dexter.service   import Service, Handler, Result
from   urllib.request   import Request, urlopen

import json

_HEADERS = {'User-Agent': 'Mozilla/5.0'}

class _UsHandler(Handler):
    """
    Get the weather from weather.gov via there RESTful API.
    """
    def __init__(self, service, tokens, start, end, coordinates):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, False)

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
        which  = 0
        period = periods[which]
        name     = period['name']
        if which > 0:
            name = "on " + name
        forecast = period['detailedForecast']

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
            prefix = ("what's", "the", "weather")
            (start, end, score) = fuzzy_list_range(words, prefix)
            if len(words) >= end:
                return self._handler_class(
                    self, tokens, start, end, self._coordinates
                )
        except Exception as e:
            LOG.debug("Failed to handle '%s': %s" % (words, e))

        # Not for us
        return None
