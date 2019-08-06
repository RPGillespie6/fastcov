
#include <foobar.h>
#include <vector>

using namespace std;

int main()
{
    for (auto & v : {"hello", "xvy", "throw"}) {
        branchfoo(v);
    }

    return 0;
}
