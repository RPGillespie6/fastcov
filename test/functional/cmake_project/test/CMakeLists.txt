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

add_executable(latin1_test
    ../src/latin1_enc.cpp
    latin1_test.cpp
)

add_test(NAME ctest_2 COMMAND latin1_test)