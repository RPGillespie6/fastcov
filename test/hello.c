#include <stdio.h>

static void print_hello(int again) {
  // Branch coverage, two possible branches
  printf("Hello%s!\n", again ? " again" : "");
}

int main(int argc, char **argv) {
  print_hello(0);
  print_hello(1);
  return 0;
}
