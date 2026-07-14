#!/bin/bash

# Print every line, fail if any line fails
set -xe

# Save for later
BASE_DIR=${PWD}

# Build CMake Project
export CC=${CC:-gcc}
export CXX=${CXX:-g++}
GCOV=${GCOV:-gcov}
cd cmake_project
rm -rf build/
mkdir build && cd build
cmake .. -G Ninja
ninja

# Run unit tests
ctest

# Run fastcov with smart branch filtering, as well as system header (/usr/include) and cmake project test file filtering
# ${BASE_DIR}/fastcov.py -t ExampleTest --gcov "${GCOV}" --branch-coverage --include cmake_project/src/ --verbose --lcov -o example.info
${BASE_DIR}/fastcov.py -t ExampleTest --gcov "${GCOV}" --branch-coverage --exclude /usr/include cmake_project/test/ --verbose --lcov -o example.info

# Generate report with lcov's genhtml
genhtml --branch-coverage example.info -o coverage_report

echo "Now open ${PWD}/coverage_report/index.html in a browser"
