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

# Get coverage config for multiprocessing
cp ../.coveragerc .

# Generate GCDA
ctest

# Test zerocounters
test `find . -name *.gcda | wc -l` -ne 0
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters
test `find . -name *.gcda | wc -l` -eq 0

# Run ctest_1
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters  # Clear previous test coverage
ctest -R ctest_1

# Create a fastcov JSON to be filtered later
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9 --verbose -o basic.fastcov.json

# Test (basic report generation - no branches)
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9 --verbose --exclude cmake_project/test/ --lcov -o test1.actual.info
cmp test1.actual.info ${TEST_DIR}/expected_results/test1.expected.info

coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9 --exclude cmake_project/test/ -o test1.actual.fastcov.json
${TEST_DIR}/json_cmp.py test1.actual.fastcov.json ${TEST_DIR}/expected_results/test1.expected.fastcov.json

# Test the setting of the "testname" field
coverage run -a ${TEST_DIR}/fastcov.py -t FunctionalTest1 --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test1.tn.actual.info
cmp test1.tn.actual.info ${TEST_DIR}/expected_results/test1.tn.expected.info

# Test (basic report info - with branches)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test2.actual.info
cmp test2.actual.info ${TEST_DIR}/expected_results/test2.expected.info

coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ -o test2.actual.fastcov.json
${TEST_DIR}/json_cmp.py test2.actual.fastcov.json ${TEST_DIR}/expected_results/test2.expected.fastcov.json

# Test (basic lcov info - with branches; equivalent --include)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --verbose --include src/ --lcov -o test3.actual.info
cmp test3.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; equivalent --exclude-gcda)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --verbose --exclude-gcda test1.cpp.gcda --lcov -o test4.actual.info
cmp test4.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; equivalent --source-files)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --verbose --source-files ../src/source1.cpp ../src/source2.cpp --lcov -o test5.actual.info
cmp test5.actual.info ${TEST_DIR}/expected_results/test2.expected.info

# Test (basic lcov info - with branches; gcno untested file coverage)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --source-files ../src/source1.cpp ../src/source2.cpp ../src/untested.cpp --lcov -o untested.actual.info
cmp untested.actual.info ${TEST_DIR}/expected_results/untested.expected.info

# Test (basic lcov info - with branches; gcno untested file coverage; equivalent --gcda-files)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --gcda-files ./test/CMakeFiles/test1.dir/__/src/source1.cpp.gcno ./test/CMakeFiles/test1.dir/__/src/source2.cpp.gcno ./src/CMakeFiles/untested.dir/untested.cpp.gcno --lcov -o untested2.actual.info
cmp untested2.actual.info ${TEST_DIR}/expected_results/untested.expected.info

# Test (gcov version fail)
if coverage run -a ${TEST_DIR}/fastcov.py --gcov ${TEST_DIR}/fake-gcov.sh ; then
    echo "Expected gcov version check to fail"
    exit 1
fi

# Combine operation - filtering
coverage run -a ${TEST_DIR}/fastcov.py -C basic.fastcov.json --exclude cmake_project/test/ -o basic.fastcov.actual.json
${TEST_DIR}/json_cmp.py basic.fastcov.actual.json ${TEST_DIR}/expected_results/basic.fastcov.expected.json

coverage run -a ${TEST_DIR}/fastcov.py -C basic.fastcov.json --include cmake_project/src/ -o basic.fastcov2.actual.json
${TEST_DIR}/json_cmp.py basic.fastcov2.actual.json ${TEST_DIR}/expected_results/basic.fastcov.expected.json

coverage run -a ${TEST_DIR}/fastcov.py -C basic.fastcov.json --source-files /mnt/workspace/test/functional/cmake_project/src/source2.cpp /mnt/workspace/test/functional/cmake_project/src/source1.cpp -o basic.fastcov3.actual.json
${TEST_DIR}/json_cmp.py basic.fastcov3.actual.json ${TEST_DIR}/expected_results/basic.fastcov.expected.json

# Combine operation
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/test2.expected.info ${TEST_DIR}/expected_results/test1.tn.expected.info --lcov -o combine1.actual.info
cmp combine1.actual.info ${TEST_DIR}/expected_results/combine1.expected.info

# Combine operation - Mix and Match json/info
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/test2.expected.fastcov.json ${TEST_DIR}/expected_results/test1.tn.expected.info --lcov -o combine1.actual.info
cmp combine1.actual.info ${TEST_DIR}/expected_results/combine1.expected.info

