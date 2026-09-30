#!/usr/bin/env python3
"""Shard 1 of the check canaries (#407) -- see test_check_canaries.py for why they are split.

Run:  python3 tools/test_check_canaries_shard1.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_check_canaries as canaries                               # noqa: E402


class CanariesFire(canaries.CanariesFire):
    SHARD = 1


if __name__ == '__main__':
    unittest.main()
