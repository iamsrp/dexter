'''
Methods for dealing with audio manipulation.
'''

try:
    import alsaaudio as pyalsaaudio
except:
    import pyalsa    as pyalsaaudio

from   dexter.core.log import LOG

# ------------------------------------------------------------------------------

def set_volume(value):
    '''
    Set the volume to a value between zero and eleven.

    @type  value: float
    @param value:
        The volume level to set. This should be between 0 and 11 inclusive.
    '''
    volume = float(value)

    if volume < 0 or volume > 11:
        raise ValueError("Volume out of [0..11] range: %s" % value)

    # Get the ALSA mixer
    m = _get_alsa_mixer()

    # Set as a percentage
    pct = int((volume / 11) * 100)
    LOG.info("Setting volume to %d%%" % pct)
    m.setvolume(pct)


def get_volume():
    '''
    Get the current volume, as a value between zero and eleven.

    @rtype: float
    @return:
        The volume level; between 0 and 11 inclusive.
    '''
    # Get the ALSA mixer
    m = _get_alsa_mixer()

    # And give it back, assuming the we care about the highest value
    return 11.0 * min(100, max((0,) + tuple(m.getvolume()))) / 100.0


def _get_alsa_mixer():
    '''
    Get a handle on the ALSA mixer

    @rtype: alsaaudio.Mixer
    @return:
        The mixer.
    '''
    # Get the ALSA mixer. We should probably handle pulse audio at some point
    # too I guess.
    try:
        return pyalsaaudio.Mixer()
    except:
        return pyalsaaudio.Mixer('PCM')
