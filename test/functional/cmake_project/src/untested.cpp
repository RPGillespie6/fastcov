/*
    An untested file
*/

int untestedFoo(int y)
{
    int x = 4;
    x += y * 2;

    if (x > 99)
        return -1;

    return x;
}

void untestedExcluded() {}  // LCOV_EXCL_LINE

// LCOV_EXCL_START
void untestedRangeExcluded() {}
// LCOV_EXCL_STOP
