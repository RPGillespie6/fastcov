#!/bin/bash

# Print every line
set -x

# Fail on first error
set -e

# Run all tests, generate coverage report
pytest --cov=fastcov --cov-report xml:coverage.xml