#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov internal utils are working as expected
"""

import pytest
import fastcov

def test_tupleToDotted():
    actual_to_expected = {
        (1,0): "1.0",
        (0,7,8): "0.7.8",
        (1,2,3,4,5): "1.2.3.4.5",
    }

    for actual, expected in actual_to_expected.items():
        assert fastcov.tupleToDotted(actual) == expected

    with pytest.raises(TypeError):
        fastcov.tupleToDotted(123)

def test_chunk():
    chunk_me = [1,2,3,4,5,6,7,8,9,10]
    expected = [
        [1,2,3,4],
        [5,6,7,8],
        [9,10],
    ]

    assert len(list(fastcov.chunks(chunk_me, 4))) == len(expected)
    for i, chunk in enumerate(fastcov.chunks(chunk_me, 4)):
        assert chunk == expected[i]
