#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov's internal versioning matches both itself and setup.cfg
"""

import sys
import pytest
import fastcov

def test_fastcov_version_match():
    setup_cfg_version = ""
    with open("../../setup.cfg") as f:
        for line in f:
            if line.startswith("version"):
                setup_cfg_version = line.split()[-1].strip()
                break

    assert setup_cfg_version == fastcov.__version__

    setup_cfg_version_tup = tuple(map(int, setup_cfg_version.split(".")))
    assert setup_cfg_version_tup == fastcov.FASTCOV_VERSION

def test_python_version_match():
    fastcov.checkPythonVersion(fastcov.MINIMUM_PYTHON)
    with pytest.raises(SystemExit) as e:
        fastcov.checkPythonVersion((2,7))
        assert e.type == SystemExit
        assert e.value.code == 3

def test_gcov_version_match():
    fastcov.checkGcovVersion(fastcov.MINIMUM_GCOV)
    with pytest.raises(SystemExit) as e:
        fastcov.checkGcovVersion((8,1,0))
        assert e.type == SystemExit
        assert e.value.code == 4

def test_bad_combine_extension():
    with pytest.raises(SystemExit) as e:
        fastcov.parseAndCombine(["badfile.bad"])
        assert e.type == SystemExit
        assert e.value.code == 5