#!/usr/bin/env python3
"""A shard of tools/test_difficulty.py (#579): see its SHARDS for why it is split."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_difficulty                                                 # noqa: E402

if __name__ == '__main__':
    test_difficulty.shard_main(__file__)
