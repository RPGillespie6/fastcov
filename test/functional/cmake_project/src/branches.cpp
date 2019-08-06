#include <foobar.h>
#include <string>
#include <vector>

using namespace std;

struct A {
   vector<string> reference_tokens;
};

int branchfoo(const string & str)
{
    A a;
    vector<string> initializer_list = {"a", "b", "c"};
    a.reference_tokens = {initializer_list[0]}; // This line will contain 4 non-exceptional branches, two of which are unreachable: [ + + ] [ - - ]

    int x = 0;
    if (str == "hello")
        x = 1;
    else if (str == "world")
        x = 2;
    else
        x = 3;

    int z = 0;
    for (int i=0; i<x; i++)
        z += 2*i;

    int f = 0;
    while (z > 0) {
        f++;
        z--;
    }

    try {
        if (str == "throw" && initializer_list[0] == "a")
            throw str;
    }
    catch (const string & ex) {
        f++;
    }

    // Switch statements can be used to create odd number of branches
    switch (f) {
        case 0:
            f++;
            break;
        case 1:
            f--;
            break;
        default:
            f -= 2;
            break;
    }

    return f;
}