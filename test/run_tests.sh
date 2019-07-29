# Print every line
set -x

# Fail on first error
set -e

# Run all unit tests
cd unittest
pytest --cov=fastcov --cov-report xml:coverage.xml

# Run all functional Tests
cd ../functionaltest
pytest --cov=fastcov --cov-report xml:coverage.xml