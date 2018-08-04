'''
Methods for dealing with audio manipulation.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import alsaaudio

from   dexter.core.log import LOG

# ------------------------------------------------------------------------------

def set_volume(value):
    '''
    Set the volume to a value between zero and eleven.
    '''
    volume = float(value)

    if volume < 0 or volume > 11:
        raise ValueError("Volume out of [0..11] range: %s" % value)

    # Get the ALSA mixer. We should probably handle pulse audio at some point
    # too I guess.
    try:
        m = alsaaudio.Mixer()
    except:
        m = alsaaudio.Mixer('PCM')

    # Set as a percentage
    pct = int((volume / 11) * 100)
    LOG.info("Setting volume to %d%%" % pct)
    m.setvolume(pct)
