FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        cmake \
        file \
        g++ \
        gcc \
        lcov \
        ninja-build \
        python3 \
        python3-pip \
        python3-venv \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir coverage pytest pytest-cov \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /mnt/workspace
