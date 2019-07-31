#!/bin/bash

# Print every line
set -x

# Fail on first error
set -e

# Save for later
TEST_DIR=${PWD}

# Build CMake Project
export CC=/usr/bin/gcc-9
export CXX=/usr/bin/g++-9
cd cmake_project
rm -rf build/
mkdir build && cd build
cmake .. -G Ninja
ninja

# Run tests
ctest

# Capture coverage
coverage run ../../fastcov.py --gcov gcov-9 --exclude test/ --lcov -o test1.actual.info
cmp test1.actual.info ${TEST_DIR}/expected_results/test1.expected.info

# Write out coverage as xml
coverage xml -o coverage.xml