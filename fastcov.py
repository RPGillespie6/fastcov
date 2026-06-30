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

from __future__ import annotations

import re
import os
import sys
import glob
import json
import time
import fnmatch
import logging
import argparse
import tempfile
import shutil
import subprocess
import multiprocessing
from pathlib import Path
from collections.abc import Iterable
from typing import Dict, List, Set, Tuple, TypedDict, Optional, Union, cast, Any


# ==================== Type Definitions ====================

class GcovBranch(TypedDict):
    """Branch data from gcov JSON output."""
    count: int
    fallthrough: bool
    throw: bool


class GcovLine(TypedDict):
    """Line data from gcov JSON output."""
    line_number: int
    count: int
    branches: List[GcovBranch]
    function_name: Optional[str]


class GcovFunction(TypedDict):
    """Function data from gcov JSON output."""
    name: str
    start_line: int
    execution_count: int


class GcovFile(TypedDict, total=False):
    """File data from gcov JSON output - file_abs added by fastcov."""
    file: str
    functions: List[GcovFunction]
    lines: List[GcovLine]
    file_abs: str  # Added by fastcov during processing


class GcovJsonOutput(TypedDict):
    """Complete gcov JSON output structure."""
    files: List[GcovFile]
    current_working_directory: str
    gcov_version: str


class FunctionData(TypedDict):
    """Function coverage data in fastcov internal format."""
    start_line: int
    execution_count: int


class TestCoverage(TypedDict):
    """Test coverage data for a single source file and test name."""
    functions: Dict[str, FunctionData]
    branches: Dict[int, List[int]]
    lines: Dict[int, int]


class FastcovReport(TypedDict):
    """Fastcov internal report format."""
    sources: Dict[str, Dict[str, TestCoverage]]


class GcovFilterOptions(TypedDict):
    """Filtering options for gcov processing."""
    sources: Set[str]
    include: List[str]
    exclude: List[str]
    exclude_glob: List[str]


# ==================== Globals ====================

FASTCOV_VERSION: Tuple[int, int] = (1, 18)
MINIMUM_PYTHON: Tuple[int, int] = (3, 8)
MINIMUM_GCOV: Tuple[int, int, int] = (9, 0, 0)

# Interesting metrics
START_TIME: float = time.monotonic()
GCOVS_TOTAL: int = 0
GCOVS_SKIPPED: int = 0

# Gcov Coverage File Extensions
GCOV_GCNO_EXT: str = ".gcno"  # gcno = "[gc]ov [no]te"
GCOV_GCDA_EXT: str = ".gcda"  # gcda = "[gc]ov [da]ta"

# For when things go wrong...
EXIT_CODE: int = 0
EXIT_CODES: Dict[str, int] = {
    "gcov_version": 3,
    "python_version": 4,
    "unsupported_coverage_format": 5,
    "excl_not_found": 6,
    "bad_chunk_file": 7,
    "missing_json_key": 8,
    "no_coverage_files": 9,
}

# Disable all logging in case developers are using this as a module
logging.disable(level=logging.CRITICAL)


class FastcovFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.levelname = record.levelname.lower()
        log_message = super().format(record)
        return f"[{stopwatch():.3f}s] {log_message}"


class DiffParseError(Exception):
    """Custom exception for errors while parsing diff files."""
    pass


class DiffParser:
    """Parser for unified diff files to support --diff-filter option."""

    def _refinePaths(self, diff_metadata: Dict[str, Set[int]], diff_base_dir: str) -> None:
        diff_metadata.pop('/dev/null', None)
        diff_metadata.pop('', None)
        for key, value in list(diff_metadata.items()):
            diff_metadata.pop(key)
            # sources without added lines will be excluded
            if value:
                newpath = os.path.join(diff_base_dir, key) if diff_base_dir else os.path.abspath(key)
                diff_metadata[newpath] = value

    def _parseTargetFile(self, line_with_target_file: str) -> str:
        # f.e. '+++ b/README.md1' or '+++ b/README.md1   timestamp'
        target_source = line_with_target_file[4:].partition('\t')[0].strip()
        target_source = target_source[2:] if target_source.startswith('b/') else target_source
        return target_source

    def _parseHunkBoundaries(self, line_with_hunk_boundaries: str, line_index: int) -> Tuple[int, int, int, int]:
        # f.e. '@@ -121,4 +122,4 @@ ...'
        lines_info = line_with_hunk_boundaries[3:].partition("@@")[0].strip().split(' ')
        if len(lines_info) != 2:
            raise DiffParseError(f"Found invalid hunk. Line #{line_index}. {line_with_hunk_boundaries}")

        # Target lines info
        target_lines_info = lines_info[1].strip('+').partition(',')
        target_line_current = int(target_lines_info[0])
        target_lines_count = int(target_lines_info[2]) if target_lines_info[2] else 1

        # Source lines info
        source_lines_info = lines_info[0].strip('-').partition(',')
        source_line_current = int(source_lines_info[0])
        source_lines_count = int(source_lines_info[2]) if source_lines_info[2] else 1

        return target_line_current, target_lines_count, source_line_current, source_lines_count

    def parseDiffFile(
        self,
        diff_file: str,
        diff_base_dir: str,
        fallback_encodings: Optional[List[str]] = None
    ) -> Dict[str, Set[int]]:
        if fallback_encodings is None:
            fallback_encodings = []

        diff_metadata: Dict[str, Set[int]] = {}
        target_source: Optional[str] = None
        target_hunk: Set[int] = set()
        target_line_current: int = 0
        target_line_end: int = 0
        source_line_current: int = 0
        source_line_end: int = 0
        found_hunk: bool = False

        for i, line in enumerate(getSourceLines(diff_file, fallback_encodings), 1):
            line = line.rstrip()

            if not found_hunk:
                if line.startswith('+++ '):
                    target_source = self._parseTargetFile(line)
                elif line.startswith('@@ '):
                    (target_line_current, target_lines_count,
                     source_line_current, source_lines_count) = self._parseHunkBoundaries(line, i)
                    target_line_end = target_line_current + target_lines_count
                    source_line_end = source_line_current + source_lines_count
                    target_hunk = set()
                    found_hunk = True
                continue

            if target_line_current > target_line_end or source_line_current > source_line_end:
                raise DiffParseError(f"Hunk longer than expected. Line #{i}. {line}")

            if line.startswith('+'):
                target_hunk.add(target_line_current)
                target_line_current += 1
            elif line.startswith(' ') or line == '':
                target_line_current += 1
                source_line_current += 1
            elif line.startswith('-'):
                source_line_current += 1
            elif not line.startswith('\\'):  # No newline at end of file
                raise DiffParseError(f"Found unrecognized hunk line type. Line #{i}. {line}")

            if target_line_current == target_line_end and source_line_current == source_line_end:
                if target_source is not None:
                    if target_source in diff_metadata:
                        diff_metadata[target_source] = target_hunk.union(diff_metadata[target_source])
                    else:
                        diff_metadata[target_source] = target_hunk
                target_hunk = set()
                found_hunk = False

        if target_line_current != target_line_end or source_line_current != source_line_end:
            raise DiffParseError(
                f"Unexpected end of file. Expected hunk with {target_line_end - target_line_current} "
                f"target lines, {source_line_end - source_line_current} source lines"
            )

        self._refinePaths(diff_metadata, diff_base_dir)
        return diff_metadata

    def filterByDiff(
        self,
        diff_file: str,
        diff_base_dir: str,
        fastcov_json: FastcovReport,
        fallback_encodings: Optional[List[str]] = None
    ) -> FastcovReport:
        if fallback_encodings is None:
            fallback_encodings = []

        diff_metadata = self.parseDiffFile(diff_file, diff_base_dir, fallback_encodings)

        logging.debug(f"Include only next files: {list(diff_metadata.keys())}")

        excluded_files_count = 0
        excluded_lines_count = 0

        for source in list(fastcov_json["sources"].keys()):
            diff_lines = diff_metadata.get(source)
            if not diff_lines:
                excluded_files_count += 1
                logging.debug(f"Exclude {source} according to diff file")
                fastcov_json["sources"].pop(source)
                continue

            for test_name, report_data in list(fastcov_json["sources"][source].items()):
                # No info about functions boundaries, removing all
                for function in list(report_data["functions"].keys()):
                    report_data["functions"].pop(function, None)

                for line in list(report_data["lines"].keys()):
                    if line not in diff_lines:
                        excluded_lines_count += 1
                        report_data["lines"].pop(line)

                for branch_line in list(report_data["branches"].keys()):
                    if branch_line not in diff_lines:
                        report_data["branches"].pop(branch_line)

                if len(report_data["lines"]) == 0:
                    fastcov_json["sources"][source].pop(test_name)

            if len(fastcov_json["sources"][source]) == 0:
                excluded_files_count += 1
                logging.debug(f"Exclude {source} file as it has no lines due to diff filter")
                fastcov_json["sources"].pop(source)

        logging.info(f"Excluded {excluded_files_count} files and {excluded_lines_count} lines according to diff file")
        return fastcov_json


