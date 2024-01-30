#!/usr/bin/env python3
"""
    Author: Jean-Philippe Lapointe

    Make sure fastcov's gcov prefix options are processing the file paths as expected
"""

import pytest
import fastcov

from dataclasses import dataclass
import os

@dataclass
class TestSet:
    __test__ = False
    path: str
    prefix: str
    prefix_strip: int
    expected_result: str


def test_simpleStripping():
    testPatterns = [
        # Making the path relative to the root of the git repo
        TestSet('/home/user1/work/git/repo/subdir/to/some/file.cpp',    '',                             5, 'subdir/to/some/file.cpp'),
        # Essentially changing user directory from user1 to user2
        TestSet('/home/user1/work/git/repo/subdir/to/some/file.cpp',    '/home/user2',                  2, '/home/user2/work/git/repo/subdir/to/some/file.cpp'),
        # Relative path, shouldn't get modified.
        TestSet('subdir/to/some/file.cpp',                              '/home/user2',                  2, 'subdir/to/some/file.cpp'),
        # Current file should exist, it won't get messed with
        TestSet(os.path.abspath(__file__),                              '/home/user2',                  1, os.path.abspath(__file__)),
        # Just prefixing an already absolute path
        TestSet('/usr/include/someUnknownHeaderFile.h',                 '/home/user2/work/git/repo',    0, '/home/user2/work/git/repo/usr/include/someUnknownHeaderFile.h')
    ]

    for elem in testPatterns:
        assert(fastcov.processPrefix(elem.path, elem.prefix, elem.prefix_strip) == elem.expected_result)
