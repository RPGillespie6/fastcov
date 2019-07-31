#include <foobar.h>

int foo(bool take_branch)
{
    int x = 0;

    for (int i = 0; i < 1000; i++) {
        x += 2*i;

        if (take_branch)
            x += i;
    }

    return x;
}