def chunks(l: List[Any], n: int) -> Iterable[List[Any]]:
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def setExitCode(key: str) -> None:
    """Set global exit code using a named key."""
    global EXIT_CODE
    EXIT_CODE = EXIT_CODES[key]


def setExitCodeRaw(code: int) -> None:
    """Set global exit code directly with a raw integer."""
    global EXIT_CODE
    EXIT_CODE = code


def incrementCounters(total: int, skipped: int) -> None:
    """Increment global counters for processed gcov files."""
    global GCOVS_TOTAL, GCOVS_SKIPPED
    GCOVS_TOTAL += total
    GCOVS_SKIPPED += skipped


def stopwatch() -> float:
    """Return number of seconds since last time this was called."""
    global START_TIME
    end_time = time.monotonic()
    delta = end_time - START_TIME
    START_TIME = end_time
    return delta


def parseVersionFromLine(version_str: str) -> Tuple[int, ...]:
    """Given a string containing a dotted integer version, parse out integers and return as tuple."""
    version = re.search(r'(\d+\.\d+\.\d+)', version_str)

    if not version:
        return (0, 0, 0)

    return tuple(map(int, version.group(1).split(".")))


def getGcovVersion(gcov: str) -> Tuple[int, ...]:
    p = subprocess.Popen([gcov, "-v"], stdout=subprocess.PIPE)
    output = p.communicate()[0].decode('UTF-8')
    p.wait()
    return parseVersionFromLine(output.split("\n")[0])


def tryParseNumber(s: str) -> int:
    """Try to parse a string as integer, return 0 on failure (with warning)."""
    try:
        return int(s)
    except ValueError:
        # Log a warning if not hyphen
        if s != "-":
            logging.warning(f"Unsupported numerical value '{s}', using 0")
        # Default to 0 if we can't parse the number (e.g. "-", "NaN", etc.)
        return 0


def removeFiles(files: List[str]) -> None:
    """Remove a list of files from the filesystem."""
    for file in files:
        os.remove(file)


def processPrefix(path: str, prefix: str, prefix_strip: int) -> str:
    """Process GCOV_PREFIX and GCOV_PREFIX_STRIP logic."""
    p = Path(path)
    if p.exists() or not p.is_absolute():
        return path

    if prefix_strip > 0:
        segments = p.parts

        if len(segments) < prefix_strip + 1:
            logging.warning(f"Couldn't strip {prefix_strip} path levels from {path}.")
            return path

        segments = segments[prefix_strip + 1:]
        p = Path(segments[0])
        segments = segments[1:]
        for s in segments:
            p = p.joinpath(s)

    if len(prefix) > 0:
        if p.is_absolute():
            p = Path(prefix).joinpath(p.relative_to('/'))
        else:
            p = Path(prefix).joinpath(p)

    return str(p)


def getFilteredCoverageFiles(coverage_files: List[str], exclude: List[str]) -> List[str]:
    """Filter out gcda/gcno files based on --exclude-gcda option."""
    def excludeGcda(gcda: str) -> bool:
        for ex in exclude:
            if ex in gcda:
                logging.debug(f"Omitting {gcda} due to '--exclude-gcda {ex}'")
                return False
        return True

    return list(filter(excludeGcda, coverage_files))


def globCoverageFiles(cwd: str, coverage_type: str) -> List[str]:
    """Recursively find all files with given extension using glob."""
    return glob.glob(
        os.path.join(os.path.abspath(cwd), "**/*" + coverage_type),
        recursive=True
    )


def findCoverageFiles(
    cwd: str,
    coverage_files: List[str],
    use_gcno: bool
) -> List[str]:
    """Find coverage files (gcda or gcno) to process."""
    coverage_type = "user provided"
    if not coverage_files:
        # gcov strips off extension and searches for both .gcno/.gcda
        coverage_type = GCOV_GCNO_EXT if use_gcno else GCOV_GCDA_EXT
        coverage_files = globCoverageFiles(cwd, coverage_type)

    logging.info(f"Found {len(coverage_files)} coverage files ({coverage_type})")
    logging.debug("Coverage files found:\n    %s", "\n    ".join(coverage_files))
    return coverage_files


