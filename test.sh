#!/usr/bin/env sh

# Test fastcov against a basic hello world c app in various python versions

set -e
set +x

cd test
mkdir -p out
gcc-9 hello.c -coverage -o out/hello
./out/hello

for py in 2 3; do
    pyversion=$(python$py --version 2>&1)
    echo
    echo ">>Testing $pyversion"
    python$py ../fastcov.py -c $(pwd) --gcov gcov-9 --branch-coverage --lcov -o "$(pwd)/out/py"$py"_result.info"
    outdir="$(pwd)/out/py"$py"_html"
    genhtml --branch-coverage -p "$(cd ..; pwd)" -o $outdir "$(pwd)/out/py"$py"_result.info"
    echo "Results in file://$outdir/index.html for lcov results"
done
