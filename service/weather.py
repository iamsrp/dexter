"""
Services which get the weather.

The US one should just work out of the box since all the data is freely
accessible.

The UK one will require you to register an account with the Met Office website
and obtain and API key for personal use. See::
    https://www.metoffice.gov.uk/services/data/datapoint/getting-started
"""

from   datetime         import date, timedelta
from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range, parse_number, to_letters
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz
from   urllib.request   import Request, urlopen
from   urllib.error     import HTTPError

import json
import math
import os

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
            self._when = to_letters(words[end])
        else:
            self._when = None

        # See https://www.weather.gov/documentation/services-web-api
        self._url = f'https://api.weather.gov/points/{coordinates}'


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
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
        except HTTPError as e:
            LOG.error("Problem getting the weather data: %s", e)
            return Result(
                self,
                ("Sorry, there was a problem getting the weather for %s. "
                 "Please try again in a minute") % (self._when, ),
                False,
                True
            )

        # The data comes in a number of periods
        periods = fc_data['properties']['periods']

        # Let's just choose the first for now. The name is the name of the
        # period, the first is "tonight" or "today" etc. but later ones are
        # names of days etc.
        which = 0
        if self._when is not None:
            LOG.debug("Handling a 'when' of '%s'", self._when)
            if fuzz.ratio('tomorrow', self._when) > 75:
                # Tomorrow is today + 1day
                LOG.debug("Matched as tomorrow")
                when = (date.today() + timedelta(days=1)).strftime('%A')
            else:
                when = self._when

            # Now look for it
            for (idx, p) in enumerate(periods):
                if fuzz.ratio(when, p['name'].lower()) > 75:
                    LOG.debug("Found %s as %s at index %d",
                              when, p['name'], idx)
                    which = idx
                    break

        # Now look for the period which we want
        period   = periods[which]
        name     = period['name']
        forecast = period['detailedForecast']

        # Tweak some parts of the text to expand abbreviations etc.
        forecast = forecast.replace("mph", "miles per hour")

        # Tweak the first letter of the forecast to be lowercase since we have
        # leading text. Same for the time, if it's not a day
        forecast = forecast[0].lower() + forecast[1:]
        if name.lower() in ('tonight', 'today', 'tomorrow'):
            name = name.lower()

        # And put it together to give back
        return Result(
            self,
            f"The weather {name} will be {forecast}",
            False,
            True
        )

# ------------------------------------------------------------------------------

