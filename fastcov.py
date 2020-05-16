#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2018-present, Bryan Gillespie
"""
    Author: Bryan Gillespie
    https://github.com/RPGillespie6/fastcov

    A massively parallel gcov wrapper for generating intermediate coverage formats fast

    The goal of fastcov is to generate code coverage intermediate formats as fast as possible,
    even for large projects with hundreds of gcda objects. The intermediate formats may then be
    consumed by a report generator such as lcov's genhtml, or a dedicated frontend such as coveralls.

    Sample Usage:
        $ cd build_dir
        $ ./fastcov.py --zerocounters
        $ <run unit tests>
        $ ./fastcov.py --exclude /usr/include test/ --lcov -o report.info
        $ genhtml -o code_coverage report.info
"""

import re
import os
import sys
import glob
import json
import time
import logging
import argparse
import threading
import subprocess
import multiprocessing

FASTCOV_VERSION = (1,5)
MINIMUM_PYTHON  = (3,5)
MINIMUM_GCOV    = (9,0,0)

# Interesting metrics
START_TIME = time.monotonic()
GCOVS_TOTAL = []
GCOVS_SKIPPED = []

# Disable all logging in case developers are using this as a module
logging.disable(level=logging.CRITICAL)

class FastcovFormatter(logging.Formatter):
    def format(self, record):
        record.levelname = record.levelname.lower()
        log_message = super(FastcovFormatter, self).format(record)
        return "[{:.3f}s] {}".format(stopwatch(), log_message)

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def stopwatch():
    """Return number of seconds since last time this was called"""
    global START_TIME
    end_time   = time.monotonic()
    delta      = end_time - START_TIME
    START_TIME = end_time
    return delta

def parseVersionFromLine(version_str):
    """Given a string containing a dotted integer version, parse out integers and return as tuple"""
    version = re.search(r'(\d+\.\d+\.\d+)', version_str)

    if not version:
        return (0,0,0)

    return tuple(map(int, version.group(1).split(".")))

def getGcovVersion(gcov):
    p = subprocess.Popen([gcov, "-v"], stdout=subprocess.PIPE)
    output = p.communicate()[0].decode('UTF-8')
    p.wait()
    return parseVersionFromLine(output.split("\n")[0])

def removeFiles(files):
    for file in files:
        os.remove(file)

def getFilteredCoverageFiles(coverage_files, exclude):
    def excludeGcda(gcda):
        for ex in exclude:
            if ex in gcda:
                logging.debug("Omitting %s due to '--exclude-gcda %s'", gcda, ex)
                return False
        return True
    return list(filter(excludeGcda, coverage_files))

def findCoverageFiles(cwd, coverage_files, use_gcno):
    coverage_type = "user provided"
    if not coverage_files:
        coverage_type = "gcno" if use_gcno else "gcda"
        coverage_files = glob.glob(os.path.join(os.path.abspath(cwd), "**/*." + coverage_type), recursive=True)

    logging.info("Found {} coverage files ({})".format(len(coverage_files), coverage_type))
    logging.debug("Coverage files found:\n    %s", "\n    ".join(coverage_files))
    return coverage_files

