#!/usr/bin/env python3
"""Shard 1 of tools/test_difficulty.py (#579) -- see its SHARDS for why it is split.

Run:  python3 tools/test_difficulty_shard1.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_difficulty as whole                                      # noqa: E402

SHARD = 1


def load_tests(loader, tests, pattern):
    return whole.shard_suite(loader, SHARD)


if __name__ == '__main__':
    unittest.main()
