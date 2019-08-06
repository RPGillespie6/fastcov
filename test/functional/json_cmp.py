#!/usr/bin/env python3

import sys
import json
import argparse

parser = argparse.ArgumentParser(description='Compare two json files')
parser.add_argument('file1', help="First JSON file")
parser.add_argument('file2', help="Second JSON file")
args = parser.parse_args()

with open(args.file1) as f1, open(args.file2) as f2:
    file1, file2 = json.load(f1), json.load(f2)
    if file1 != file2:
        sys.exit(1)