#!/bin/bash
set -e

# GPU/CPU mode — controlled by USE_GPU env var (default: 1 = GPU)
if [ "${USE_GPU:-1}" = "0" ]; then
    echo "CPU mode: disabling GPU for Ollama."
    export OLLAMA_NUM_GPU=0
else
    echo "GPU mode: Ollama will use available CUDA devices."
fi

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

# Start FastAPI in the background (internal only — ngrok handles external access)
uvicorn api:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Start ngrok in a retry loop so a transient failure (e.g. duplicate session)
# doesn't kill the container. Retries with backoff up to 5 times.
if [ -n "$NGROK_AUTHTOKEN" ]; then
    ngrok config add-authtoken "$NGROK_AUTHTOKEN"
    (
        RETRIES=0
        MAX_RETRIES=5
        BACKOFF=10
        while [ $RETRIES -lt $MAX_RETRIES ]; do
            echo "Starting ngrok (attempt $((RETRIES+1))/$MAX_RETRIES)..."
            DOMAIN_FLAG=""
            [ -n "$NGROK_DOMAIN" ] && DOMAIN_FLAG="--domain=$NGROK_DOMAIN"
            ngrok http 8000 --log=stdout $DOMAIN_FLAG &
            NGROK_PID=$!

            # Wait for tunnel to open, then print URL
            for i in $(seq 1 15); do
                URL=$(curl -s http://localhost:4040/api/tunnels \
                      | grep -o '"public_url":"[^"]*' \
                      | grep https \
                      | cut -d'"' -f4)
                if [ -n "$URL" ]; then
                    echo "------------------------------------"
                    echo "  ngrok public URL: $URL"
                    echo "------------------------------------"
                    break
                fi
                sleep 1
            done

            wait $NGROK_PID
            echo "ngrok exited. Retrying in ${BACKOFF}s..."
            sleep $BACKOFF
            RETRIES=$((RETRIES+1))
            BACKOFF=$((BACKOFF*2))
        done
        echo "ngrok failed after $MAX_RETRIES attempts. Container stays up without tunnel."
    ) &
else
    echo "WARNING: NGROK_AUTHTOKEN not set — tunnel not started."
    echo "  Pass it with: docker run -e NGROK_AUTHTOKEN=<token> ..."
fi

# Container lifetime is tied to uvicorn only — ngrok failures won't restart the container
wait $UVICORN_PID
kill $OLLAMA_PID 2>/dev/null
