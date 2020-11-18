"""
Methods for dealing with audio I/O manipulation.
"""

from dexter.core.log import LOG

try:
    import alsaaudio as pyalsaaudio
except:
    import pyalsa    as pyalsaaudio

# ------------------------------------------------------------------------------

MIN_VOLUME =  0
MAX_VOLUME = 11

# ------------------------------------------------------------------------------


def set_volume(value):
    """
    Set the volume to a value between zero and eleven.

    :type  value: float
    :param value:
        The volume level to set. This should be between `MIN_VOLUME` and 
        `MAX_VOLUME` inclusive.
    """
    volume = float(value)

    if volume < MIN_VOLUME or volume > MAX_VOLUME:
        raise ValueError("Volume out of [%d..%d] range: %s" %
                         (MIN_VOLUME, MAX_VOLUME, value))

    # Get the ALSA mixer
    m = _get_alsa_mixer()

    # Set as a percentage
    pct = int((volume / MAX_VOLUME) * 100)
    LOG.info("Setting volume to %d%%" % pct)
    m.setvolume(pct)


def get_volume():
    """
    Get the current volume, as a value between zero and eleven.

    :rtype: float
    :return:
        The volume level; between 0 and 11 inclusive.
    """
    # Get the ALSA mixer
    m = _get_alsa_mixer()

    # And give it back, assuming the we care about the highest value
    return float(MAX_VOLUME) * min(100, max((0,) + tuple(m.getvolume()))) / 100.0


def _get_alsa_mixer():
    """
    Get a handle on the ALSA mixer

    :rtype: alsaaudio.Mixer
    :return:
        The mixer.
    """
    # Get the ALSA mixer by going in the order that they are listed
    for mixer in pyalsaaudio.mixers():
        try:
            return pyalsaaudio.Mixer(mixer)
        except:
            pass

    # With no mixer we can't do anything
    raise ValueError("No mixer found")