def _pick_tmp_dir(estimated_need: int = 0, user_dir: str = "") -> str:
    """Pick a temp directory with space check.

    Prefers /dev/shm (tmpfs, RAM-backed) for performance, falls back to the
    system temporary directory if /dev/shm has insufficient free space or is
    unavailable.

    *estimated_need* is a rough upper bound in bytes; if 0 it's treated as
    "always use the preferred candidate".
    """
    if user_dir:
        return user_dir

    candidates = ["/dev/shm"]
    for d in candidates:
        try:
            usage = shutil.disk_usage(d)
            if estimated_need == 0 or usage.free >= estimated_need:
                return d
        except OSError:
            continue

    return tempfile.gettempdir()


def _prepare_merged_chunk(
    chunk: List[str],
    gcno_dir: str,
    search_dir: str,
    tmpdir: str,
) -> Tuple[str, List[str]]:
    """Create a temporary directory with both .gcda and .gcno files.

    When .gcda and .gcno live in separate directory trees (e.g. CMake build/
    dir vs test-case dir), gcov cannot find the .gcno file and produces
    incomplete JSON.  This function mirrors the common relative path structure
    under *tmpdir* and symlinks both file types into it so that gcov finds
    the .gcno sibling naturally.

    Returns (*tmpdir*, *new_chunk*) where *new_chunk* contains the symlinked
    paths gcov should receive.
    """
    new_chunk: List[str] = []
    for gcda_path in chunk:
        rel = os.path.relpath(gcda_path, search_dir)

        dst_gcda = os.path.join(tmpdir, rel)
        os.makedirs(os.path.dirname(dst_gcda), exist_ok=True)
        os.symlink(gcda_path, dst_gcda)
        new_chunk.append(dst_gcda)

        # Mirror the matching .gcno alongside it
        gcno_rel = rel.replace('.gcda', '.gcno')
        src_gcno = os.path.join(gcno_dir, gcno_rel)
        if os.path.exists(src_gcno):
            dst_gcno = os.path.join(tmpdir, gcno_rel)
            os.makedirs(os.path.dirname(dst_gcno), exist_ok=True)
            os.symlink(src_gcno, dst_gcno)

    return tmpdir, new_chunk


def _cleanup_tmpdir(tmpdir: Optional[str]) -> None:
    """Remove a temporary directory created by _prepare_merged_chunk."""
    if tmpdir is not None:
        shutil.rmtree(tmpdir, ignore_errors=True)


