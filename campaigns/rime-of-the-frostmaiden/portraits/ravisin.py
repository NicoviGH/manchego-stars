#!/usr/bin/env python3
"""Regenerate Ravisin's bust from Garytop's vendored FE-Repo Aversa mug.

  python3 campaigns/rime-of-the-frostmaiden/portraits/ravisin.py

This is a strict palette operation on the original 128x112 FE-Repo sheet: crop the
96x80 main frame, replace the seven approved hair/skin colours, and index it for the
existing FE8 portrait pipeline. No generated pixels, geometry edits, smoothing, or
redrawing are involved. The original brown face/chest markings stay brown.
"""
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))

import inject.cast  # noqa: E402
import inject.portraits  # noqa: E402


def main():
    source = os.path.join(HERE, 'vendor', inject.portraits.RAVISIN_VENDOR_MUG)
    if not os.path.isfile(source):
        raise SystemExit('ERROR: missing vendored Ravisin source: %s' % source)
    out = os.path.join(HERE, 'ravisin.png')
    inject.cast._vendor_mug_to_bust(source, inject.portraits.RAVISIN_RECOLOR).save(out)
    print('-> %s' % out)


if __name__ == '__main__':
    main()
