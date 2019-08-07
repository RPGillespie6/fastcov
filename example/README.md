## Example Project

This directory contains a complete working CMake example project.

This guide will walk you through building the project and generating coverage using the fastcov docker image.

1. Ensure that the fastcov docker image is installed

```bash
$ docker pull rpgillespie6/fastcov
```
If it is installed, it should say `Status: Image is up to date for rpgillespie6/fastcov:latest`. If you don't have docker, follow the installation instructions for your Linux distribution [here](https://docs.docker.com/install/linux/docker-ce/ubuntu/).

2. Start an instance of the image from the *base fastcov directory*

Right now you are reading this README in the `example/` directory. Back up one directory before launching the docker container so the soft links pointing to `fastcov.py` work inside the container.

Launch the instance with:

```bash
$ docker run -it --rm -v ${PWD}:/mnt/workspace -w /mnt/workspace -u $(id -u ${USER}):$(id -g ${USER}) rpgillespie6/fastcov
```

This should place you inside the docker container (you can press ctrl-D to exit the container)

3. Build the example project with the provided script

```bash
$ cd example/
$ ./build.sh
```

4. Exit the docker container with ctrl-D

5. Open the coverage report with a browser

If you have Firefox installed, you can simply do:

```bash
$ firefox example/cmake_project/build/coverage_report/index.html
```

6. Play around with fastcov's filtering options in build.sh

Fastcov comes with a lot of filtering options. This example uses filtering options that automatically remove system headers, "noisy" branches, and test files. Try removing the various filtering options (or adding new ones) to see how the coverage report changes!

That's it - Happy Testing!