#!/usr/bin/env python3
"""
    Author: Roman Burtnyk

    Make sure fastcov diff parser are working as expected
"""

import pytest
import fastcov


def test_DiffParser_parseTargetFile_usual():
    actual = fastcov.DiffParser()._parseTargetFile('+++ file1/tests   \n')
    assert actual == 'file1/tests'
    actual = fastcov.DiffParser()._parseTargetFile('+++ test2')
    assert actual == 'test2'

def test_DiffParser_parseTargetFile_empty():
    actual = fastcov.DiffParser()._parseTargetFile('+++ ')
    assert actual == ''

def test_DiffParser_parseTargetFile_with_prefix():
    actual = fastcov.DiffParser()._parseTargetFile('+++ b/dir2/file\n')
    assert actual == 'dir2/file'
    actual = fastcov.DiffParser()._parseTargetFile('+++ b/b/file\n')
    assert actual == 'b/file'
    actual = fastcov.DiffParser()._parseTargetFile('+++ bfile/b\n')
    assert actual == 'bfile/b'

def test_DiffParser_parseTargetFile_with_timestamp():
    actual = fastcov.DiffParser()._parseTargetFile('+++ base/test_file.txt\t2002-02-21 23:30:39.942229878 -0800')
    assert actual == 'base/test_file.txt'

def test_DiffParser_parseHunkBoundaries_usual():
    tstart,tlen, sstart, slen = fastcov.DiffParser()._parseHunkBoundaries('@@ -1,2 +3,4 @@ zero line  \n', 1)
    assert sstart == 1
    assert slen == 2
    assert tstart == 3
    assert tlen == 4

def test_DiffParser_parseHunkBoundaries_count_missed():
    tstart,tlen, sstart, slen = fastcov.DiffParser()._parseHunkBoundaries('@@ -11 +13,14 @@ zero line  \n', 1)
    assert sstart == 11
    assert slen == 1
    assert tstart == 13
    assert tlen == 14

    tstart, tlen, sstart, slen = fastcov.DiffParser()._parseHunkBoundaries('@@ -11 +13 @@ zero line  \n', 1)
    assert sstart == 11
    assert slen == 1
    assert tstart == 13
    assert tlen == 1

    tstart, tlen, sstart, slen = fastcov.DiffParser()._parseHunkBoundaries('@@ -11,12 +13 @@ zero line  \n', 1)
    assert sstart == 11
    assert slen == 12
    assert tstart == 13
    assert tlen == 1

def test_DiffParser_parseHunkBoundaries_invalid_hunk():
    with pytest.raises(fastcov.DiffParseError) as e:
        fastcov.DiffParser()._parseHunkBoundaries('@@ 1112 @@ zero line  \n', 1)

    with pytest.raises(fastcov.DiffParseError) as e:
        fastcov.DiffParser()._parseHunkBoundaries('@@ @@ zero line  \n', 1)


def test_DiffParser_parseDiffFile_empty():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/empty.diff', '/base')
    assert not result

def test_DiffParser_parseDiffFile_no_files():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/no_files.diff', '/base')
    assert not result

def test_DiffParser_parseDiffFile_deleted_file():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/deleted_file.diff', '/base')
    assert not result

def test_DiffParser_parseDiffFile_file_deleted_added_modifiled():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/file_del_mod_add_lines.diff', '/base')
    assert result == {'/base/test.txt': {4, 8}}

def test_DiffParser_parseDiffFile_file_deleted_added_check_other_base():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/file_del_mod_add_lines.diff', '/base/base2')
    assert result == {'/base/base2/test.txt': {4, 8}}

def test_DiffParser_parseDiffFile_file_renamed_and_edited():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/renamed_edited.diff', '/base')
    assert result == {'/base/test5.txt': {8}}

def test_DiffParser_parseDiffFile_few_files_with_few_added_hunks():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/few_files_with_few_added_hunks.diff', '/base')
    assert result == {"/base/test.txt":{2,3,4,5,6,7,8,9,10,11,23,24,25,26,27,28,29,30,31,32,33},
                      "/base/test2.txt":{10,11,12,13},
                      "/base/test3.txt":{5,6,7,8,9,10,11,21,22,23,24,25}
                      }

def test_DiffParser_parseDiffFile_few_files_with_few_modified_hunks():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/few_files_with_few_modified_hunks.diff', '/base')
    assert result == {"/base/test.txt":{2,3,4,5,6,7,8,9,10,25,26,27,28,29,30,31,32,33},
                      "/base/test2.txt":{10,11,12},
                      "/base/test3.txt":{2,3,4,22,23,24}
                      }

def test_DiffParser_parseDiffFile_invalid():
    with pytest.raises(fastcov.DiffParseError) as e:
        fastcov.DiffParser()._parseHunkBoundaries('@@ 1112 @@ zero line  \n', 1)

def test_DiffParser_parseDiffFile_hunk_longer_than_expected():
    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/hunk_longer_than_expected.diff', '/base')

    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/hunk_longer_than_expected2.diff', '/base')

def test_DiffParser_parseDiffFile_last_hunk_longer_than_expected():
    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/last_hunk_longer_than_expected.diff', '/base')

    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/last_hunk_longer_than_expected2.diff', '/base')

def test_DiffParser_parseDiffFile_hunk_shorter_than_expected():
    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/hunk_shorter_than_expected.diff', '/base')

    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/hunk_shorter_than_expected2.diff', '/base')

def test_DiffParser_parseDiffFile_last_hunk_shorter_than_expected():
    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/last_hunk_shorter_than_expected.diff', '/base')

    with pytest.raises(fastcov.DiffParseError) as e:
        result = fastcov.DiffParser().parseDiffFile('diff_tests_data/last_hunk_shorter_than_expected2.diff', '/base')

def test_DiffParser_parseDiffFile_bad_encoding():
    result = fastcov.DiffParser().parseDiffFile('diff_tests_data/bad_encoding.diff', '/base')
    assert result == {'/base/test.txt': {4, 8}}
