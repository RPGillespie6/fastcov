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

def test_addDicts():
    dict1 = {"a": 1}
    dict2 = {"a": 0, "b": 1, "c": 200}

    # Should return a new dict
    result = fastcov.addDicts(dict1, dict2)
    assert(result == {"a": 1, "b": 1, "c": 200})

    result2 = fastcov.addDicts(result, dict2)
    assert(result2 == {"a": 1, "b": 2, "c": 400})

def test_addLists():
    list1 = [1,2,3,4]
    list2 = [1,0,0,4]
    list3 = [1,0]
    list4 = [9,9,9]

    # Should return a new list
    result = fastcov.addLists(list1, list2)
    assert(result == [2,2,3,8])

    # if lens are mismatched, make sure it overlays onto bigger one
    result = fastcov.addLists(list1, list3)
    assert(result == [2,2,3,4])

    # if lens are mismatched, make sure it overlays onto bigger one
    result = fastcov.addLists(list4, list1)
    assert(result == [10,11,12,4])