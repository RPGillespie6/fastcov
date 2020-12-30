#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2020-present, Bryan Gillespie

SCRIPT_DESCRIPTION = """
    Author: Bryan Gillespie
    https://github.com/RPGillespie6/fastcov

    A simple utility for summarizing a fastcov coverage file and returning non-zero rc if coverage thresholds are not met.

    Sample Usage:
        $ ./fastcov_summary.py coverage.json --line-coverage-threshold 70
"""

import sys
import json
import time
import argparse
from collections import defaultdict

# Interesting metrics
START_TIME    = time.monotonic()

# For when things go wrong...
# Start error codes at 3 because 1-2 are special
# See https://stackoverflow.com/a/1535733/2516916
EXIT_CODE  = 0
EXIT_CODES = {
    "function_coverage_threshold": 3,
    "line_coverage_threshold": 4,
    "branch_coverage_threshold": 5,
}

def setExitCode(key):
    global EXIT_CODE
    EXIT_CODE = EXIT_CODES[key]

def stopwatch():
    """Return number of seconds since last time this was called."""
    global START_TIME
    end_time   = time.monotonic()
    delta      = end_time - START_TIME
    START_TIME = end_time
    return delta

def parseArgs():
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument('fastcov_coverage', help='The fastcov coverage file to summarize')
    parser.add_argument('-f', '--function-coverage-threshold', type=float, default=0, help='Fail if function coverage falls below this %%')
    parser.add_argument('-l', '--line-coverage-threshold',     type=float, default=0, help='Fail if line coverage falls below this %%')
    parser.add_argument('-b', '--branch-coverage-threshold',   type=float, default=0, help='Fail if branch coverage falls below this %%')
    return parser.parse_args()

def main():
    args = parseArgs()

    with open(args.fastcov_coverage) as f:
        coverage = json.load(f)

    totals = {
        "function": {"percent": 0, "total": 0, "hit": 0},
        "line":     {"percent": 0, "total": 0, "hit": 0},
        "branch":   {"percent": 0, "total": 0, "hit": 0},
    }

    for source in coverage["sources"].values():
        ss = {
            "function": defaultdict(bool),
            "line": defaultdict(bool),
            "branch": defaultdict(bool),
        }

        for test in source.values():
            for name, info in test["functions"].items():
                ss["function"][name] = ss["function"][name] or bool(info["execution_count"])

            for line, hits in test["lines"].items():
                ss["line"][line] = ss["line"][line] or bool(hits)

            for line, branches in test["branches"].items():
                for i, hits in enumerate(branches):
                    key = line + "_" + str(i)
                    ss["branch"][key] = ss["branch"][key] or bool(hits)

        for t in ["function", "line", "branch"]:
            totals[t]["total"] += len(ss[t].keys())
            totals[t]["hit"]   += sum(ss[t].values())

    for t in ["function", "line", "branch"]:
        if totals[t]["total"]:
            totals[t]["percent"] = 100 * totals[t]["hit"] / totals[t]["total"]

    total_processing_time = stopwatch()

    print("Total Processing Time: {:.3f}s".format(total_processing_time))
    print()
    print("Coverage Rates")
    print("==============")
    for t in ["function", "line", "branch"]:
        if totals[t]["total"]:
            print("{}: {:.1f}% ({} of {})".format(t, totals[t]["percent"], totals[t]["hit"], totals[t]["total"]))
        else:
            print("{}: {:.1f}% (not measured)".format(t, totals[t]["percent"]))
    print()

    for t in ["function", "line", "branch"]:
        arg_key = t + "_coverage_threshold"
        threshold = getattr(args, arg_key)
        if totals[t]["percent"] < threshold:
            print("{} coverage threshold failed ({:.1f}% < {:.1f}%)".format(t, totals[t]["percent"], threshold))
            setExitCode(arg_key)
        elif threshold > 0:
            print("{} coverage threshold passed ({}%)".format(t, threshold))

    # If there was an error along the way...
    if EXIT_CODE:
        sys.exit(EXIT_CODE)

if __name__ == '__main__':
    main()