def gcovWorker(
    data_q: multiprocessing.Queue,
    metrics_q: multiprocessing.Queue,
    args: argparse.Namespace,
    chunk: List[str],
    gcov_filter_options: GcovFilterOptions
) -> None:
    """Worker process that runs gcov on a chunk of files and returns coverage data."""
    base_report: FastcovReport = {"sources": {}}
    gcovs_total = 0
    gcovs_skipped = 0
    tmpdir = None

    gcov_bin = args.gcov
    gcov_args = ["--json-format", "--stdout"]
    if getattr(args, 'branchcoverage', False) or getattr(args, 'xbranchcoverage', False):
        gcov_args.append("--branch-probabilities")

    encoding = sys.stdout.encoding if sys.stdout.encoding else 'UTF-8'
    workdir = args.cdirectory if args.cdirectory else "."

    # When --gcno-dir is set, build an ephemeral merged directory so gcov can
    # find both .gcda and .gcno side by side.  /dev/shm (tmpfs) is preferred
    # for performance; fall back to system temp if unavailable.
    gcno_dir = getattr(args, 'gcno_dir', "")
    if gcno_dir:
        tmpdir = tempfile.mkdtemp(
            prefix="fastcov_",
            dir=_pick_tmp_dir(len(chunk) * 65536, gcno_dir),
        )
        _, merged_chunk = _prepare_merged_chunk(
            chunk, gcno_dir, args.directory, tmpdir,
        )
        gcov_input = merged_chunk
    else:
        gcov_input = chunk

    p = subprocess.Popen(
        [gcov_bin] + gcov_args + gcov_input,
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    # Ensure stdout is not None
    if p.stdout is None:
        logging.error("Failed to get stdout from gcov process")
        setExitCode("bad_chunk_file")
        _cleanup_tmpdir(tmpdir)
        return

    for i, line in enumerate(iter(p.stdout.readline, b'')):
        try:
            intermediate_json = cast(GcovJsonOutput, json.loads(line.decode(encoding)))
        except json.decoder.JSONDecodeError as e:
            logging.error(f"Could not process chunk file '{gcov_input[i]}' ({i+1}/{len(gcov_input)})")
            logging.error(str(e))
            setExitCode("bad_chunk_file")
            continue

        if "current_working_directory" not in intermediate_json:
            gcda_name = os.path.basename(
                intermediate_json.get("data_file", gcov_input[i] if i < len(gcov_input) else "?")
            )
            # When processing .gcda files (normal mode), missing
            # current_working_directory usually means the .gcno file is in a
            # different tree — warn and skip gracefully.  When processing
            # .gcno files (--process-gcno mode), the error is more likely
            # genuine (corrupt/empty file), so preserve the error exit code.
            logging.warning(f"Missing 'current_working_directory' for '{gcda_name}' "
                           f"— gcov could not find source files (try --gcno-directory)")
            if args.use_gcno:
                setExitCode("missing_json_key")
            gcovs_skipped += 1
            continue

        intermediate_json_files = processGcovs(
            args.cdirectory,
            intermediate_json["files"],
            intermediate_json["current_working_directory"],
            gcov_filter_options
        )

        for f in intermediate_json_files:
            distillSource(f, base_report["sources"], args.test_name, getattr(args, 'xbranchcoverage', False))

        gcovs_total += len(intermediate_json["files"])
        gcovs_skipped += len(intermediate_json["files"]) - len(intermediate_json_files)

    p.wait()

    _cleanup_tmpdir(tmpdir)

    data_q.put(base_report)
    metrics_q.put((gcovs_total, gcovs_skipped))

    sys.exit(EXIT_CODE)


def processGcdas(
    args: argparse.Namespace,
    coverage_files: List[str],
    gcov_filter_options: GcovFilterOptions
) -> FastcovReport:
    """Spawn multiple gcovWorker processes in parallel and combine their results."""
    chunk_size = max(args.minimum_chunk, int(len(coverage_files) / args.jobs) + 1)

    processes = []
    data_q: multiprocessing.Queue = multiprocessing.Queue()
    metrics_q: multiprocessing.Queue = multiprocessing.Queue()

    for chunk in chunks(coverage_files, chunk_size):
        p = multiprocessing.Process(
            target=gcovWorker,
            args=(data_q, metrics_q, args, chunk, gcov_filter_options)
        )
        processes.append(p)
        p.start()

    logging.info(f"Spawned {len(processes)} gcov processes, each processing at most {chunk_size} coverage files")

    fastcov_jsons: List[FastcovReport] = []
    for _ in processes:
        fastcov_jsons.append(cast(FastcovReport, data_q.get()))
        incrementCounters(*metrics_q.get())

    for p in processes:
        p.join()
        if p.exitcode is not None and p.exitcode != 0:
            setExitCodeRaw(p.exitcode)

    # Combine all results
    base_fastcov = fastcov_jsons.pop()
    for fj in fastcov_jsons:
        combineReports(base_fastcov, fj)

    return base_fastcov


def shouldFilterSource(source: str, gcov_filter_options: GcovFilterOptions) -> bool:
    """Returns true if the provided source file should be filtered due to CLI options."""
    # If explicit sources were passed, check for match
    if gcov_filter_options["sources"]:
        if source not in gcov_filter_options["sources"]:
            logging.debug(f"Filtering coverage for '{source}' due to option '--source-files'")
            return True

    # Check exclude filter
    for ex in gcov_filter_options["exclude"]:
        if ex in source:
            logging.debug(f"Filtering coverage for '{source}' due to option '--exclude {ex}'")
            return True

    # Check exclude-glob filter
    for ex_glob in gcov_filter_options["exclude_glob"]:
        if fnmatch.fnmatch(source, ex_glob):
            logging.debug(f"Filtering coverage for '{source}' due to option '--exclude-glob {ex_glob}'")
            return True

    # Check include filter
    if gcov_filter_options["include"]:
        included = any(inc in source for inc in gcov_filter_options["include"])
        if not included:
            logging.debug(f"Filtering coverage for '{source}' due to option '--include {' '.join(gcov_filter_options['include'])}'")
            return True

    return False


def filterFastcov(fastcov_json: FastcovReport, args: argparse.Namespace) -> None:
    """Apply all source file filtering options (--include, --exclude, --source-files, etc.)."""
    logging.info("Performing filtering operations (if applicable)")
    gcov_filter_options = getGcovFilterOptions(args)

    for source in list(fastcov_json["sources"].keys()):
        if shouldFilterSource(source, gcov_filter_options):
            del fastcov_json["sources"][source]


def processGcov(
    cwd: str,
    gcov: GcovFile,
    source_base_dir: str,
    files: List[GcovFile],
    gcov_filter_options: GcovFilterOptions
) -> None:
    # Uses cwd if set, else source_base_dir from gcov json. If both are empty, uses "."
    base_dir = cwd if cwd else source_base_dir
    base_dir = base_dir if base_dir else "."
    # Add absolute path - create a new dict with the additional field
    gcov_with_abs: GcovFile = {**gcov, "file_abs": os.path.abspath(os.path.join(base_dir, gcov["file"]))}

    if shouldFilterSource(gcov_with_abs["file_abs"], gcov_filter_options):
        return

    files.append(gcov_with_abs)
    logging.debug(f"Accepted coverage for '{gcov_with_abs['file_abs']}'")


def processGcovs(
    cwd: str,
    gcov_files: List[GcovFile],
    source_base_dir: str,
    gcov_filter_options: GcovFilterOptions
) -> List[GcovFile]:
    files: List[GcovFile] = []
    for gcov in gcov_files:
        processGcov(cwd, gcov, source_base_dir, files, gcov_filter_options)
    return files


def dumpBranchCoverageToLcovInfo(f, branches: Dict[int, List[int]]) -> None:
    branch_miss = 0
    branch_found = 0
    brda: List[Tuple[int, int, int, int]] = []
    for line_num, branch_counts in branches.items():
        for i, count in enumerate(branch_counts):
            # Branch (<line number>, <block number>, <branch number>, <taken>)
            brda.append((line_num, int(i/2), i, count))
            branch_miss += int(count == 0)
            branch_found += 1
    for v in sorted(brda):
        f.write(f"BRDA:{v[0]},{v[1]},{v[2]},{v[3]}\n")
    f.write(f"BRF:{branch_found}\n")                # Branches Found
    f.write(f"BRH:{branch_found - branch_miss}\n")  # Branches Hit


def dumpToLcovInfo(fastcov_json: FastcovReport, output: str) -> None:
    with open(output, "w") as out_f:
        sources = fastcov_json["sources"]
        for sf in sorted(sources.keys()):
            for tn in sorted(sources[sf].keys()):
                data = sources[sf][tn]
                out_f.write(f"TN:{tn}\n")  # Test Name
                out_f.write(f"SF:{sf}\n")  # Source File

                fn_miss = 0
                fn_list_local: List[Tuple[int, str]] = []
                fnda: List[Tuple[int, str]] = []
                for function, fdata in data["functions"].items():
                    fn_list_local.append((fdata["start_line"], function))
                    fnda.append((fdata["execution_count"], function))
                    fn_miss += int(fdata["execution_count"] == 0)
                # NOTE: lcov sorts FN, but not FNDA.
                for v in sorted(fn_list_local):
                    out_f.write(f"FN:{v[0]},{v[1]}\n")
                for v in sorted(fnda):
                    out_f.write(f"FNDA:{v[0]},{v[1]}\n")
                out_f.write(f"FNF:{len(data['functions'])}\n")
                out_f.write(f"FNH:{len(data['functions']) - fn_miss}\n")

                if data["branches"]:
                    dumpBranchCoverageToLcovInfo(out_f, data["branches"])

                line_miss = 0
                da: List[Tuple[int, int]] = []
                for line_num, count in data["lines"].items():
                    da.append((line_num, count))
                    line_miss += int(count == 0)
                for line_tuple in sorted(da):
                    out_f.write(f"DA:{line_tuple[0]},{line_tuple[1]}\n")
                out_f.write(f"LF:{len(data['lines'])}\n")
                out_f.write(f"LH:{len(data['lines']) - line_miss}\n")
                out_f.write("end_of_record\n")


def getSourceLines(source: str, fallback_encodings: Optional[List[str]] = None) -> List[str]:
    """Return a list of lines from the provided source, trying to decode with fallback encodings if the default fails."""
    if fallback_encodings is None:
        fallback_encodings = []
    
    default_encoding = sys.getdefaultencoding()
    for encoding in [default_encoding] + fallback_encodings:
        try:
            with open(source, encoding=encoding) as f:
                return f.readlines()
        except UnicodeDecodeError:
            pass

    logging.warning(f"Could not decode '{source}' with {default_encoding} or fallback encodings ({','.join(fallback_encodings)}); ignoring errors")
    with open(source, errors="ignore") as f:
        return f.readlines()


def containsMarker(markers: List[str], strBody: str) -> bool:
    for marker in markers:
        if marker in strBody:
            return True
    return False


# Returns whether source coverage changed or not
def exclProcessSource(
    fastcov_sources: Dict[str, Dict[str, TestCoverage]],
    source: str,
    exclude_branches_sw: List[str],
    include_branches_sw: List[str],
    exclude_line_marker: List[str],
    fallback_encodings: List[str],
    gcov_prefix: str,
    gcov_prefix_strip: int
) -> bool:
    source_to_open = processPrefix(source, gcov_prefix, gcov_prefix_strip)

    # Before doing any work, check if this file even needs to be processed
    if not exclude_branches_sw and not include_branches_sw:
        with open(source_to_open, errors="ignore") as f:
            if not containsMarker(exclude_line_marker + ["LCOV_EXCL"], f.read()):
                return False

    start_line = 0
    end_line = 0
    for i, line in enumerate(getSourceLines(source_to_open, fallback_encodings), 1):
        for test_name in fastcov_sources[source]:
            fastcov_data = fastcov_sources[source][test_name]

            # Check branch exclusion
            if (exclude_branches_sw or include_branches_sw) and (i in fastcov_data["branches"]):
                del_exclude_br = exclude_branches_sw and any(line.lstrip().startswith(e) for e in exclude_branches_sw)
                del_include_br = include_branches_sw and all(not line.lstrip().startswith(e) for e in include_branches_sw)
                if del_exclude_br or del_include_br:
                    del fastcov_data["branches"][i]

            if not containsMarker(exclude_line_marker + ["LCOV_EXCL"], line):
                continue

            # Build line_to_func
            line_to_func: Dict[int, Set[str]] = {}
            for func_name in fastcov_data["functions"].keys():
                func_line = fastcov_data["functions"][func_name]["start_line"]
                line_to_func.setdefault(func_line, set()).add(func_name)

            if any(marker in line for marker in exclude_line_marker):
                # Safe pop for typed dict keys
                if "lines" in fastcov_data:
                    fastcov_data["lines"].pop(i, None)
                if "branches" in fastcov_data:
                    fastcov_data["branches"].pop(i, None)
                for func_name in line_to_func.get(i, set()):
                    fastcov_data["functions"].pop(func_name, None)

            elif "LCOV_EXCL_START" in line:
                start_line = i
            elif "LCOV_EXCL_STOP" in line:
                end_line = i
                if not start_line:
                    end_line = 0
                    continue

                # Safe pop for typed dict keys
                if "lines" in fastcov_data and "branches" in fastcov_data:
                    for line_num in list(fastcov_data["lines"].keys()):
                        if start_line <= line_num <= end_line:
                            fastcov_data["lines"].pop(line_num)
                    
                    for line_num in list(fastcov_data["branches"].keys()):
                        if start_line <= line_num <= end_line:
                            fastcov_data["branches"].pop(line_num)

                for line_num in range(start_line, end_line):
                    for func_name in line_to_func.get(line_num, set()):
                        fastcov_data["functions"].pop(func_name, None)

                start_line = end_line = 0
            elif "LCOV_EXCL_BR_LINE" in line:
                fastcov_data["branches"].pop(i, None)

    return True


def exclMarkerWorker(
    data_q: multiprocessing.Queue,
    fastcov_sources: Dict[str, Dict[str, TestCoverage]],
    chunk: List[str],
    exclude_branches_sw: List[str],
    include_branches_sw: List[str],
    exclude_line_marker: List[str],
    fallback_encodings: List[str],
    gcov_prefix: str,
    gcov_prefix_strip: int
) -> None:
    changed_sources: List[Tuple[str, Dict[str, TestCoverage]]] = []

    for source in chunk:
        try:
            if exclProcessSource(fastcov_sources, source, exclude_branches_sw, include_branches_sw, 
                                exclude_line_marker, fallback_encodings, gcov_prefix, gcov_prefix_strip):
                changed_sources.append((source, fastcov_sources[source]))
        except FileNotFoundError:
            logging.error(f"Could not find '{source}' to scan for exclusion markers...")
            setExitCode("excl_not_found")  # Set exit code because of error

    # Write out changed sources back to main fastcov file
    data_q.put(changed_sources)

    # Exit current process with appropriate code
    sys.exit(EXIT_CODE)


def processExclusionMarkers(
    fastcov_json: FastcovReport,
    jobs: int,
    exclude_branches_sw: List[str],
    include_branches_sw: List[str],
    exclude_line_marker: List[str],
    min_chunk_size: int,
    fallback_encodings: List[str],
    gcov_prefix: str,
    gcov_prefix_strip: int
) -> None:
    chunk_size = max(min_chunk_size, int(len(fastcov_json["sources"]) / jobs) + 1)

    processes = []
    data_q: multiprocessing.Queue = multiprocessing.Queue()
    for chunk in chunks(list(fastcov_json["sources"].keys()), chunk_size):
        p = multiprocessing.Process(
            target=exclMarkerWorker,
            args=(data_q, fastcov_json["sources"], chunk, exclude_branches_sw, include_branches_sw, 
                  exclude_line_marker, fallback_encodings, gcov_prefix, gcov_prefix_strip)
        )
        processes.append(p)
        p.start()

    logging.info(f"Spawned {len(processes)} exclusion marker scanning processes, each processing at most {chunk_size} source files")

    changed_sources: List[Tuple[str, Dict[str, TestCoverage]]] = []
    for _ in processes:
        changed_sources.extend(data_q.get())

    for p in processes:
        p.join()
        if p.exitcode is not None and p.exitcode != 0:
            setExitCodeRaw(p.exitcode)

    for changed_source in changed_sources:
        fastcov_json["sources"][changed_source[0]] = changed_source[1]


def validateSources(
    fastcov_json: FastcovReport,
    gcov_prefix: str,
    gcov_prefix_strip: int
) -> None:
    logging.info("Checking if all sources exist")
    for source in fastcov_json["sources"].keys():
        source = processPrefix(source, gcov_prefix, gcov_prefix_strip)
        if not os.path.exists(source):
            logging.error(f"Cannot find '{source}'")


def distillFunction(
    function_raw: GcovFunction,
    functions: Dict[str, FunctionData]
) -> None:
    function_name = function_raw["name"]
    start_line = int(function_raw["start_line"])
    execution_count = int(function_raw["execution_count"])
    if function_name not in functions:
        functions[function_name] = {
            "start_line": start_line,
            "execution_count": execution_count
        }
    else:
        functions[function_name]["execution_count"] += execution_count


def emptyBranchSet(branch1: GcovBranch, branch2: GcovBranch) -> bool:
    return (branch1["count"] == 0 and branch2["count"] == 0)


def matchingBranchSet(branch1: GcovBranch, branch2: GcovBranch) -> bool:
    return (branch1["count"] == branch2["count"])


def filterExceptionalBranches(branches: List[GcovBranch]) -> List[GcovBranch]:
    filtered_branches: List[GcovBranch] = []
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


def distillLine(
    line_raw: GcovLine,
    lines: Dict[int, int],
    branches: Dict[int, List[int]],
    include_exceptional_branches: bool
) -> None:
    line_number = int(line_raw["line_number"])
    count = int(line_raw["count"])
    if count < 0:
        if "function_name" in line_raw and line_raw["function_name"] is not None:
            logging.warning(f"Ignoring negative count found in '{line_raw['function_name']}'.")
        else:
            logging.warning("Ignoring negative count.")
        count = 0

    if line_number not in lines:
        lines[line_number] = count
    else:
        lines[line_number] += count

    # Filter out exceptional branches by default unless requested otherwise
    branches_to_process = line_raw["branches"]
    if not include_exceptional_branches:
        branches_to_process = filterExceptionalBranches(line_raw["branches"])

    # Increment all branch counts
    for i, branch in enumerate(branches_to_process):
        if line_number not in branches:
            branches[line_number] = []
        blen = len(branches[line_number])
        glen = len(branches_to_process)
        if blen < glen:
            branches[line_number] += [0] * (glen - blen)
        # branch["count"] is int from GcovBranch
        branches[line_number][i] += int(branch["count"])


def distillSource(
    source_raw: GcovFile,
    sources: Dict[str, Dict[str, TestCoverage]],
    test_name: str,
    include_exceptional_branches: bool
) -> None:
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
        distillLine(
            line,
            sources[source_name][test_name]["lines"],
            sources[source_name][test_name]["branches"],
            include_exceptional_branches
        )


def dumpToJson(intermediate: FastcovReport, output: str) -> None:
    with open(output, "w") as f:
        json.dump(intermediate, f)


def getGcovFilterOptions(args: argparse.Namespace) -> GcovFilterOptions:
    return {
        "sources": set([os.path.abspath(s) for s in args.sources]),  # Make paths absolute, use set for fast lookups
        "include": args.includepost,
        "exclude": args.excludepost,
        "exclude_glob": args.excludepost_glob
    }


def addDicts(dict1: Dict[int, int], dict2: Dict[int, int]) -> Dict[int, int]:
    """Add dicts together by value."""
    result = dict1.copy()
    for k, v in dict2.items():
        result[k] = result.get(k, 0) + v
    return result


def addLists(list1: List[int], list2: List[int]) -> List[int]:
    """Add lists together by value."""
    blist = list(list2)
    slist = list(list1)
    if len(list1) > len(list2):
        blist, slist = slist, blist

    for i, b in enumerate(slist):
        blist[i] += b

    return blist


def combineReports(base: FastcovReport, overlay: FastcovReport) -> None:
    base_sources = base.get("sources", {})
    overlay_sources = overlay.get("sources", {})
    
    for source, scov in overlay_sources.items():
        # Combine Source Coverage
        if source not in base_sources:
            base_sources[source] = scov
            continue

        for test_name, tcov in scov.items():
            # Combine Source Test Name Coverage
            if test_name not in base_sources[source]:
                base_sources[source][test_name] = tcov
                continue

            # Get the existing test coverage data
            base_test_data = base_sources[source][test_name]
            
            # Combine Line Coverage
            base_test_data["lines"] = addDicts(base_test_data["lines"], tcov["lines"])

            # Combine Branch Coverage
            for branch, cov in tcov["branches"].items():
                if branch not in base_test_data["branches"]:
                    base_test_data["branches"][branch] = cov
                else:
                    base_test_data["branches"][branch] = addLists(base_test_data["branches"][branch], cov)

            # Combine Function Coverage
            for function_name, func_cov in tcov["functions"].items():
                if function_name in base_test_data["functions"]:
                    # Update existing function data
                    base_test_data["functions"][function_name]["execution_count"] += func_cov["execution_count"]
                else:
                    # Add new function data
                    base_test_data["functions"][function_name] = func_cov


def parseInfo(path: str) -> FastcovReport:
    """Parse an lcov .info file into fastcov json."""
    fastcov_json: FastcovReport = {"sources": {}}

    with open(path) as f:
        current_test_name: str = ""
        current_sf: str = ""

        for line in f:
            line = line.strip()
            if line.startswith("TN:"):
                current_test_name = line[3:]
            elif line.startswith("SF:"):
                current_sf = line[3:]
                if current_sf not in fastcov_json["sources"]:
                    fastcov_json["sources"][current_sf] = {}
                if current_test_name not in fastcov_json["sources"][current_sf]:
                    fastcov_json["sources"][current_sf][current_test_name] = {
                        "functions": {},
                        "branches": {},
                        "lines": {},
                    }
                current_data: TestCoverage = fastcov_json["sources"][current_sf][current_test_name]
            elif line.startswith("FN:"):
                line_nums, function_name = line[3:].rsplit(",", maxsplit=1)
                line_num_start = line_nums.split(",")[0]
                current_data["functions"][function_name] = {
                    "start_line": tryParseNumber(line_num_start),
                    "execution_count": 0
                }
            elif line.startswith("FNDA:"):
                count_str, function_name = line[5:].split(",", maxsplit=1)
                count: int = tryParseNumber(count_str)  # Explicit type annotation
                if function_name in current_data["functions"]:
                    current_data["functions"][function_name]["execution_count"] = count
            elif line.startswith("DA:"):
                line_num_str, count_str = line[3:].split(",", maxsplit=1)
                line_num: int = int(line_num_str)
                count_val: int = tryParseNumber(count_str)  # Explicit type annotation
                current_data["lines"][line_num] = count_val
            elif line.startswith("BRDA:"):
                tokens = line[5:].split(",")
                line_num = int(tokens[0])
                count_val = tryParseNumber(tokens[-1])  # This returns int
                if line_num not in current_data["branches"]:
                    current_data["branches"][line_num] = []
                current_data["branches"][line_num].append(count_val)  # Should be int now

    return fastcov_json


def convertKeysToInt(report: FastcovReport) -> None:
    for source in report["sources"].keys():
        for test_name in report["sources"][source].keys():
            report_data = report["sources"][source][test_name]
            report_data["lines"] = {int(k): v for k, v in report_data["lines"].items()}
            report_data["branches"] = {int(k): v for k, v in report_data["branches"].items()}


def parseAndCombine(paths: List[str]) -> FastcovReport:
    base_report: Optional[FastcovReport] = None

    for path in paths:
        if path.endswith(".json"):
            with open(path) as f:
                report = cast(FastcovReport, json.load(f))
        elif path.endswith(".info"):
            report = parseInfo(path)
        else:
            logging.error(f"Currently only fastcov .json and lcov .info supported for combine operations, aborting due to {path}...\n")
            sys.exit(EXIT_CODES["unsupported_coverage_format"])

        # In order for sorting to work later when we serialize,
        # make sure integer keys are int
        convertKeysToInt(report)

        if base_report is None:
            base_report = report
            logging.info(f"Setting {path} as base report")
        else:
            combineReports(base_report, report)
            logging.info(f"Adding {path} to base report")

    if base_report is None:
        return {"sources": {}}
    return base_report


def getCombineCoverage(args: argparse.Namespace) -> FastcovReport:
    logging.info("Performing combine operation")
    fastcov_json = parseAndCombine(args.combine)
    filterFastcov(fastcov_json, args)
    return fastcov_json


def getGcovCoverage(args: argparse.Namespace) -> FastcovReport:
    checkPythonVersion(sys.version_info[0:2])

    # Need at least gcov 9.0.0 because that's when gcov JSON and stdout streaming was introduced
    checkGcovVersion(getGcovVersion(args.gcov))

    # Get list of gcda files to process
    coverage_files = findCoverageFiles(args.directory, args.coverage_files, args.use_gcno)

    # If gcda/gcno filtering is enabled, filter them out now
    if args.excludepre:
        coverage_files = getFilteredCoverageFiles(coverage_files, args.excludepre)
        logging.info(f"Found {len(coverage_files)} coverage files after filtering")

    # We "zero" the "counters" by simply deleting all gcda files
    if args.zerocounters:
        removeFiles(globCoverageFiles(args.directory, GCOV_GCDA_EXT))
        logging.info(f"Removed {len(coverage_files)} .gcda files")
        sys.exit()

    if not coverage_files:
        logging.error(f"No coverage files found in directory '{args.directory}'")
        setExitCode("no_coverage_files")
        sys.exit(EXIT_CODE)

    # Fire up one gcov per cpu and start processing gcdas
    gcov_filter_options = getGcovFilterOptions(args)
    fastcov_json = processGcdas(args, coverage_files, gcov_filter_options)

    # Summarize processing results
    logging.info(f"Processed {GCOVS_TOTAL - GCOVS_SKIPPED} .gcov files ({GCOVS_TOTAL} total, {GCOVS_SKIPPED} skipped)")
    logging.debug(
    "Final report will contain coverage for the following %d source files:\n    %s",
    len(fastcov_json['sources']),
    "\n    ".join(fastcov_json['sources'])
)

    return fastcov_json


def formatCoveredItems(covered: int, total: int) -> str:
    coverage = (covered * 100.0) / total if total > 0 else 100.0
    coverage = round(coverage, 2)
    return f"{coverage:.2f}%, {covered}/{total}"


def dumpStatistic(fastcov_json: FastcovReport) -> None:
    total_lines = 0
    covered_lines = 0
    total_functions = 0
    covered_functions = 0
    total_files = len(fastcov_json["sources"])
    covered_files = 0

    for source_name, source in fastcov_json["sources"].items():
        is_file_covered = False
        for test_name, test in source.items():
            total_lines += len(test["lines"])
            for execution_count in test["lines"].values():
                covered_lines += 1 if execution_count > 0 else 0
                is_file_covered = is_file_covered or execution_count > 0
            total_functions += len(test["functions"])
            for function in test["functions"].values():
                covered_functions += 1 if function['execution_count'] > 0 else 0
                is_file_covered = is_file_covered or function['execution_count'] > 0
        if is_file_covered:
            covered_files = covered_files + 1

    logging.info(f"Files Coverage: {formatCoveredItems(covered_files, total_files)}")
    logging.info(f"Functions Coverage: {formatCoveredItems(covered_functions, total_functions)}")
    logging.info(f"Lines Coverage: {formatCoveredItems(covered_lines, total_lines)}")


def dumpFile(fastcov_json: FastcovReport, args: argparse.Namespace) -> None:
    if args.lcov:
        dumpToLcovInfo(fastcov_json, args.output)
        logging.info(f"Created lcov info file '{args.output}'")
    else:
        dumpToJson(fastcov_json, args.output)
        logging.info(f"Created fastcov json file '{args.output}'")

    if args.dump_statistic:
        dumpStatistic(fastcov_json)


def tupleToDotted(tup: Tuple[int, ...]) -> str:
    return ".".join(map(str, tup))


def parseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='A parallel gcov wrapper for fast coverage report generation')
    parser.add_argument('-z', '--zerocounters', dest='zerocounters', action="store_true", help='Recursively delete all gcda files')

    # Enable Branch Coverage
    parser.add_argument('-b', '--branch-coverage', dest='branchcoverage', action="store_true", help='Include only the most useful branches in the coverage report.')
    parser.add_argument('-B', '--exceptional-branch-coverage', dest='xbranchcoverage', action="store_true", help='Include ALL branches in the coverage report (including potentially noisy exceptional branches).')
    parser.add_argument('-A', '--exclude-br-lines-starting-with', dest='exclude_branches_sw', nargs="+", metavar='', default=[], help='Exclude branches from lines starting with one of the provided strings (i.e. assert, return, etc.)')
    parser.add_argument('-a', '--include-br-lines-starting-with', dest='include_branches_sw', nargs="+", metavar='', default=[], help='Include only branches from lines starting with one of the provided strings (i.e. if, else, while, etc.)')
    parser.add_argument('-X', '--skip-exclusion-markers', dest='skip_exclusion_markers', action="store_true", help='Skip reading source files to search for lcov exclusion markers (such as "LCOV_EXCL_LINE")')
    parser.add_argument('-x', '--scan-exclusion-markers', dest='scan_exclusion_markers', action="store_true", help='(Combine operations) Force reading source files to search for lcov exclusion markers (such as "LCOV_EXCL_LINE")')

    # Capture untested file coverage as well via gcno
    parser.add_argument('-n', '--process-gcno', dest='use_gcno', action="store_true", help='Process both gcno and gcda coverage files. This option is useful for capturing untested files in the coverage report.')

    # Filtering Options
    parser.add_argument('-s', '--source-files', dest='sources', nargs="+", metavar='', default=[], help='Filter: Specify exactly which source files should be included in the final report. Paths must be either absolute or relative to current directory.')
    parser.add_argument('-e', '--exclude', dest='excludepost', nargs="+", metavar='', default=[], help='Filter: Exclude source files from final report if they contain one of the provided substrings (i.e. /usr/include test/, etc.)')
    parser.add_argument('-eg', '--exclude-glob', dest='excludepost_glob', nargs="+", metavar='', default=[], help='Filter: Exclude source files by glob pattern from final report if they contain one of the provided substrings (i.e. /usr/include test/, etc.)')
    parser.add_argument('-i', '--include', dest='includepost', nargs="+", metavar='', default=[], help='Filter: Only include source files in final report that contain one of the provided substrings (i.e. src/ etc.)')
    parser.add_argument('-f', '--gcda-files', dest='coverage_files', nargs="+", metavar='', default=[], help='Filter: Specify exactly which gcda or gcno files should be processed. Note that specifying gcno causes both gcno and gcda to be processed.')
    parser.add_argument('-E', '--exclude-gcda', dest='excludepre', nargs="+", metavar='', default=[], help='Filter: Exclude gcda or gcno files from being processed via simple find matching (not regex)')
    parser.add_argument('-u', '--diff-filter', dest='diff_file', default='', help='Unified diff file with changes which will be included into final report')
    parser.add_argument('-ub', '--diff-base-dir', dest='diff_base_dir', default='', help='Base directory for sources in unified diff file, usually repository dir')
    parser.add_argument('-ce', '--custom-exclusion-marker', dest='exclude_line_marker', nargs="+", metavar='', default=["LCOV_EXCL_LINE"], help='Filter: Add filter for lines that will be excluded from coverage (same behavior as "LCOV_EXCL_LINE")')

    parser.add_argument('-g', '--gcov', dest='gcov', default='gcov', help='Which gcov binary to use')

    parser.add_argument('-d', '--search-directory', dest='directory', default=".", help='Base directory to recursively search for gcda files (default: .)')
    parser.add_argument('-c', '--compiler-directory', dest='cdirectory', default="", help='Base directory compiler was invoked from (default: . or read from gcov)')
    parser.add_argument('-G', '--gcno-directory', dest='gcno_dir', default="", help='Directory containing .gcno files. When .gcda and .gcno are in separate directory trees, fastcv symlinks both into an ephemeral temp dir so gcov can find the .gcno sibling. Combine with -c to help gcov resolve relative source paths.')

    parser.add_argument('-j', '--jobs', dest='jobs', type=int, default=multiprocessing.cpu_count(), help=f'Number of parallel gcov to spawn (default: {multiprocessing.cpu_count()}).')
    parser.add_argument('-m', '--minimum-chunk-size', dest='minimum_chunk', type=int, default=5, help='Minimum number of files a thread should process (default: 5).')

    parser.add_argument('-F', '--fallback-encodings', dest='fallback_encodings', nargs="+", metavar='', default=[], help='List of encodings to try if opening a source file with the default fails (i.e. latin1, etc.). This option is not usually needed.')

    parser.add_argument('-l', '--lcov', dest='lcov', action="store_true", help='Output in lcov info format instead of fastcov json')
    parser.add_argument('-o', '--output', dest='output', default="", help='Name of output file (default: coverage.json or coverage.info, depends on --lcov option)')
    parser.add_argument('-q', '--quiet', dest='quiet', action="store_true", help='Suppress output to stdout')

    parser.add_argument('-t', '--test-name', dest='test_name', default="", help='Specify a test name for the coverage. Equivalent to lcov\'s `-t`.')
    parser.add_argument('-C', '--add-tracefile', dest='combine', nargs="+", help='Combine multiple coverage files into one. If this flag is specified, fastcov will do a combine operation instead invoking gcov. Equivalent to lcov\'s `-a`.')

    parser.add_argument('-V', '--verbose', dest="verbose", action="store_true", help="Print more detailed information about what fastcov is doing")
    parser.add_argument('-w', '--validate-sources', dest="validate_sources", action="store_true", help="Check if every source file exists")
    parser.add_argument('-p', '--dump-statistic', dest="dump_statistic", action="store_true", help="Dump total statistic at the end")
    parser.add_argument('-v', '--version', action="version", version=f'%(prog)s {__version__}', help="Show program's version number and exit")

    parser.add_argument('-gps', '--gcov_prefix_strip', dest="gcov_prefix_strip", action="store", default=0, type=int, help="The number of initial directory names to strip off the absolute paths in the object file.")
    parser.add_argument('-gp', '--gcov_prefix', dest="gcov_prefix", action="store", default="", help="The prefix to add to the paths in the object file.")

    args = parser.parse_args()
    if not args.output:
        args.output = 'coverage.info' if args.lcov else 'coverage.json'
    return args


