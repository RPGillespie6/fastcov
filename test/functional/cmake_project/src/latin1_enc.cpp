// NOTE: ררר This file has been saved with the latin1 (ISO 8859-11) encoding ררר
// Do not change the encoding or delete the non-utf8 characters

#include <foobar.h>

int latinfoo(bool take_branch)
{
    int x = 0;

    for (int i = 0; i < 1000; i++) {
        x += 2*i; //LCOV_EXCL_LINE

        if (take_branch) //LCOV_EXCL_BR_LINE
            x += i;
    }

    //LCOV_EXCL_START
    for (int i = 0; i < 1000; i++) {
        x -= 2*i;

        if (take_branch)
            x--;
    }
    //LCOV_EXCL_STOP

    for (int i = 0; i < 1000; i++) { //LCOV_EXCL_STOP (dangling stop - should be ignored)
        x -= (i % 2) ? 1 : 2;

        if (take_branch)
            x++;
    }

    return x;
}