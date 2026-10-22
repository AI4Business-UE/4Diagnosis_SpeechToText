FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    redis-tools \
    && apt clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY src /app
WORKDIR /app

EXPOSE 8000

ENTRYPOINT ["daphne", "-b", "0.0.0.0", "-p", "8000", "stt.asgi:application"]