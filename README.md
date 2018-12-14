# fastcov
A massively parallel gcov wrapper for generating intermediate coverage formats *fast*

The goal of fastcov is to generate code coverage intermediate formats *as fast as possible* (ideally < 1 second), even for large projects with hundreds of gcda objects. The intermediate formats may then be consumed by a report generator such as lcov's genhtml, or a dedicated front end such as coveralls.

Currently the only intermediate formats supported are gcov json format and lcov info format.

In order to achieve the massive speed gains, a few constraints apply:

1. GCC version >= 7.1.0 only (ideally >= 9.0.0 for maximum speed and correctness)

These versions of GCC have support for intemediate coverage formats in conjuction with multiple file passing to gcov.

2. Object files must be either be built:  
  a. Using absolute paths for all `-I` flags passed to the compiler  
  b. Invoking the compiler from the same root directory

If you use CMake, you are almost certainly satisfying the second constraint (unless you care about `ExternalProject` coverage).

3. (for GCC version < 9.0.0): *Potential* header file loss of correctness

This is because running gcov in parallel generates .gcov header reports in parallel which overwrite each other. This isn't a problem unless your header files have actual logic (i.e. header only library) that you want to measure coverage for. In this case it is highly recommended to use GCC >= 9.0.0 which will always generate correct header coverage. If this is not possible, use the `--headers` flag to specify which gcda files should not be run in parallel in order to capture accurate header file data just for those.

Sample Usage:
```bash
$ cd build_dir
$ find . -name *.gcda | xargs rm -f #Cleanup
$ fastcov.py --exclude /usr/include --lcov -o report.info
$ genhtml -o code_coverage report.info
```

## Benchmarks

Anecdotal testing on my own projects indicate that fastcov is over 100x faster than lcov and over 30x faster than gcovr:

Project Size: ~250 .gcda, ~500 .gcov

Time to process all gcda and parse all gcov:  
fastcov: ~700ms  
lcov:    ~90s  
gcovr:   ~30s
