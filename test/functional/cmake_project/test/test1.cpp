
#include <foobar.h>
#include <cassert>

using namespace std;

int main()
{
    foo(false);
    for (int i = 0; i < 10; i++) {
        bar(true, i, 1);
    }

    return 0;
}
