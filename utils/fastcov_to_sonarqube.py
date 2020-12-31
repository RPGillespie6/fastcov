#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2020-present, Bryan Gillespie

SCRIPT_DESCRIPTION = """
    Author: Bryan Gillespie
    https://github.com/RPGillespie6/fastcov

    A simple utility for converting fastcov JSON format to Sonarqube generic coverage format (https://docs.sonarqube.org/latest/analysis/generic-test/).

    Sample Usage:
        $ ./fastcov_to_sonarqube.py coverage.json -o sonarcube_coverage.xml --pretty
"""

import json
import time
import argparse
from collections import defaultdict

import xml.dom.minidom # For pretty printing
import xml.etree.ElementTree as ET

# Interesting metrics
START_TIME    = time.monotonic()

def stopwatch():
    """Return number of seconds since last time this was called."""
    global START_TIME
    end_time   = time.monotonic()
    delta      = end_time - START_TIME
    START_TIME = end_time
    return delta

def parseArgs():
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument('fastcov_coverage', help='The fastcov coverage file to convert')
    parser.add_argument('-p', '--pretty', action="store_true", help='Pretty print XML')
    parser.add_argument('-o', '--output', default="sonarqube_coverage.xml", help='Name of the output file')
    return parser.parse_args()

def main():
    args = parseArgs()

    with open(args.fastcov_coverage) as f:
        coverage = json.load(f)

    root = ET.Element('coverage')
    root.set("version", "1")

    for path, source in coverage["sources"].items():
        source_file = ET.SubElement(root, 'file')
        source_file.set("path", path)

        ss = {
            "function": defaultdict(bool), # Not currently used, but maybe in future Sonarqube version
            "line": defaultdict(bool),
            "branch": defaultdict(lambda: defaultdict(bool)),
        }

        for test in source.values():
            for name, info in test["functions"].items():
                ss["function"][name] = ss["function"][name] or bool(info["execution_count"])

            for line, hits in test["lines"].items():
                ss["line"][line] = ss["line"][line] or bool(hits)

            for line, branches in test["branches"].items():
                for i, hits in enumerate(branches):
                    ss["branch"][line][str(i)] = ss["branch"][line][str(i)] or bool(hits)

        for line, covered in ss["line"].items():
            source_line = ET.SubElement(source_file, 'lineToCover')
            source_line.set("lineNumber", line)
            source_line.set("covered", str(covered).lower())

            if line in ss["branch"]:
                source_line.set("branchesToCover", str(len(ss["branch"][line])))
                source_line.set("coveredBranches", str(sum(ss["branch"][line].values())))

    total_processing_time = stopwatch()

    with open(args.output, "w") as f:
        doc_string = ET.tostring(root, encoding="unicode")

        if args.pretty:
            # .childNodes[0] nonsense is to eliminate xml version tag that minidom auto-injects
            doc_string = xml.dom.minidom.parseString(doc_string).childNodes[0].toprettyxml()

        f.write(doc_string)

    print("Total Processing Time: {:.3f}s".format(total_processing_time))
    print("Results written to: {}".format(args.output))

if __name__ == '__main__':
    main()