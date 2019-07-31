#!/bin/bash

# Print every line
set -x

# Fail on first error
set -e

# Run all unit tests
cd unit
./run_all.sh

# Run all functional Tests
cd ../functional
./run_all.sh