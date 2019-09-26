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

# Erase coverage
coverage erase

# Generate GCDA
ctest

# Test zerocounters
test `find . -name *.gcda | wc -l` -ne 0
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters
test `find . -name *.gcda | wc -l` -eq 0

# Run ctest_1
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters  # Clear previous test coverage
ctest -R ctest_1

# Test (basic report generation - no branches)
coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test1.actual.info
cmp test1.actual.info ${TEST_DIR}/expected_results/test1.expected.info

coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude cmake_project/test/ --gcov-raw -o test1.actual.gcov.json
${TEST_DIR}/json_cmp.py test1.actual.gcov.json test1.actual.gcov.json #Just check we can parse it for now... gcov race conditions make it hard to compare against expected

coverage run --append ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude cmake_project/test/ -o test1.actual.fastcov.json
${TEST_DIR}/json_cmp.py test1.actual.fastcov.json ${TEST_DIR}/expected_results/test1.expected.fastcov.json

# Test (basic report info - with branches)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test2.actual.info
cmp test2.actual.info ${TEST_DIR}/expected_results/test2.expected.info

coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --gcov-raw -o test2.actual.gcov.json
${TEST_DIR}/json_cmp.py test2.actual.gcov.json test2.actual.gcov.json #Just check we can parse it for now... gcov race conditions make it hard to compare against expected

coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ -o test2.actual.fastcov.json
${TEST_DIR}/json_cmp.py test2.actual.fastcov.json ${TEST_DIR}/expected_results/test2.expected.fastcov.json

# Test (basic lcov info - with branches; equivalent --include)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --include src/ --lcov -o test3.actual.info
cmp test3.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; equivalent --exclude-gcda)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude-gcda test1.cpp.gcda --lcov -o test4.actual.info
cmp test4.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; equivalent --source-files)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --source-files ../src/source1.cpp ../src/source2.cpp --lcov -o test5.actual.info
cmp test5.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; gcno untested file coverage)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --source-files ../src/source1.cpp ../src/source2.cpp ../src/untested.cpp --lcov -o untested.actual.info
cmp untested.actual.info ${TEST_DIR}/expected_results/untested.expected.info

# Test (basic lcov info - with branches; gcno untested file coverage; equivalent --gcda-files)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --gcda-files ./test/CMakeFiles/test1.dir/__/src/source1.cpp.gcno ./test/CMakeFiles/test1.dir/__/src/source2.cpp.gcno ./src/CMakeFiles/untested.dir/untested.cpp.gcno --lcov -o untested2.actual.info
cmp untested2.actual.info ${TEST_DIR}/expected_results/untested.expected.info

# Test (gcov version fail)
if coverage run --append ${TEST_DIR}/fastcov.py --gcov ${TEST_DIR}/fake-gcov.sh ; then
    echo "Expected gcov version check to fail"
    exit 1
fi

# Run ctest_2
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters  # Clear previous test coverage
ctest -R ctest_2

# Check that the file has the right encoding
ENCODING=$(file --mime-encoding ../src/latin1_enc.cpp)
if [ "${ENCODING}" != "../src/latin1_enc.cpp: iso-8859-1" ]; then
    echo "Expected file to have non-utf8 encoding"
    exit 1
fi

# Test (lcov info - with non-utf8 encoding and fallback)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --fallback-encodings latin1 --lcov -o test8.actual.info
cmp test8.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Test (lcov info - with non-utf8 encoding and no fallback)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test9.actual.info
cmp test9.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Run ctest_3
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters # Clear previous test coverage
ctest -R ctest_3

# Test (lcov info - with inclusive branch filtering)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --include-br-lines-starting-with if else --lcov -o include_branches_sw.actual.info
cmp include_branches_sw.actual.info ${TEST_DIR}/expected_results/include_branches_sw.expected.info

# Test (lcov info - with exclusive branch filtering)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --exclude-br-lines-starting-with for if else --lcov -o exclude_branches_sw.actual.info
cmp exclude_branches_sw.actual.info ${TEST_DIR}/expected_results/exclude_branches_sw.expected.info

# Test (lcov info - with smart branch filtering)
coverage run --append ${TEST_DIR}/fastcov.py --branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --lcov -o filter_branches.actual.info
cmp filter_branches.actual.info ${TEST_DIR}/expected_results/filter_branches.expected.info

# Run ctest_all
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters # Clear previous test coverage
ctest # Run all

# Test (multiple tests touching same source)
coverage run --append ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --source-files ../src/source1.cpp --lcov -o multitest.actual.info
cmp multitest.actual.info ${TEST_DIR}/expected_results/multitest.expected.info

# Write out coverage as xml
coverage xml -o coverage.xml