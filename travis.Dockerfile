# Ubuntu based image providing gcc-9 for testing

FROM ubuntu:disco

RUN apt-get update && \
    apt-get install -y \
    cmake \
    gcc-9 \
    lcov \
    python2 \
    python3

# Following is required in docker containers when locale is not set, for
# python sys.stdout.encoding to be not None. Another option is to use
# (sys.stdout.encoding or "utf-8") in python instead.
ENV PYTHONIOENCODING utf-8
