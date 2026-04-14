# Build
docker build -t pantrai-llm backend/llm/

# Run with a named volume so the model persists across rebuilds
docker run -p 8080:80 -v pantrai_ollama:/root/.ollama pantrai-llm