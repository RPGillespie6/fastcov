## Example Project

This directory contains a complete working CMake example project.

This guide will walk you through building the project and generating coverage locally.

1. Ensure the required tools are installed

The example expects Python 3, GCC/G++, gcov, CMake, Ninja, and lcov/genhtml to be available on your path.

2. Build the example project with the provided script

```bash
$ cd example/
$ ./build.sh
```

3. Open the coverage report with a browser

If you have Firefox installed, you can simply do:

```bash
$ firefox example/cmake_project/build/coverage_report/index.html
```

4. Play around with fastcov's filtering options in build.sh

Fastcov comes with a lot of filtering options. This example uses filtering options that automatically remove system headers, "noisy" branches, and test files. Try removing the various filtering options (or adding new ones) to see how the coverage report changes!

That's it - Happy Testing!
