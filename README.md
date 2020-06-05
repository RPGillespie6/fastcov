[![Build Status](https://travis-ci.com/RPGillespie6/fastcov.svg?branch=master)](https://travis-ci.com/RPGillespie6/fastcov)
[![Code Coverage](https://img.shields.io/codecov/c/github/rpgillespie6/fastcov.svg)](https://codecov.io/gh/RPGillespie6/fastcov)
[![PyPI Version](https://img.shields.io/pypi/v/fastcov.svg)](https://pypi.org/project/fastcov/)
<!-- # SPDX-License-Identifier: MIT -->

# fastcov
A parallelized gcov wrapper for generating intermediate coverage formats *fast*

The goal of fastcov is to generate code coverage intermediate formats *as fast as possible*, even for large projects with hundreds of gcda objects. The intermediate formats may then be consumed by a report generator such as lcov's genhtml, or a dedicated front end such as coveralls, codecov, etc. fastcov was originally designed to be a drop-in replacement for lcov (application coverage only, not kernel coverage).

Currently the only intermediate formats supported are gcov json format, fastcov json format, and lcov info format. Adding support for other formats should require just a few lines of python to transform fastcov json format to the desired shape.

In order to achieve the speed gains, a few constraints apply:

1. GCC version >= 9.0.0

These versions of GCOV have support for JSON intermediate format as well as streaming report data straight to stdout. This second feature (the ability for gcov to stream report data to stdout) is critical - without it, fastcov cannot run multiple instances of gcov in parallel without loss of correctness.

If your linux distribution doesn't ship with GCC 9, the current easiest way (in my opinion) to try out fastcov is to use the fastcov docker image, which has GCC 9 compilers (`gcc-9` and `g++-9`), Python3, and CMake inside:

```bash
docker pull rpgillespie6/fastcov:latest
```

If you need other dependencies, just modify the Dockerfile and rebuild.

2. Object files must be either be built:

- Using absolute paths for all `-I` flags passed to the compiler

or

- Invoking the compiler from the same root directory

If you use CMake, you are almost certainly satisfying this second constraint (unless you care about `ExternalProject` coverage).

## Quick Start

Assuming you have docker, fastcov is easy to use:

```bash
$ docker pull rpgillespie6/fastcov
$ docker run -it --rm -v ${PWD}:/mnt/workspace -w /mnt/workspace -u $(id -u ${USER}):$(id -g ${USER}) rpgillespie6/fastcov
$ <build project> # Make sure to compile with gcc-9 or g++-9 and to pass "-g -O0 -fprofile-arcs -ftest-coverage" to all gcc/g++ statements
$ <run unit tests>
$ fastcov.py --gcov gcov-9 --exclude /usr/include --lcov -o report.info
$ genhtml -o code_coverage report.info
$ firefox code_coverage/index.html
```

See the [example](example/) directory for a working CMake example.

## Installation

A minimum of Python 3.5 is currently required.

Fastcov is a single source python tool. That means you can simply copy `fastcov.py` from this repository and run it directly with no other hassle.

However, fastcov is also available as a Python3 package that can be installed via pip.

Install newest stable fastcov release from PyPI:

```bash
$ pip3 install fastcov
```

Or install the bleeding edge version from GitHub:

```bash
$ pip3 install git+https://github.com/rpgillespie6/fastcov.git
```

## Filtering Options

Fastcov uses *substring matching* (not regex) for all of its filtering options. Furthermore, all filtering options take a list of parameters as arguments.

Here are some common filtering combinations you may find useful:

```bash
$ fastcov.py --exclude /usr/include test/ # Exclude system header files and test files from final report
$ fastcov.py --include src/ # Only include files with "src/" in its path in the final report
$ fastcov.py --source-files ../src/source1.cpp ../src/source2.cpp # Only include exactly ../src/source1.cpp and ../src/source2.cpp in the final report
$ fastcov.py --branch-coverage # Only include most useful branches (discards exceptional branches and initializer list branches)
$ fastcov.py --exceptional-branch-coverage # Include ALL branches in coverage report
```

It's possible to include *both* `--include` and `--exclude`. In this case, `--exclude` always takes priority. This could be used, for example, to include files that are in `src/` but not in `src/test/` by passing `--include src/ --exclude test/`.

Branch filters furthermore can stack:

```bash
$ fastcov.py --branch-coverage --include-br-lines-starting-with if else       # Only include branch coverage for lines starting with "if" or "else"
$ fastcov.py --branch-coverage --exclude-br-lines-starting-with assert ASSERT # Don't include coverage for lines starting with "assert" or "ASSERT"
```

It's possible to include *both* `--include-br-lines-starting-with` and `--exclude-br-lines-starting-with`. In this case, the branch will be removed if either the line does not start with one of `--include-br-lines-starting-with` or the line does start with one of `--exclude-br-lines-starting-with`. This could be used, for example, to include branches starting with `else` but not with `else if` by passing `--include-br-lines-starting-with else --exclude-br-lines-starting-with "else if"`.

## Combine Operations

Fastcov can combine arbitrary `.info` and `.json` reports into a single report by setting the combine flag `-C`. Furthermore, the same pipeline that is run during non-combine operations can optionally be applied to the combined report (filtering, exclusion scanning, select output format).

Combine operations are not subject to the gcov and python minimum version requirements.

A few example snippets:
```bash
# Basic combine operation combining 3 reports into 1
$ fastcov.py -C report1.info report2.info report3.json --lcov -o report_final.info
# Read in report1.info, remove all coverage for files containing "/usr/include" and write out the result
$ fastcov.py -C report1.info --exclude /usr/include --lcov -o report1_filtered.info
# Combine 2 reports, (re-)scanning all of the source files contained in the final report for exclusion markers
$ fastcov.py -C report1.json report2.json --scan-exclusion-markers -o report3.json
```

## Benchmarks

Anecdotal testing on my own projects indicate that fastcov is over 100x faster than lcov and over 30x faster than gcovr:

Project Size: ~250 .gcda, ~500 .gcov generated by gcov

Time to process all gcda and parse all gcov:

- fastcov: ~700ms
- lcov:    ~90s
- gcovr:   ~30s

Your mileage may vary depending on the number of cores you have available for fastcov to use!