#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov's internal versioning matches both itself and setup.cfg
"""

import fastcov

def test_version_match():
    setup_cfg_version = ""
    with open("../../setup.cfg") as f:
        for line in f:
            if "version" in line:
                setup_cfg_version = line.split()[-1].strip()

    assert setup_cfg_version == fastcov.__version__

    setup_cfg_version_tup = tuple(map(int, setup_cfg_version.split(".")))
    assert setup_cfg_version_tup == fastcov.FASTCOV_VERSION