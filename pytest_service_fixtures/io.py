# -*- coding: utf-8 -*-
"""
Oisin Mulvihill
2015-02-06

"""
import logging

import pytest


@pytest.fixture(scope='session')
def logger(request):
    """Set up a root logger showing all entries in the console.
    """
    log = logging.getLogger()
    hdlr = logging.StreamHandler()
    fmt = '%(asctime)s %(name)s %(levelname)s %(message)s'
    formatter = logging.Formatter(fmt)
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.DEBUG)
    log.propagate = False

    return log
