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

# Erase coverage
coverage erase

# Test 1 (basic lcov info - no branches)
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude test/ --lcov -o test1.actual.info
cmp test1.actual.info ${TEST_DIR}/expected_results/test1.expected.info

# Test 2 (zerocounters)
test `find . -name *.gcda | wc -l` -ne 0
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters
test `find . -name *.gcda | wc -l` -eq 0

# Test 3 (gcov version fail)
if coverage run --append ${TEST_DIR}/fastcov.py --gcov ${TEST_DIR}/fake-gcov.sh ; then
    echo "Expected gcov version check to fail"
    exit 1
fi

# Write out coverage as xml
coverage xml -o coverage.xml