def checkPythonVersion(version: Tuple[int, int]) -> None:
    """Exit if the provided python version is less than the supported version."""
    if version < MINIMUM_PYTHON:
        sys.stderr.write(f"Minimum python version {tupleToDotted(MINIMUM_PYTHON)} required, found {tupleToDotted(version)}\n")
        sys.exit(EXIT_CODES["python_version"])


def checkGcovVersion(version: Tuple[int, ...]) -> None:
    """Exit if the provided gcov version is less than the supported version."""
    if version < MINIMUM_GCOV:
        sys.stderr.write(f"Minimum gcov version {tupleToDotted(MINIMUM_GCOV)} required, found {tupleToDotted(version)}\n")
        sys.exit(EXIT_CODES["gcov_version"])


def setupLogging(quiet: bool, verbose: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(FastcovFormatter("[%(levelname)s]: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    if not quiet:
        logging.disable(level=logging.NOTSET)  # Re-enable logging

    if verbose:
        root.setLevel(logging.DEBUG)


def main() -> None:
    # Python 3.14+ changed the default multiprocessing start method from "fork" to "spawn" on POSIX.
    # This causes massive slowdowns (13 times) due to pickling overhead. Workers are safe to fork (no threads exist at this point).
    multiprocessing.set_start_method("fork")

    args = parseArgs()

    # Setup logging
    setupLogging(args.quiet, args.verbose)

    if args.gcov_prefix_strip > 0:
        os.environ["GCOV_PREFIX_STRIP"] = str(args.gcov_prefix_strip)

    if len(args.gcov_prefix) > 0:
        os.environ["GCOV_PREFIX"] = args.gcov_prefix

    # Get report from appropriate source
    if args.combine:
        fastcov_json = getCombineCoverage(args)
        skip_exclusion_markers = not args.scan_exclusion_markers
    else:
        fastcov_json = getGcovCoverage(args)
        skip_exclusion_markers = args.skip_exclusion_markers

    # Scan for exclusion markers
    if not skip_exclusion_markers:
        processExclusionMarkers(fastcov_json, args.jobs, args.exclude_branches_sw, args.include_branches_sw,
                               args.exclude_line_marker, args.minimum_chunk, args.fallback_encodings,
                               args.gcov_prefix, args.gcov_prefix_strip)
        logging.info(f"Scanned {len(fastcov_json['sources'])} source files for exclusion markers")

    if args.diff_file:
        logging.info(f"Filtering according to {args.diff_file} file")
        DiffParser().filterByDiff(args.diff_file, args.diff_base_dir, fastcov_json, args.fallback_encodings)

    if args.validate_sources:
        validateSources(fastcov_json, args.gcov_prefix, args.gcov_prefix_strip)

    # Dump to desired file format
    dumpFile(fastcov_json, args)

    # If there was an error along the way, but we still completed the pipeline...
    if EXIT_CODE:
        sys.exit(EXIT_CODE)


# Set package version... it's way down here so that we can call tupleToDotted
__version__: str = tupleToDotted(FASTCOV_VERSION)

if __name__ == '__main__':
    main()
