#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov internal utils are working as expected
"""

import unittest
import fastcov

class TestUtils(unittest.TestCase):

    def test_tupleToDotted(self):
        actual_to_expected = {
            (1,0): "1.0",
            (0,7,8): "0.7.8",
            (1,2,3,4,5): "1.2.3.4.5",
        }

        for actual, expected in actual_to_expected.items():
            self.assertEqual(fastcov.tupleToDotted(actual), expected)

        with self.assertRaises(TypeError):
            fastcov.tupleToDotted(123)

    def test_chunk(self):
        chunk_me = [1,2,3,4,5,6,7,8,9,10]
        expected = [
            [1,2,3,4],
            [5,6,7,8],
            [9,10],
        ]

        self.assertEqual(len(list(fastcov.chunks(chunk_me, 4))), len(expected))
        for i, chunk in enumerate(fastcov.chunks(chunk_me, 4)):
            self.assertEqual(chunk, expected[i])

if __name__ == '__main__':
    unittest.main()