def gcovWorker(cwd, gcov, files, chunk, gcov_filter_options, branch_coverage):
    gcov_args = "-it"
    if branch_coverage:
        gcov_args += "b"

    p = subprocess.Popen([gcov, gcov_args] + chunk, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for line in iter(p.stdout.readline, b''):
        intermediate_json = json.loads(line.decode(sys.stdout.encoding))
        intermediate_json_files = processGcovs(cwd, intermediate_json["files"], gcov_filter_options)
        for f in intermediate_json_files:
            files.append(f) #thread safe, there might be a better way to do this though
        GCOVS_TOTAL.append(len(intermediate_json["files"]))
        GCOVS_SKIPPED.append(len(intermediate_json["files"])-len(intermediate_json_files))
    p.wait()

def processGcdas(cwd, gcov, jobs, coverage_files, gcov_filter_options, branch_coverage, min_chunk_size):
    chunk_size = max(min_chunk_size, int(len(coverage_files) / jobs) + 1)

    threads = []
    intermediate_json_files = []
    for chunk in chunks(coverage_files, chunk_size):
        t = threading.Thread(target=gcovWorker, args=(cwd, gcov, intermediate_json_files, chunk, gcov_filter_options, branch_coverage))
        threads.append(t)
        t.start()

    logging.info("Spawned {} gcov threads, each processing at most {} coverage files".format(len(threads), chunk_size))
    for t in threads:
        t.join()

    return intermediate_json_files

def processGcov(cwd, gcov, files, gcov_filter_options):
    # Add absolute path
    gcov["file_abs"] = os.path.abspath(os.path.join(cwd, gcov["file"]))

    # If explicit sources were passed, check for match
    if gcov_filter_options["sources"]:
        if gcov["file_abs"] in gcov_filter_options["sources"]:
            files.append(gcov)
            logging.debug("Accepted coverage for '%s'", gcov["file_abs"])
        else:
            logging.debug("Skipping coverage for '%s' due to option '--source-files'", gcov["file_abs"])
        return

    # Check exclude filter
    for ex in gcov_filter_options["exclude"]:
        if ex in gcov["file_abs"]:
            logging.debug("Skipping coverage for '%s' due to option '--exclude %s'", gcov["file_abs"], ex)
            return

    # Check include filter
    if gcov_filter_options["include"]:
        included = False
        for ex in gcov_filter_options["include"]:
            if ex in gcov["file_abs"]:
                included = True
                files.append(gcov)
                logging.debug("Accepted coverage for '%s'", gcov["file_abs"])
                break

        if not included:
            logging.debug("Skipping coverage for '%s' due to option '--include %s'", gcov["file_abs"], " ".join(gcov_filter_options["include"]))

        return

    files.append(gcov)
    logging.debug("Accepted coverage for '%s'", gcov["file_abs"])

def processGcovs(cwd, gcov_files, gcov_filter_options):
    files = []
    for gcov in gcov_files:
        processGcov(cwd, gcov, files, gcov_filter_options)
    return files

def dumpBranchCoverageToLcovInfo(f, branches):
    branch_miss = 0
    branch_found = 0
    brda = []
    for line_num, branch_counts in branches.items():
        for i, count in enumerate(branch_counts):
            # Branch (<line number>, <block number>, <branch number>, <taken>)
            brda.append((line_num, int(i/2), i, count))
            branch_miss += int(count == 0)
            branch_found += 1
    for v in sorted(brda):
        f.write("BRDA:{},{},{},{}\n".format(*v))
    f.write("BRF:{}\n".format(branch_found))                # Branches Found
    f.write("BRH:{}\n".format(branch_found - branch_miss))  # Branches Hit

def dumpToLcovInfo(fastcov_json, output):
    with open(output, "w") as f:
        sources = fastcov_json["sources"]
        for sf in sorted(sources.keys()):
            for tn in sorted(sources[sf].keys()):
                data = sources[sf][tn]
                f.write("TN:{}\n".format(tn)) #Test Name - used mainly in conjuction with genhtml --show-details
                f.write("SF:{}\n".format(sf)) #Source File

                fn_miss = 0
                fn = []
                fnda = []
                for function, fdata in data["functions"].items():
                    fn.append((fdata["start_line"], function))  # Function Start Line
                    fnda.append((fdata["execution_count"], function))  # Function Hits
                    fn_miss += int(fdata["execution_count"] == 0)
                # NOTE: lcov sorts FN, but not FNDA.
                for v in sorted(fn):
                    f.write("FN:{},{}\n".format(*v))
                for v in sorted(fnda):
                    f.write("FNDA:{},{}\n".format(*v))
                f.write("FNF:{}\n".format(len(data["functions"])))               #Functions Found
                f.write("FNH:{}\n".format((len(data["functions"]) - fn_miss)))   #Functions Hit

                if data["branches"]:
                    dumpBranchCoverageToLcovInfo(f, data["branches"])

                line_miss = 0
                da = []
                for line_num, count in data["lines"].items():
                    da.append((line_num, count))
                    line_miss += int(count == 0)
                for v in sorted(da):
                    f.write("DA:{},{}\n".format(*v))  # Line
                f.write("LF:{}\n".format(len(data["lines"])))                 #Lines Found
                f.write("LH:{}\n".format((len(data["lines"]) - line_miss)))   #Lines Hit
                f.write("end_of_record\n")

def getSourceLines(source, fallback_encodings=[]):
    """Return a list of lines from the provided source, trying to decode with fallback encodings if the default fails"""
    default_encoding = sys.getdefaultencoding()
    for encoding in [default_encoding] + fallback_encodings:
        try:
            with open(source, encoding=encoding) as f:
                return f.readlines()
        except UnicodeDecodeError:
            pass

    logging.warning("Could not decode '{}' with {} or fallback encodings ({}); ignoring errors".format(source, default_encoding, ",".join(fallback_encodings)))
    with open(source, errors="ignore") as f:
        return f.readlines()

def exclMarkerWorker(fastcov_sources, chunk, exclude_branches_sw, include_branches_sw, fallback_encodings):
    for source in chunk:
        start_line = 0
        end_line = 0
        # Start enumeration at line 1 because the first line of the file is line 1 not 0
        for i, line in enumerate(getSourceLines(source, fallback_encodings), 1):
            # Cycle through test names (likely only 1)
            for test_name in fastcov_sources[source]:
                fastcov_data = fastcov_sources[source][test_name]

                if i in fastcov_data["branches"]:
                    del_exclude_br = exclude_branches_sw and any(line.lstrip().startswith(e) for e in exclude_branches_sw)
                    del_include_br = include_branches_sw and all(not line.lstrip().startswith(e) for e in include_branches_sw)
                    if del_exclude_br or del_include_br:
                        del fastcov_data["branches"][i]

                if "LCOV_EXCL" not in line:
                    continue

                if "LCOV_EXCL_LINE" in line:
                    for key in ["lines", "branches"]:
                        if i in fastcov_data[key]:
                            del fastcov_data[key][i]
                elif "LCOV_EXCL_START" in line:
                    start_line = i
                elif "LCOV_EXCL_STOP" in line:
                    end_line = i

                    if not start_line:
                        end_line = 0
                        continue

                    for key in ["lines", "branches"]:
                        for line_num in list(fastcov_data[key].keys()):
                            if start_line <= line_num <= end_line:
                                del fastcov_data[key][line_num]

                    start_line = end_line = 0
                elif "LCOV_EXCL_BR_LINE" in line:
                    if i in fastcov_data["branches"]:
                        del fastcov_data["branches"][i]

def scanExclusionMarkers(fastcov_json, jobs, exclude_branches_sw, include_branches_sw, min_chunk_size, fallback_encodings):
    chunk_size = max(min_chunk_size, int(len(fastcov_json["sources"]) / jobs) + 1)

    threads = []
    for chunk in chunks(list(fastcov_json["sources"].keys()), chunk_size):
        t = threading.Thread(target=exclMarkerWorker, args=(fastcov_json["sources"], chunk, exclude_branches_sw, include_branches_sw, fallback_encodings))
        threads.append(t)
        t.start()

    logging.info("Spawned {} threads each scanning at most {} source files".format(len(threads), chunk_size))
    for t in threads:
        t.join()

def distillFunction(function_raw, functions):
    function_name   = function_raw["name"]
    # NOTE: need to explicitly cast all counts coming from gcov to int - this is because gcov's json library
    # will pass as scientific notation (i.e. 12+e45)
    start_line      = int(function_raw["start_line"])
    execution_count = int(function_raw["execution_count"])
    if function_name not in functions:
        functions[function_name] = {
            "start_line": start_line,
            "execution_count": execution_count
        }
    else:
        functions[function_name]["execution_count"] += execution_count

def emptyBranchSet(branch1, branch2):
    return (branch1["count"] == 0 and branch2["count"] == 0)

def matchingBranchSet(branch1, branch2):
    return (branch1["count"] == branch2["count"])

def filterExceptionalBranches(branches):
    filtered_branches = []
    exception_branch = False
    for i in range(0, len(branches), 2):
        if i+1 >= len(branches):
            filtered_branches.append(branches[i])
            break

        # Filter exceptional branch noise
        if branches[i+1]["throw"]:
            exception_branch = True
            continue

        # Filter initializer list noise
        if exception_branch and emptyBranchSet(branches[i], branches[i+1]) and len(filtered_branches) >= 2 and matchingBranchSet(filtered_branches[-1], filtered_branches[-2]):
            return []

        filtered_branches.append(branches[i])
        filtered_branches.append(branches[i+1])

    return filtered_branches

def distillLine(line_raw, lines, branches, include_exceptional_branches):
    line_number = int(line_raw["line_number"])
    count       = int(line_raw["count"])
    if line_number not in lines:
        lines[line_number] = count
    else:
        lines[line_number] += count

    # Filter out exceptional branches by default unless requested otherwise
    if not include_exceptional_branches:
        line_raw["branches"] = filterExceptionalBranches(line_raw["branches"])

    # Increment all branch counts
    for i, branch in enumerate(line_raw["branches"]):
        if line_number not in branches:
            branches[line_number] = []
        blen = len(branches[line_number])
        glen = len(line_raw["branches"])
        if blen < glen:
            branches[line_number] += [0] * (glen - blen)
        branches[line_number][i] += int(branch["count"])

def distillSource(source_raw, sources, test_name, include_exceptional_branches):
    source_name = source_raw["file_abs"]
    if source_name not in sources:
        sources[source_name] = {
            test_name: {
                "functions": {},
                "branches": {},
                "lines": {}
            }
        }

    for function in source_raw["functions"]:
        distillFunction(function, sources[source_name][test_name]["functions"])

    for line in source_raw["lines"]:
        distillLine(line, sources[source_name][test_name]["lines"], sources[source_name][test_name]["branches"], include_exceptional_branches)

def distillReport(report_raw, args):
    report_json = {
        "sources": {}
    }

    for source in report_raw:
        distillSource(source, report_json["sources"], args.test_name, args.xbranchcoverage)

    return report_json

def dumpToJson(intermediate, output):
    with open(output, "w") as f:
        json.dump(intermediate, f)

def getGcovFilterOptions(args):
    return {
        "sources": set([os.path.abspath(s) for s in args.sources]), #Make paths absolute, use set for fast lookups
        "include": args.includepost,
        "exclude": args.excludepost,
    }

def addDicts(dict1, dict2):
    """Add dicts together by value. i.e. addDicts({"a":1,"b":0}, {"a":2}) == {"a":3,"b":0}"""
    result = {k:v for k,v in dict1.items()}
    for k,v in dict2.items():
        if k in result:
            result[k] += v
        else:
            result[k] = v

    return result

def addLists(list1, list2):
    """Add lists together by value. i.e. addLists([1,1], [2,2]) == [3,3]"""
    if len(list1) == len(list2):
        return [b1 + b2 for b1, b2 in zip(list1, list2)]
    else:
        # One report had different number branch measurements than the other, print a warning
        logging.warning("Possible loss of correctness. Different number of branches for same line when combining reports ({} vs {})\n".format(list1, list2))
        return list1 if len(list1) > len(list2) else list2

def combineReports(base, overlay):
    for source, scov in overlay["sources"].items():
        # Combine Source Coverage
        if source not in base["sources"]:
            base["sources"][source] = scov
            continue

        for test_name, tcov in scov.items():
            # Combine Source Test Name Coverage
            if test_name not in base["sources"][source]:
                base["sources"][source][test_name] = tcov
                continue

            # Drill down and create convenience variable
            base_data = base["sources"][source][test_name]

            # Combine Line Coverage
            base_data["lines"] = addDicts(base_data["lines"], tcov["lines"])

            # Combine Branch Coverage
            for branch, cov in tcov["branches"].items():
                if branch not in base_data["branches"]:
                    base_data["branches"][branch] = cov
                else:
                    base_data["branches"][branch] = addLists(base_data["branches"][branch], cov)

            # Combine Function Coverage
            for function, cov in tcov["functions"].items():
                if function not in base_data["functions"]:
                    base_data["functions"][function] = cov
                else:
                    base_data["functions"][function]["execution_count"] += cov["execution_count"]

def parseInfo(path):
    """Parse an lcov .info file into fastcov json"""
    fastcov_json = {
        "sources": {}
    }

    with open(path) as f:
        for line in f:
            if line.startswith("TN:"):
                current_test_name = line[3:].strip()
            elif line.startswith("SF:"):
                current_sf = line[3:].strip()
                fastcov_json["sources"][current_sf] = {
                    current_test_name: {
                        "functions": {},
                        "branches": {},
                        "lines": {},
                    }
                }
                current_data = fastcov_json["sources"][current_sf][current_test_name]
            elif line.startswith("FN:"):
                line_num, function_name = line[3:].strip().split(",")
                current_data["functions"][function_name] = {}
                current_data["functions"][function_name]["start_line"] = int(line_num)
            elif line.startswith("FNDA:"):
                count, function_name = line[5:].strip().split(",")
                current_data["functions"][function_name]["execution_count"] = int(count)
            elif line.startswith("DA:"):
                line_num, count = line[3:].strip().split(",")
                current_data["lines"][line_num] = int(count)
            elif line.startswith("BRDA:"):
                branch_tokens = line[5:].strip().split(",")
                line_num, count = branch_tokens[0], branch_tokens[-1]
                if line_num not in current_data["branches"]:
                    current_data["branches"][line_num] = []
                current_data["branches"][line_num].append(int(count))

    return fastcov_json

def convertKeysToInt(report):
    for source in report["sources"].keys():
        for test_name in report["sources"][source].keys():
            report_data = report["sources"][source][test_name]
            report_data["lines"]    = {int(k):v for k,v in report_data["lines"].items()}
            report_data["branches"] = {int(k):v for k,v in report_data["branches"].items()}

def parseAndCombine(paths):
    base_report = {}

    for path in paths:
        if path.endswith(".json"):
            with open(path) as f:
                report = json.load(f)
        elif path.endswith(".info"):
            report = parseInfo(path)
        else:
            sys.stderr.write("Currently only fastcov .json and lcov .info supported for combine operations, aborting due to {}...\n".format(path))
            sys.exit(3)

        # In order for sorting to work later when we serialize,
        # make sure integer keys are int
        convertKeysToInt(report)

        if not base_report:
            base_report = report
            logging.info("Setting {} as base report".format(path))
        else:
            combineReports(base_report, report)
            logging.info("Adding {} to base report".format(path))

    return base_report

def combineCoverageFiles(args):
    logging.info("Performing combine operation")
    fastcov_json = parseAndCombine(args.combine)
    dumpFile(fastcov_json, args)

def dumpFile(fastcov_json, args):
    if args.lcov:
        dumpToLcovInfo(fastcov_json, args.output)
        logging.info("Created lcov info file '{}'".format(args.output))
    else:
        dumpToJson(fastcov_json, args.output)
        logging.info("Created fastcov json file '{}'".format(args.output))

def tupleToDotted(tup):
    return ".".join(map(str, tup))

def parseArgs():
    parser = argparse.ArgumentParser(description='A parallel gcov wrapper for fast coverage report generation')
    parser.add_argument('-z', '--zerocounters', dest='zerocounters', action="store_true", help='Recursively delete all gcda files')

    # Enable Branch Coverage
    parser.add_argument('-b', '--branch-coverage', dest='branchcoverage', action="store_true", help='Include only the most useful branches in the coverage report.')
    parser.add_argument('-B', '--exceptional-branch-coverage', dest='xbranchcoverage', action="store_true", help='Include ALL branches in the coverage report (including potentially noisy exceptional branches).')
    parser.add_argument('-A', '--exclude-br-lines-starting-with', dest='exclude_branches_sw', nargs="+", metavar='', default=[], help='Exclude branches from lines starting with one of the provided strings (i.e. assert, return, etc.)')
    parser.add_argument('-a', '--include-br-lines-starting-with', dest='include_branches_sw', nargs="+", metavar='', default=[], help='Include only branches from lines starting with one of the provided strings (i.e. if, else, while, etc.)')

    # Capture untested file coverage as well via gcno
    parser.add_argument('-n', '--process-gcno', dest='use_gcno', action="store_true", help='Process both gcno and gcda coverage files. This option is useful for capturing untested files in the coverage report.')

    # Filtering Options
    parser.add_argument('-s', '--source-files', dest='sources',     nargs="+", metavar='', default=[], help='Filter: Specify exactly which source files should be included in the final report. Paths must be either absolute or relative to current directory.')
    parser.add_argument('-e', '--exclude',      dest='excludepost', nargs="+", metavar='', default=[], help='Filter: Exclude source files from final report if they contain one of the provided substrings (i.e. /usr/include test/, etc.)')
    parser.add_argument('-i', '--include',      dest='includepost', nargs="+", metavar='', default=[], help='Filter: Only include source files in final report that contain one of the provided substrings (i.e. src/ etc.)')
    parser.add_argument('-f', '--gcda-files',   dest='coverage_files',  nargs="+", metavar='', default=[], help='Filter: Specify exactly which gcda or gcno files should be processed. Note that specifying gcno causes both gcno and gcda to be processed.')
    parser.add_argument('-E', '--exclude-gcda', dest='excludepre',  nargs="+", metavar='', default=[], help='Filter: Exclude gcda or gcno files from being processed via simple find matching (not regex)')

    parser.add_argument('-g', '--gcov', dest='gcov', default='gcov', help='Which gcov binary to use')

    parser.add_argument('-d', '--search-directory', dest='directory', default=".", help='Base directory to recursively search for gcda files (default: .)')
    parser.add_argument('-c', '--compiler-directory', dest='cdirectory', default=".", help='Base directory compiler was invoked from (default: .) \
                                                                                            This needs to be set if invoking fastcov from somewhere other than the base compiler directory.')

    parser.add_argument('-j', '--jobs', dest='jobs', type=int, default=multiprocessing.cpu_count(), help='Number of parallel gcov to spawn (default: {}).'.format(multiprocessing.cpu_count()))
    parser.add_argument('-m', '--minimum-chunk-size', dest='minimum_chunk', type=int, default=5,    help='Minimum number of files a thread should process (default: 5). \
                                                                                                          If you have only 4 gcda files but they are monstrously huge, you could change this value to a 1 so that each thread will only process 1 gcda. Otherwise fastcov will spawn only 1 thread to process all of them.')

    parser.add_argument('-F', '--fallback-encodings', dest='fallback_encodings', nargs="+", metavar='', default=[], help='List of encodings to try if opening a source file with the default fails (i.e. latin1, etc.). This option is not usually needed.')

    parser.add_argument('-l', '--lcov',   dest='lcov',   action="store_true",     help='Output in lcov info format instead of fastcov json')
    parser.add_argument('-o', '--output', dest='output', default="coverage.json", help='Name of output file (default: coverage.json)')
    parser.add_argument('-q', '--quiet',  dest='quiet',  action="store_true",     help='Suppress output to stdout')

    parser.add_argument('-t', '--test-name',     dest='test_name', default="", help='Specify a test name for the coverage. Equivalent to lcov\'s `-t`.')
    parser.add_argument('-C', '--add-tracefile', dest='combine',   nargs="+",  help='Combine multiple coverage files into one. If this flag is specified, fastcov will do a combine operation instead invoking gcov. Equivalent to lcov\'s `-a`.')

    parser.add_argument('-V', '--verbose', dest="verbose", action="store_true", help="Print more detailed information about what fastcov is doing")
    parser.add_argument('-v', '--version', action="version", version='%(prog)s {version}'.format(version=__version__), help="Show program's version number and exit")

    args = parser.parse_args()

    return args

def checkPythonVersion(version):
    """Exit if the provided python version is less than the supported version"""
    if version < MINIMUM_PYTHON:
        sys.stderr.write("Minimum python version {} required, found {}\n".format(tupleToDotted(MINIMUM_PYTHON), tupleToDotted(version)))
        sys.exit(1)

def checkGcovVersion(version):
    """Exit if the provided gcov version is less than the supported version"""
    if version < MINIMUM_GCOV:
        sys.stderr.write("Minimum gcov version {} required, found {}\n".format(tupleToDotted(MINIMUM_GCOV), tupleToDotted(version)))
        sys.exit(2)

def setupLogging(quiet, verbose):
    handler = logging.StreamHandler()
    handler.setFormatter(FastcovFormatter("[%(levelname)s]: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    if not quiet:
        logging.disable(level=logging.NOTSET) # Re-enable logging

    if verbose:
        root.setLevel(logging.DEBUG)

def main():
    args = parseArgs()

    # Setup logging
    setupLogging(args.quiet, args.verbose)

    # Need at least python 3.5 because of use of recursive glob
    checkPythonVersion(sys.version_info[0:2])

    # Combine operation?
    if args.combine:
        combineCoverageFiles(args)
        return

    # Need at least gcov 9.0.0 because that's when gcov JSON and stdout streaming was introduced
    checkGcovVersion(getGcovVersion(args.gcov))

    # Get list of gcda files to process
    coverage_files = findCoverageFiles(args.directory, args.coverage_files, args.use_gcno)

    # If gcda/gcno filtering is enabled, filter them out now
    if args.excludepre:
        coverage_files = getFilteredCoverageFiles(coverage_files, args.excludepre)
        logging.info("Found {} coverage files after filtering".format(len(coverage_files)))

    # We "zero" the "counters" by simply deleting all gcda files
    if args.zerocounters:
        removeFiles(coverage_files)
        logging.info("Removed {} .gcda files".format(len(coverage_files)))
        return

    # Fire up one gcov per cpu and start processing gcdas
    gcov_filter_options = getGcovFilterOptions(args)
    intermediate_json_files = processGcdas(args.cdirectory, args.gcov, args.jobs, coverage_files, gcov_filter_options, args.branchcoverage or args.xbranchcoverage, args.minimum_chunk)

    # Summarize processing results
    gcov_total = sum(GCOVS_TOTAL)
    gcov_skipped = sum(GCOVS_SKIPPED)
    logging.info("Processed {} .gcov files ({} total, {} skipped)".format(gcov_total - gcov_skipped, gcov_total, gcov_skipped))

    # Distill all the extraneous info gcov gives us down to the core report
    fastcov_json = distillReport(intermediate_json_files, args)
    logging.info("Aggregated raw gcov JSON into fastcov JSON report")
    logging.debug("Final report will contain coverage for the following %d source files:\n    %s", len(fastcov_json["sources"]), "\n    ".join(fastcov_json["sources"]))

    # Scan for exclusion markers
    scanExclusionMarkers(fastcov_json, args.jobs, args.exclude_branches_sw, args.include_branches_sw, args.minimum_chunk, args.fallback_encodings)
    logging.info("Scanned {} source files for exclusion markers".format(len(fastcov_json["sources"])))

    # Dump to desired file format
    dumpFile(fastcov_json, args)

# Set package version... it's way down here so that we can call tupleToDotted
__version__ = tupleToDotted(FASTCOV_VERSION)

if __name__ == '__main__':
    main()
