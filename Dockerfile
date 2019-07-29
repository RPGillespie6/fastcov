FROM ubuntu:disco

MAINTAINER Bryan Gillespie <rpgillespie6@gmail.com>

RUN apt-get update && \
    apt-get install -y g++ python3 python3-pip cmake ninja-build lcov && \
    pip3 install pytest pytest-cov

#This layer will go away when GCC 9+ becomes default
RUN apt-get install -y gcc-9 g++-9