class _UkHandler(Handler):
    """
    Get the weather from the UK's Met Office site.

    See::
        https://www.metoffice.gov.uk/services/data/datapoint/api-reference
        https://www.metoffice.gov.uk/binaries/content/assets/metofficegovuk/pdf/data/datapoint_api_reference.pdf
    """
    URL = 'http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json'

    DIRECTIONS = {
        'N' : 'north',
        'E' : 'east',
        'S' : 'south',
        'W' : 'west',
    }

    DAY_MAX_TEMP    = 'Dm'
    NIGHT_MAX_TEMP  = 'Nm'
    WIND_GUST_DAY   = 'Gn'
    WIND_GUST_NIGHT = 'Gm'
    WIND_DIR        = 'D'
    WIND_SPEED      = 'S'
    TYPE            = 'W'
    RAIN_PROB_DAY   = 'PPd'
    RAIN_PROB_NIGHT = 'PPn'

    TYPES = {
        '0' : 'clear',
        '1' : 'sunny',
        '2' : 'partly cloudy',
        '3' : 'partly cloudy',
        '5' : 'mist',
        '6' : 'fog',
        '7' : 'cloudy',
        '8' : 'overcast',
        '9' : 'light rain showers',
        '10' : 'light rain showers',
        '11' : 'drizzle',
        '12' : 'light rain',
        '13' : 'heavy rain showers',
        '14' : 'heavy rain showers',
        '15' : 'heavy rain',
        '16' : 'sleet showers',
        '17' : 'sleet showers',
        '18' : 'sleet',
        '19' : 'hail showers',
        '20' : 'hail showers',
        '21' : 'hail',
        '22' : 'light snow showers',
        '23' : 'light snow showers',
        '24' : 'light snow',
        '25' : 'heavy snow showers',
        '26' : 'heavy snow showers',
        '27' : 'heavy snow',
        '28' : 'thunder showers',
        '29' : 'thunder showers',
        '30' : 'thunder'
    }

    PRECIPITATION_TYPES = {
        '9' : 'rain',
        '10' : 'rain',
        '11' : 'drizzle',
        '12' : 'rain',
        '13' : 'rain',
        '14' : 'rain',
        '15' : 'rain',
        '16' : 'sleet',
        '17' : 'sleet',
        '18' : 'sleet',
        '19' : 'hail',
        '20' : 'hail',
        '21' : 'hail',
        '22' : 'snow',
        '23' : 'snow',
        '24' : 'snow',
        '25' : 'snow',
        '26' : 'snow',
        '27' : 'snow',
        '28' : 'thunder',
        '29' : 'thunder',
        '30' : 'thunder'
    }

    def __init__(self, service, tokens, words, start, end, coordinates):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, True)

        # The stuff after the end of the match is the day specifier (we hope)
        if end < len(words):
            self._when = to_letters(words[end])
        else:
            self._when = None
        self._location = service.metoffice_location(coordinates)

        # Create the URL where we grab the forecast from
        location = self._location['id']
        api_key  = service.api_key
        self._url = f'{self.URL}/{location}?res=daily&key={api_key}'


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            # Start with the main URL request
            request = Request(self._url,
                              headers=_HEADERS)
            with urlopen(request) as handle:
                data = json.loads(''.join(l.decode('UTF')
                                          for l in handle.readlines()))
        except HTTPError as e:
            LOG.error("Problem getting the weather data: %s", e)
            return Result(
                self,
                ("Sorry, there was a problem getting the weather for %s. "
                 "Please try again in a minute") % (self._when, ),
                False,
                True
            )

        # Shred out the parameter names
        params = dict()
        for param in data['SiteRep']['Wx']['Param']:
            params[param['name']] = param

        # And find the forecasts, keyed by date and day/night
        periods = dict()
        for period in data['SiteRep']['DV']['Location']['Period']:
            for rep in period['Rep']:
                key = "%s-%s" % (period['value'], rep['$'])
                periods[key] = rep

        # See when we want
        if self._when is None:
            day_night = 'Day'
            day = date.today()
        else:
            # Look for the day as a date string
            when = self._when.lower()
            day_night = 'Day'
            if fuzz.ratio('today', when) > 75:
                day = date.today()
            elif fuzz.ratio('tonight', when) > 75:
                day = date.today()
                day_night = 'Night'
            elif fuzz.ratio('tomorrow', when) > 75:
                # Tomorrow is today + 1day
                day = date.today() + timedelta(days=1)
            else:
                # Look for the matching day
                best = None
                day = date.today()
                for i in range(7):
                    day = day + timedelta(days=1)
                    ratio = fuzz.ratio(when, day.strftime('%A').lower())
                    if best is None or ratio > best[0]:
                        best = (ratio, day)
                day = best[1]

        # The key comes from the day and day/night values now
        key = day.strftime(f'%Y-%m-%dZ-{day_night}')

        # And look it up
        period = periods.get(key)
        if period is None:
            return Result(
                self,
                ("Sorry, there was a problem getting the weather for %s" %
                 (self._when, )),
                False,
                True
            )

        # Get the details
        typ = period.get(self.TYPE)
        wind_speed = period.get(self.WIND_SPEED)
        wind_dir   = self._dir(period.get(self.WIND_DIR))
        wind_gust  = period.get(self.WIND_GUST_DAY,
                                period.get(self.WIND_GUST_NIGHT))
        rain_prob  = period.get(self.RAIN_PROB_DAY,
                                period.get(self.RAIN_PROB_NIGHT))
        max_temp   = period.get(self.DAY_MAX_TEMP,
                                period.get(self.NIGHT_MAX_TEMP))

        # Now build up the string
        main = f'The weather in {self._location["name"]} {self._when} will be'
        wind = ''
        rain = ''
        if typ in self.TYPES:
            main += ' ' + self.TYPES[typ]
        else:
            main += ' a surprise'
        if max_temp:
            main += ' with a maximum temperature of ' + \
                     max_temp + ' celcius'
        if wind_speed:
            wind += wind_speed + ' mile per hour'
            if wind_dir:
                wind += ' ' + wind_dir
            wind +=  ' winds'
            if wind_gust:
                wind += ' gusting up to ' + wind_gust + ' miles per hour'
        if rain_prob:
            rain += 'a ' + rain_prob + '% chance of ' + \
                    self.PRECIPITATION_TYPES.get(typ, 'rain')

        # Put the parts together
        result = main
        if wind:
            if rain:
                result += ', '
            else:
                result += ' and '
            result += wind
        if rain:
            result += ', with ' + rain
        result += '.'

        # And give it back
        return Result(self, result, False, True)


    def _dir(self, spec):
        """
        Get a wind direction from the specification string.
        """
        if spec:
            return ' '.join(
                self.DIRECTIONS.get(char, '')
                for char in spec
            )
        else:
            return None

