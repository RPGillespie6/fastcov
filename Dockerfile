FROM zbeekman/nightly-gcc-trunk-docker-image

MAINTAINER Bryan Gillespie <rpgillespie6@gmail.com>

RUN apt-get update && \
    apt-get install -y python3 cmake lcov