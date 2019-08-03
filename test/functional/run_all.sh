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

# Run ctest_1
ctest -R ctest_1

# Erase coverage
coverage erase

# Test 1 (basic lcov info - no branches)
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude test/ --lcov -o test1.actual.info
cmp test1.actual.info ${TEST_DIR}/expected_results/test1.expected.info

# Test 2 (basic lcov info - with branches)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude test/ --lcov -o test2.actual.info
cmp test2.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test 3 (basic lcov info - with branches; equivalent --include)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --include src/ --lcov -o test3.actual.info
cmp test3.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test 4 (basic lcov info - with branches; equivalent --exclude-gcda)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude-gcda test1.cpp.gcda --lcov -o test4.actual.info
cmp test4.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test 5 (basic lcov info - with branches; equivalent --source-files)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --source-files ../src/source1.cpp ../src/source2.cpp --lcov -o test5.actual.info
cmp test5.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test 6 (zerocounters)
test `find . -name *.gcda | wc -l` -ne 0
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters
test `find . -name *.gcda | wc -l` -eq 0

# Test 7 (gcov version fail)
if coverage run --append ${TEST_DIR}/fastcov.py --gcov ${TEST_DIR}/fake-gcov.sh ; then
    echo "Expected gcov version check to fail"
    exit 1
fi

# Run ctest_2
ctest -R ctest_2

# Test 8 (lcov info - with non-utf8 encoding and fallback)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude test/ --fallback-encodings latin1 --lcov -o test8.actual.info
cmp test8.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Test 9 (lcov info - with non-utf8 encoding and no fallback)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude test/ --lcov -o test9.actual.info
cmp test9.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Write out coverage as xml
coverage xml -o coverage.xml