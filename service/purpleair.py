"""
Get data from Purple Air and render it.

You will need an API key to do this, as well as a sensor ID. Last tie I checked
you could get an API key by mailing ``contact@purpleair.com``.
"""

from   dexter.core.log   import LOG
from   dexter.core.util  import fuzzy_list_range
from   dexter.service    import Service, Handler, Result

import httplib2
import json
import os
import time

class _PurpleAirHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_PurpleAirHandler, self).__init__(service, tokens, 1.0, True)


    def _get_data(self):
        """
        @see Handler.handle()
        """
        # We'll want to cache the data since hammering PurpleAir is unfriendly
        # and also results in getting back no data.
        sensor_id = self.service.get_sensor_id()
        key       = self.service.get_key()
        filename  = '/tmp/dexter_purpleair_%s' % (sensor_id,)
        now       = time.time()
        content   = None

        # Look for a cached version which is less and a minute old
        try:
            ctime = os.stat(filename).st_ctime
            if now - ctime < 60:
                with open(filename, 'rb') as fh:
                    content = fh.read()
        except IOError:
            pass

        # If we didn't have a good cached version then download it
        if not content:
            h = httplib2.Http()
            resp, content = \
                h.request("https://api.purpleair.com/v1/sensors/%d" % (sensor_id,),
			  "GET",
			  headers={'content-type':'text/plain',
                                   'X-API-Key'   : key } )

            # Save what we downloaded into the cache
            try:
                with open(filename, 'wb') as fh:
                    fh.write(content)
            except IOError:
                pass

        # Now load in whatever we had
        raw = json.loads(content)

        # And pull out the first value from the "results" section, which should
        # be what we care about
        if 'sensor' not in raw or len(raw['sensor']) == 0:
            return {}
        else:
            LOG.debug("Got: %s", raw['sensor'])
            return raw['sensor']


class _AQHandler(_PurpleAirHandler):
    def __init__(self, service, tokens, raw):
        """
        @see Handler.__init__()
        """
        super(_AQHandler, self).__init__(service, tokens)
        self._raw = raw


    def handle(self):
        """
        @see Handler.handle()
        """
        data  = self._get_data()

        # We can look to derive the AQI from this
        value = data.get('pm2.5')
        if value is not None:
            # This is a very rough approximation to the AQI from the PM2_5Value
            value = float(value)
            aqi = value * value / 285
            if self._raw:
                what = "The air quality index %s is %d." % (aqi,)
            else:
                if aqi < 10:
                    quality = "good"
                elif aqi < 50:
                    quality = "okay"
                elif aiq < 100:
                    quality = "acceptable"
                elif aiq < 150:
                    quality = "poor"
                elif aiq < 200:
                    quality = "bad"
                elif aiq < 250:
                    quality = "hazardous"
                else:
                    quality = "extremely hazardous"
                what = "The air quality is %s" % (quality,)
        else:
            what = "The air quality is unknown"

        # And give it back
        return Result(
            self,
            what,
            False,
            True
        )


class _HumidityHandler(_PurpleAirHandler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_HumidityHandler, self).__init__(service, tokens)


    def handle(self):
        """
        @see Handler.handle()
        """
        data = self._get_data()
        humidity = data.get('humidity')
        if humidity is not None:
            what = "%s percent" % (humidity,)
        else:
            what = "unknown"
        return Result(
            self,
            "The humidity is %s." % (what,),
            False,
            True
        )


class _TemperatureHandler(_PurpleAirHandler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_TemperatureHandler, self).__init__(service, tokens)


    def handle(self):
        """
        @see Handler.handle()
        """
        # This comes in Fahrenheit, one day we'll convert it depending on user
        # tastes...
        data = self._get_data()
        temperature = data.get('temperature')
        if temperature is not None:
            what = "%s degrees fahrenheit" % (temperature,)
        else:
            what = "unknown"
        return Result(
            self,
            "The temperature is %s." % (what,),
            False,
            True
        )


class PurpleAirService(Service):
    """
    A service which grabs data from a Purple Air station and uses it to give
    back the values therein.
    """
    _HANDLERS = ((('air', 'quality', 'index'),
                  lambda service, tokens: _AQHandler(service, tokens, True)),
                 (('air', 'quality',),
                  lambda service, tokens: _AQHandler(service, tokens, False)),
                 (('humidity',),
                  _HumidityHandler),
                 (('temperature',),
                  _TemperatureHandler),)
    _PREFICES = (('what', 'is', 'the',),
                 ('whats', 'the',),)


    def __init__(self, state, sensor_id=None, api_key=None):
        """
        @see Service.__init__()
        :type  sensor_id: int
        :param sensor_id:
            The device ID. This can usually be found by looking at the sensor
            information on the Purple Air map (e.g. in the "Get this widget"
            tool-tip). This is required.
        :type  api_key: str
        :param api_key:
            The API read key for the PurleAir API. This is reqiured.
        """
        super(PurpleAirService, self).__init__("PurpleAir", state)

        if sensor_id is None:
            raise ValueError("Sensor ID was not given")
        if api_key is None:
            raise ValueError("API key  was not given")
        self._sensor_id = sensor_id
        self._key       = api_key


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        words = self._words(tokens)
        for (what, handler) in self._HANDLERS:
            for prefix in self._PREFICES:
                phrase = (prefix + what)
                try:
                    (s, e, _) = fuzzy_list_range(words, phrase)
                    if s == 0 and e == len(phrase):
                        return handler(self, tokens)
                except Exception as e:
                    LOG.debug("Failed to handle '%s': %s" % (' '.join(words), e))
        return None


    def get_sensor_id(self):
        """
        Get the sensor ID.
        """
        return self._sensor_id


    def get_key(self):
        """
        Get the API key.
        """
        return self._key
