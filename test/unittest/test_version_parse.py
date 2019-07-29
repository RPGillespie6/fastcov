#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov correctly handles gcov version parsing
"""

import fastcov

def test_ubuntu_18_04():
    version_str = "gcov (Ubuntu 7.3.0-27ubuntu1~18.04) 7.3.0"
    assert fastcov.parseVersionFromLine(version_str) == (7,3,0)

def test_ubuntu_test_ppa():
    version_str = "gcov (Ubuntu 9.1.0-2ubuntu2~16.04) 9.1.0"
    assert fastcov.parseVersionFromLine(version_str) == (9,1,0)

def test_experimental():
    version_str = "gcov (GCC) 9.0.1 20190401 (experimental)"
    assert fastcov.parseVersionFromLine(version_str) == (9,0,1)

def test_upstream():
    version_str = "gcov (GCC) 9.1.0"
    assert fastcov.parseVersionFromLine(version_str) == (9,1,0)

def test_no_version():
    version_str = "gcov (GCC)"
    assert fastcov.parseVersionFromLine(version_str) == (0,0,0)