#!/usr/bin/env python3
"""
    Author: Roman Burtnyk

    Make sure fastcov diff filtering are working as expected
"""

import json
import fastcov

def test_DiffParser_filterByDiff_empty_file():
    with open('diff_tests_data/basic.json') as f:
        fastcov_data = json.load(f)
    actual = fastcov.DiffParser().filterByDiff('diff_tests_data/no_files.diff', '/mnt/workspace', fastcov_data)
    assert actual == {'sources': {}}

def test_DiffParser_filterByDiff_exclude_few_lines():
    with open('diff_tests_data/basic.json') as f:
        fastcov_data = json.load(f)
        fastcov.convertKeysToInt(fastcov_data)
    with open('diff_tests_data/exclude_few_lines.expected.json') as f:
        expected = json.load(f)
        fastcov.convertKeysToInt(expected)
    actual = fastcov.DiffParser().filterByDiff('diff_tests_data/exclude_few_lines.diff', '/mnt/workspace', fastcov_data)
    assert actual == expected

def test_DiffParser_filterByDiff_include_no_lines():
    with open('diff_tests_data/basic.json') as f:
        fastcov_data = json.load(f)
    actual = fastcov.DiffParser().filterByDiff('diff_tests_data/include_no_lines.diff', '/mnt/workspace', fastcov_data)
    assert actual == {'sources': {}}

def test_DiffParser_filterByDiff_include_one_file_no_branches():
    with open('diff_tests_data/basic.json') as f:
        fastcov_data = json.load(f)
        fastcov.convertKeysToInt(fastcov_data)
    with open('diff_tests_data/include_1file_no_branches.expected.json') as f:
        expected = json.load(f)
        fastcov.convertKeysToInt(expected)
    actual = fastcov.DiffParser().filterByDiff('diff_tests_data/include_1file_no_branches.diff', '/mnt/workspace', fastcov_data)
    assert actual == expected

def test_DiffParser_filterByDiff_exclude_each_item():
    with open('diff_tests_data/basic.json') as f:
        fastcov_data = json.load(f)
        fastcov.convertKeysToInt(fastcov_data)
    with open('diff_tests_data/exclude_each_item.expected.json') as f:
        expected = json.load(f)
        fastcov.convertKeysToInt(expected)
    actual = fastcov.DiffParser().filterByDiff('diff_tests_data/exclude_each_item.diff', '/mnt/workspace', fastcov_data)
    assert actual == expected
