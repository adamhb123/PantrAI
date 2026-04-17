FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

# Install Python 3.12 + system dependencies
# Ubuntu 24.04 ships Python 3.12 natively — no PPA needed
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3-pip \
        curl \
        zstd \
        unzip \
        libgl1 \
        libglib2.0-0 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install ngrok
RUN curl -Lo /tmp/ngrok.zip \
        https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip \
    && unzip /tmp/ngrok.zip -d /usr/local/bin \
    && rm /tmp/ngrok.zip

# Install Python dependencies
RUN pip install --no-cache-dir --break-system-packages \
        fastapi \
        uvicorn[standard] \
        ollama \
        numpy \
        opencv-python-headless \
        python-dotenv

WORKDIR /app

# Copy application source (exclude test images and notes)
COPY api.py llm.py prompts.py util.py ./

# Copy env file as the default; users can override via --env-file or -e flags
COPY llm.template.env llm.env

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ollama model storage — mount a named volume here to persist models across
# container rebuilds.
#
# Requires NVIDIA Container Toolkit on the host.
#
#   docker run -d --name pantrai-llm --restart always \
#     --gpus all \
#     --shm-size=8g \
#     -e NGROK_AUTHTOKEN=<your_token> \
#     -e NGROK_DOMAIN=<your_static_domain> \
#     -v pantrai_ollama:/root/.ollama \
#     pantrai-llm
VOLUME ["/root/.ollama"]

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
