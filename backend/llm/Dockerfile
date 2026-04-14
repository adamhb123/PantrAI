FROM python:3.12-slim

# Install system dependencies: nginx, curl (for Ollama installer), libGL for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx \
        curl \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install Python dependencies
RUN pip install --no-cache-dir \
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

# Nginx config — replaces the default site
COPY nginx.conf /etc/nginx/sites-available/default

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ollama model storage — mount a named volume here to persist models across
# container rebuilds:  -v pantrai_ollama:/root/.ollama
VOLUME ["/root/.ollama"]

# Expose only the nginx port to the host
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