# Combine operation- source files across coverage reports
${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --source-files ../src/source1.cpp --lcov -o combine.source1.actual.info
${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --process-gcno --source-files ../src/source2.cpp --lcov -o combine.source2.actual.info
coverage run -a ${TEST_DIR}/fastcov.py -C combine.source1.actual.info combine.source2.actual.info --lcov -o combine2.actual.info
cmp combine2.actual.info ${TEST_DIR}/expected_results/combine2.expected.info

# Combine files with different function inclusion
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/combine3b.info ${TEST_DIR}/expected_results/combine3a.info --lcov -o combine3.actual.info
cmp combine3.actual.info ${TEST_DIR}/expected_results/combine3.expected.info

# Combine files with different test names
# Expected result generated with:
# lcov -a combine4a.info -a combine4b.info -a combine4c.info --rc lcov_branch_coverage=1 -o combine4.expected.info
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/combine4a.info ${TEST_DIR}/expected_results/combine4b.info ${TEST_DIR}/expected_results/combine4c.info --lcov -o combine4.actual.info
cmp combine4.actual.info ${TEST_DIR}/expected_results/combine4.expected.info

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
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --fallback-encodings latin1 --lcov -o test8.actual.info
cmp test8.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Test (lcov info - with non-utf8 encoding and no fallback)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude cmake_project/test/ --lcov -o test9.actual.info
cmp test9.actual.info ${TEST_DIR}/expected_results/latin1_test.expected.info

# Run ctest_3
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters # Clear previous test coverage
ctest -R ctest_3

# Test (lcov info - with inclusive branch filtering)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --include-br-lines-starting-with if else --lcov -o include_branches_sw.actual.info
cmp include_branches_sw.actual.info ${TEST_DIR}/expected_results/include_branches_sw.expected.info

# Test (lcov info - with exclusive branch filtering)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --exclude-br-lines-starting-with for if else --lcov -o exclude_branches_sw.actual.info
cmp exclude_branches_sw.actual.info ${TEST_DIR}/expected_results/exclude_branches_sw.expected.info

# Test (lcov info - with smart branch filtering)
coverage run -a ${TEST_DIR}/fastcov.py --branch-coverage --gcov gcov-9 --exclude /usr/include cmake_project/test/ --lcov -o filter_branches.actual.info
cmp filter_branches.actual.info ${TEST_DIR}/expected_results/filter_branches.expected.info

# Run ctest_all
${TEST_DIR}/fastcov.py --gcov gcov-9 --zerocounters # Clear previous test coverage
ctest # Run all

# Test (multiple tests touching same source)
coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --source-files ../src/source1.cpp --lcov -o multitest.actual.info
cmp multitest.actual.info ${TEST_DIR}/expected_results/multitest.expected.info

# Test missing source files during exclusion scan results in non-zero error code
rc=0
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/missing_files.json --scan-exclusion-markers -o missing.json || rc=$?
test $rc -eq 6

# Test (running data from other than build directory)
RUN_DIR=${PWD}
pushd ${TEST_DIR}
COVERAGE_FILE=${RUN_DIR}/.coverage.other_dir coverage run -a ${TEST_DIR}/fastcov.py --exceptional-branch-coverage --gcov gcov-9 --source-files cmake_project/src/source1.cpp --lcov -o ${RUN_DIR}/multitest_nonbuild_dir.actual.info
cmp ${RUN_DIR}/multitest_nonbuild_dir.actual.info ${TEST_DIR}/expected_results/multitest.expected.info
popd

# Test (error messages for missing sources)
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/missing_files.json --validate-sources -o missing.json 2>&1 | grep 'Cannot find' | grep "error" | wc -l > missing_files_count.log
mfc=$(cat missing_files_count.log)
test "$mfc" -eq "2"

# Test (output redirect return no error)
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9  --lcov -o redirected.output.info > redirected.output.info.log 2>redirected.output.info.log

# Test (default name for json)
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9
test -f "coverage.json"

# Test (default name for lcov)
coverage run -a ${TEST_DIR}/fastcov.py --gcov gcov-9 --lcov
test -f "coverage.info"

# Test (exclude using glob)
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/exclude_glob_test.info --lcov --exclude-glob '*/source*.cpp' -o exclude_glob_test.actual.info
cmp exclude_glob_test.actual.info ${TEST_DIR}/expected_results/exclude_glob_test.expected.info

# Test (print coverage info)
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/dump_coverage_test.json --lcov -o print_coverage.json -p 2>print_coverage.info.log
cat print_coverage.info.log | grep 'Files Coverage: 66.67%, 2/3'
cat print_coverage.info.log | grep 'Functions Coverage: 60.00%, 3/5'
cat print_coverage.info.log | grep 'Lines Coverage: 60.00%, 9/15'

# Test (diff filtering)
coverage run -a ${TEST_DIR}/fastcov.py -C ${TEST_DIR}/expected_results/diff_filter_data/basic.json --diff-filter ${TEST_DIR}/expected_results/diff_filter_data/exclude_each_item.diff --diff-base-dir /mnt/workspace -o exclude_each_item.actual.json
${TEST_DIR}/json_cmp.py exclude_each_item.actual.json ${TEST_DIR}/expected_results/diff_filter_data/exclude_each_item.expected.json

# Write out coverage as xml
coverage combine
coverage xml -o coverage.xml
coverage html # Generate HTML report