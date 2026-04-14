#!/bin/bash
set -e

# Start Ollama in the background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
until ollama list > /dev/null 2>&1; do
    sleep 1
done

# Pull the model if not already present in the persistent volume
if ! ollama list | grep -q "gemma3:12b"; then
    echo "Pulling gemma3:12b..."
    ollama pull gemma3:12b
else
    echo "gemma3:12b already present, skipping pull."
fi

# Start FastAPI with uvicorn
uvicorn api:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Start nginx in the foreground (keeps container alive)
nginx -g "daemon off;" &
NGINX_PID=$!

# If any process exits, shut down the rest
wait -n
kill $OLLAMA_PID $UVICORN_PID $NGINX_PID 2>/dev/null
