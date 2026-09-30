#!/usr/bin/env python3
"""compiled_manifest.py forget|record -- bracket the decomp compile for the mtime rewind (#416).

The Makefile runs `forget` before `make -C fireemblem8u` and `record` after it succeeds, so
the record always describes the objects on disk. inject.warm has the why.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.warm  # noqa: E402


def main(argv):
    if argv == ['forget']:
        inject.warm.forget_compiled()
    elif argv == ['record']:
        print('compiled manifest: %d injected file(s) recorded' % inject.warm.record_compiled())
    else:
        sys.exit('usage: compiled_manifest.py forget|record')


if __name__ == '__main__':
    main(sys.argv[1:])
