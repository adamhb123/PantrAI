# Build
Note: change path 'backend/llm/' depending on working directory

Windows:
`docker build -t pantrai-llm-win -f Dockerfile.windows backend/llm/`
Linux:
`docker build -t pantrai-llm-linux -f Dockerfile backend/llm/`


# Run
Windows:
`docker run -e NGROK_AUTHTOKEN=<\your_token> -v pantrai_ollama:/root/.ollama pantrai-llm-win`
Linux:
`docker run -e NGROK_AUTHTOKEN=<\your_token> -v pantrai_ollama:/root/.ollama pantrai-llm-linux`