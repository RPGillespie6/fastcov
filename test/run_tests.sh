#!/bin/bash

# Print every line
set -x

# Fail on first error
set -e

# Check that example project builds
cd ../example
./build.sh

# Run all unit tests
cd ../test/unit
./run_all.sh

# Run all functional Tests
cd ../functional
./run_all.sh