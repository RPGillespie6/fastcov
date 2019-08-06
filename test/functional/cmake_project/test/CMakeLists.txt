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

add_executable(branch_test
    ../src/branches.cpp
    branch_test.cpp
)

add_test(NAME ctest_3 COMMAND branch_test)

# Duplicate of test1... used to check that multiple tests touching same file increases coverage correctly
add_executable(multitest
    ../src/source1.cpp
    ../src/source2.cpp
    test1_2.cpp
)

add_test(NAME ctest_4 COMMAND multitest)