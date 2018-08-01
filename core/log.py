'''
How we log in the system.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import logging

# Keep it simple for now
LOG = logging

LOG.basicConfig(
    format='[%(asctime)s %(threadName)s %(filename)s:%(lineno)d %(levelname)s] %(message)s',
    level=logging.INFO
)
