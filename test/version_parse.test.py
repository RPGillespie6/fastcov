#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov correctly handles gcov version parsing
"""

import unittest
import fastcov

class TestVersionParse(unittest.TestCase):

    def test_ubuntu_18_04(self):
        version_str = "gcov (Ubuntu 7.3.0-27ubuntu1~18.04) 7.3.0"
        self.assertEqual(fastcov.parseVersionFromLine(version_str), (7,3,0))

    def test_experimental(self):
        version_str = "gcov (GCC) 9.0.1 20190401 (experimental)"
        self.assertEqual(fastcov.parseVersionFromLine(version_str), (9,0,1))

    def test_no_version(self):
        version_str = "gcov (GCC)"
        self.assertEqual(fastcov.parseVersionFromLine(version_str), (0,0,0))

if __name__ == '__main__':
    unittest.main()