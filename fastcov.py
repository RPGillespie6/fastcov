#!/usr/bin/env python3
"""
    Author: Bryan Gillespie

    A drop in replacement for lcov
"""

import os
import glob
import json
import argparse
import subprocess
import multiprocessing

MINIMUM_GCOV = (7,1,0)
IDEAL_GCOV   = (9,0,0)

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def getGcovVersion(gcov):
    p = subprocess.Popen([gcov, "-v"], stdout=subprocess.PIPE)
    output = p.communicate()[0].decode('UTF-8')
    p.wait()
    version = tuple(map(int, output.split("\n")[0].split()[-1].split(".")))
    return version

def getGcdaFiles(args):
    return glob.glob(os.path.join(args.directory, "**/*.gcda"), recursive=True)

def getGcovFiles(args):
    return glob.iglob(os.path.join(args.directory, "*.gcov"))

def filterGcovFiles(gcov):
    with open(gcov) as f:
        path = f.readline()[5:]
        for ex in args.exclude:
            if ex in path:
                return False
        return True

def processGcdas(gcov, jobs, gcda_files):
    chunk_size = int(len(gcda_files) / jobs) + 1

    processes = []
    for chunk in chunks(gcda_files, chunk_size):
        processes.append(subprocess.Popen([gcov, "-i"] + chunk, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    for p in processes:
        p.wait()

def processGcovLine(file, line):
    line_type, data = line.split(":", 1)
    if line_type == "lcount":
        num, count = data.split(",")
        hit = (count != 0)
        file["lines_hit"] += int(hit)
        file["lines"].append({
            "branches": [],
            "line_number": num,
            "count": count,
            "unexecuted_block": not hit
        })
    elif line_type == "function":
        num, count, name = data.split(",")
        hit = (count != 0)
        file["functions_hit"] += int(hit)
        file["functions"].append({
            "name": name,
            "execution_count": count,
            "start_line": num,
            "end_line": None,
            "blocks": None,
            "blocks_executed": None,
            "demangled_name": None
        })

def processGcov(files, gcov, exclude):
    with open(gcov) as f:
        path = f.readline()[5:].rstrip()
        for ex in exclude:
            if ex in path:
                return
        file = {
            "file": path,
            "functions": [],
            "functions_hit": 0,
            "lines": [],
            "lines_hit": 0
        }
        for line in f:
            processGcovLine(file, line.rstrip())
    files.append(file)

def processGcovs(gcov_files, exclude):
    files = []
    for gcov in gcov_files:
        processGcov(files, gcov, exclude)
    return files

def dumpToLcov(intermediate, output):
    with open(output, "w") as f:
        for file in intermediate:
            f.write("SF:%s\n" % file["file"])
            for function in file["functions"]:
                f.write("FN:%s,%s\n" % (function["start_line"], function["name"]))
                f.write("FNDA:%s,%s\n" % (function["execution_count"], function["name"]))
            f.write("FNF:%s\n" % len(file["functions"]))
            f.write("FNH:%s\n" % file["functions_hit"])
            for line in file["lines"]:
                f.write("DA:%s,%s\n" % (line["line_number"], line["count"]))
            f.write("LF:%s\n" % len(file["lines"]))
            f.write("LH:%s\n" % file["lines_hit"])
            f.write("end_of_record\n")

def dumpToGcovJson(intermediate, output):
    with open(output, "w") as f:
        json.dump(intermediate, f)

def main(args):
    # Need at least gcov 7.1.0 because of bug not allowing -i in conjunction with multiple files
    # See: https://github.com/gcc-mirror/gcc/commit/41da7513d5aaaff3a5651b40edeccc1e32ea785a
    current_gcov_version = getGcovVersion(args.gcov)
    if current_gcov_version < MINIMUM_GCOV:
        print("Minimum gcov version {} required, found {}".format(".".join(map(str, MINIMUM_GCOV)), ".".join(map(str, current_gcov_version))))
        exit(1)

    gcda_files = getGcdaFiles(args)
    processGcdas(args.gcov, args.jobs, gcda_files)
    gcov_files = getGcovFiles(args)
    i = processGcovs(gcov_files, args.exclude)

    if args.lcov:
        dumpToLcov(i, args.output)
    else:
        dumpToGcovJson(i, args.output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Program description here')
    parser.add_argument('-e', '--exclude', dest='exclude', nargs="+", default=[], help='List of prefixes to ignore when processing gcov files')
    parser.add_argument('-g', '--gcov', dest='gcov', default='gcov', help='which gcov binary to use')
    parser.add_argument('-d', '--directory', dest='directory', default=".", help='base directory')
    parser.add_argument('-j', '--jobs', dest='jobs', type=int, default=4*multiprocessing.cpu_count(), help='Number of parallel gcov to spawn (default: 4 * cpu_count)')
    parser.add_argument('-o', '--output', dest='output', default="coverage.json", help='Name of output file (default: coverage.json)')
    parser.add_argument('-i', '--lcov', dest='lcov', action="store_true", help='Output in lcov info format instead of gcov json')
    args = parser.parse_args()
    main(args)