# ------------------------------------------------------------------------------

class WeatherService(Service):
    """
    A service which gets the weather.
    """
    def __init__(self,
                 state,
                 coordinates=None,
                 region     ="US",
                 api_key    =None):
        """
        @see Service.__init__()

        :param coordinates:
            A comma-separated (latitude,longitude) pair, with no spaces
            e.g. ``40.7858267,-74.0050447``.
        :param region:
            The region for the forecast, currently only ``US`` and ``UK`` are
            supported.
        :param api_key:
            The Met Office API key string, if UK region.
        """
        super().__init__("Random", state)

        # Validate required inputs
        if coordinates is None:
            raise ValueError("Not given coordinates")
        if region is None:
            raise ValueError("Not given a region")

        # Save general inputs
        self._coordinates = coordinates
        self._api_key     = api_key

        # Handle region-specific params
        if region == "US":
            self._handler_class = _UsHandler
        elif region == "UK":
            # We need to get the location from the Met Office site
            if self._api_key is None:
                raise ValueError("Need a Met Office API key for the UK")
            self._metoffice_locations = dict()
            self._handler_class       = _UkHandler
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


    def metoffice_location(self, coordinates):
        """
        Give back the Met Office location dict, if any.
        """
        if coordinates not in self._metoffice_locations:
            self._metoffice_locations[coordinates] = \
                self._find_metoffice_location(self._api_key, coordinates)
        return self._metoffice_locations[coordinates]


    @property
    def api_key(self):
        return self._api_key


    def _get_metoffice_sitelist(self, api_key):
        """
        Get the list of Met Office sites, caching it into a file since we want to
        avoid downloading it multiple times.
        """
        # Cache it as this
        filename = os.path.join('/tmp', 'sitelist_%s' % os.getuid())

        # See if we have a cached version
        if os.path.exists(filename):
            with open(filename, 'r') as fh:
                # Pull it all in
                return json.loads(fh.read())
        else:
            # Pull it down
            url = f'{_UkHandler.URL}/sitelist?key={api_key}'
            request = Request(url, headers=_HEADERS)
            with urlopen(request) as handle:
                text = ''.join(l.decode('UTF')
                               for l in handle.readlines())

            # Save it
            with open(filename, 'w') as fh:
                return fh.write(text)

            # And give it back
            return json.loads(text)


    def _find_metoffice_location(self, api_key, coordinates):
        """
        Find the closest location data from the given Met Office sites file.
        """
        # Turn the coordinates string into a pair of values
        coords = [float(v.strip()) for v in coordinates.split(',')]

        # Load in the file and find the closest site
        data = self._get_metoffice_sitelist(api_key)
        best = None
        for location in data['Locations']['Location']:
            # Simply cartesian distance
            longitude = float(location['longitude'])
            latitude  = float(location['latitude'])
            dist = math.sqrt((coords[0] - latitude )**2 +
                             (coords[1] - longitude)**2)
            if best is None or best[0] > dist:
                best = (dist, location)

        # Anything?
        return best[1] if best is not None else None
