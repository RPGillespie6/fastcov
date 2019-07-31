include_directories(
    "."
    "../src"
)

add_executable(test1
    ../src/source1.cpp
    ../src/source2.cpp
    test1.cpp
)

add_test(NAME ctest_1 COMMAND test1)