FROM ubuntu:20.04

ENV TZ=Europe/Berlin

LABEL org.opencontainers.image.authors="Bryan Gillespie <rpgillespie6@gmail.com>"

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y g++ python3 python3-pip cmake ninja-build lcov && \
    pip3 install pytest pytest-cov