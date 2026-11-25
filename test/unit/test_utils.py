#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    Make sure fastcov internal utils are working as expected
"""

import os
import sys

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
    left = {"a": 1}
    right = {"a": 0, "b": 1, "c": 200}

    result = fastcov.addDicts(left, right)
    assert result is left
    assert left == {"a": 1, "b": 1, "c": 200}
    assert right == {"a": 0, "b": 1, "c": 200}

    more = {"a": 0, "b": 1, "c": 200}
    result2 = fastcov.addDicts(left, more)
    assert result2 is left
    assert left == {"a": 1, "b": 2, "c": 400}
    assert more == {"a": 0, "b": 1, "c": 200}

def test_addLists():
    left = [1, 2, 3, 4]
    right = [1, 0, 0, 4]
    assert fastcov.addLists(left, right) is left
    assert left == [2, 2, 3, 8]
    assert right == [1, 0, 0, 4]

    longer = [1, 2, 3, 4]
    shorter = [1, 0]
    assert fastcov.addLists(longer, shorter) is longer
    assert longer == [2, 2, 3, 4]
    assert shorter == [1, 0]

    shorter = [9, 9, 9]
    longer = [1, 2, 3, 4]
    assert fastcov.addLists(shorter, longer) is shorter
    assert shorter == [10, 11, 12, 4]
    assert longer == [1, 2, 3, 4]

def _coverage(lines, branches, functions):
    return {"functions": functions, "branches": branches, "lines": lines}

def test_combineReports_sums_shared_coverage_and_keeps_disjoint_files():
    base = {"sources": {
        "/a.cpp": {"": _coverage(
            {10: 3, 11: 0},
            {10: [1, 0]},
            {"foo": {"start_line": 4, "execution_count": 2}},
        )},
        "/only_base.cpp": {"": _coverage({1: 1}, {}, {})},
    }}
    overlay = {"sources": {
        "/a.cpp": {"": _coverage(
            {10: 1, 12: 8},
            {10: [0, 5, 7]},
            {
                "foo": {"start_line": 99, "execution_count": 4},
                "bar": {"start_line": 20, "execution_count": 1},
            },
        )},
        "/only_overlay.cpp": {"test_b": _coverage({2: 0}, {}, {})},
    }}

    fastcov.combineReports(base, overlay)

    shared = base["sources"]["/a.cpp"][""]
    assert shared["lines"] == {10: 4, 11: 0, 12: 8}
    assert shared["branches"][10] == [1, 5, 7]
    assert shared["functions"]["foo"] == {"start_line": 4, "execution_count": 6}
    assert shared["functions"]["bar"] == {"start_line": 20, "execution_count": 1}
    assert base["sources"]["/only_base.cpp"][""]["lines"] == {1: 1}
    assert base["sources"]["/only_overlay.cpp"]["test_b"]["lines"] == {2: 0}

def test_processGcdas_sums_coverage_flushed_in_partials(tmp_path, monkeypatch):
    monkeypatch.setattr(fastcov, "PARTIAL_REPORT_ENTRY_BUDGET", 1)
    fastcov.EXIT_CODE = 0
    fastcov.GCOVS_TOTAL = 0
    fastcov.GCOVS_SKIPPED = 0

    gcov = tmp_path / "gcov"
    gcov.write_text(
        "import json, os, sys\n"
        "paths = [a for a in sys.argv[1:] if not a.startswith('-')]\n"
        "for path in paths:\n"
        "    source = os.path.basename(path).split('.')[0].split('_')[0] + '.cpp'\n"
        "    print(json.dumps({\n"
        "        'current_working_directory': '/src',\n"
        "        'files': [{\n"
        "            'file': source,\n"
        "            'functions': [{'name': 'foo', 'start_line': 1, 'execution_count': 1}],\n"
        "            'lines': [\n"
        "                {'line_number': 1, 'count': 1, 'branches': [], 'function_name': 'foo'},\n"
        "                {'line_number': 2, 'count': 0, 'branches': [\n"
        "                    {'count': 1, 'fallthrough': True, 'throw': False},\n"
        "                    {'count': 0, 'fallthrough': False, 'throw': False},\n"
        "                ], 'function_name': 'foo'},\n"
        "            ],\n"
        "        }],\n"
        "    }), flush=True)\n"
    )
    os.chmod(gcov, 0o755)

    coverage_files = []
    for name in ("a_1.gcda", "a_2.gcda", "b_1.gcda", "b_2.gcda"):
        path = tmp_path / name
        path.write_text("")
        coverage_files.append(str(path))

    args = type("Args", (), {})()
    wrapper = tmp_path / "gcov.sh"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {gcov} \"$@\"\n")
    os.chmod(wrapper, 0o755)
    args.gcov = str(wrapper)
    args.branchcoverage = False
    args.xbranchcoverage = False
    args.cdirectory = ""
    args.gcno_dir = ""
    args.directory = str(tmp_path)
    args.test_name = ""
    args.use_gcno = False
    args.jobs = 4
    args.minimum_chunk = 1

    report = fastcov.processGcdas(args, coverage_files, {
        "sources": set(), "include": [], "exclude": [], "exclude_glob": [],
    })

    assert fastcov.GCOVS_TOTAL == 4
    assert fastcov.GCOVS_SKIPPED == 0
    assert fastcov.EXIT_CODE == 0
    assert set(report["sources"]) == {"/src/a.cpp", "/src/b.cpp"}
    for source in report["sources"].values():
        data = source[""]
        assert data["lines"] == {1: 2, 2: 0}
        assert data["branches"][2] == [2, 0]
        assert data["functions"]["foo"] == {"start_line": 1, "execution_count": 2}

def test_processGcdas_keeps_the_partial_that_never_reaches_the_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(fastcov, "PARTIAL_REPORT_ENTRY_BUDGET", 1_000_000)
    fastcov.EXIT_CODE = 0
    fastcov.GCOVS_TOTAL = 0
    fastcov.GCOVS_SKIPPED = 0

    gcov = tmp_path / "gcov"
    gcov.write_text(
        "import json, os, sys\n"
        "paths = [a for a in sys.argv[1:] if not a.startswith('-')]\n"
        "for path in paths:\n"
        "    source = os.path.basename(path).split('.')[0].split('_')[0] + '.cpp'\n"
        "    print(json.dumps({\n"
        "        'current_working_directory': '/src',\n"
        "        'files': [{\n"
        "            'file': source,\n"
        "            'functions': [{'name': 'foo', 'start_line': 1, 'execution_count': 3}],\n"
        "            'lines': [\n"
        "                {'line_number': 1, 'count': 3, 'branches': [], 'function_name': 'foo'},\n"
        "            ],\n"
        "        }],\n"
        "    }), flush=True)\n"
    )
    os.chmod(gcov, 0o755)

    coverage_files = []
    for name in ("a_1.gcda", "b_1.gcda"):
        path = tmp_path / name
        path.write_text("")
        coverage_files.append(str(path))

    wrapper = tmp_path / "gcov.sh"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {gcov} \"$@\"\n")
    os.chmod(wrapper, 0o755)

    args = type("Args", (), {})()
    args.gcov = str(wrapper)
    args.branchcoverage = False
    args.xbranchcoverage = False
    args.cdirectory = ""
    args.gcno_dir = ""
    args.directory = str(tmp_path)
    args.test_name = "suite"
    args.use_gcno = False
    args.jobs = 2
    args.minimum_chunk = 1

    report = fastcov.processGcdas(args, coverage_files, {
        "sources": set(), "include": [], "exclude": [], "exclude_glob": [],
    })

    assert set(report["sources"]) == {"/src/a.cpp", "/src/b.cpp"}
    for source in report["sources"].values():
        data = source["suite"]
        assert data["lines"] == {1: 3}
        assert data["functions"]["foo"]["execution_count"] == 3