FROM mcr.microsoft.com/devcontainers/python:3.12

ENV PYTHONUNBUFFERED=1

RUN sudo apt-get update && \
    sudo apt-get install -y curl poppler-utils && \
    sudo rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip