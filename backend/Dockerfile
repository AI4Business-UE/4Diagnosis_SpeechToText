FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt update && apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    redis-tools \
    && apt clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/

RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8010

CMD ["bash", "-c", "PYTHONPATH=src daphne -b 0.0.0.0 -p 8010 stt.asgi:application"]
