# -*- coding: utf-8 -*-
"""

An example pytest using a fixture from conftest.py

"""
#import pytest


def test_some_functionality(logger):

    logger.warn("Hello from example test! Please actually write some tests.")

    assert 1 == 1
