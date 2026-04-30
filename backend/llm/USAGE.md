# LLM Service — Docker Usage

> **Note:** adjust the build context path (`backend/llm/`) if running from a different working directory.

The API runs on port 8000 inside the container and is exposed externally via ngrok.
Ollama model data is stored in a named volume (`pantrai_ollama`) so it persists across rebuilds.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `NGROK_AUTHTOKEN` | Yes | ngrok auth token — tunnel won't start without it |
| `NGROK_DOMAIN` | No | Static ngrok domain; omit to get a random URL each run |
| `USE_GPU` | No | Set to `0` to force CPU mode at runtime (default: `1`) |

---

## Linux (`Dockerfile`)

### GPU (default)
Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) on the host.

```bash
docker build -t pantrai-llm -f Dockerfile backend/llm/

docker run -d --name pantrai-llm --restart always \
  --gpus all --shm-size=8g \
  -e NGROK_AUTHTOKEN=<your_token> \
  -e NGROK_DOMAIN=<your_static_domain> \
  -v pantrai_ollama:/root/.ollama \
  pantrai-llm
```

### CPU
```bash
docker build --build-arg GPU=0 -t pantrai-llm-cpu -f Dockerfile backend/llm/

docker run -d --name pantrai-llm --restart always \
  --shm-size=8g \
  -e NGROK_AUTHTOKEN=<your_token> \
  -e NGROK_DOMAIN=<your_static_domain> \
  -v pantrai_ollama:/root/.ollama \
  pantrai-llm-cpu
```

---

## Windows (`Dockerfile.windows`)

Requires Docker Desktop with the WSL2 backend enabled.
GPU mode additionally requires [NVIDIA Container Toolkit for WSL2](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

### GPU (default) — PowerShell
```powershell
docker build -t pantrai-llm-win -f Dockerfile.windows backend/llm/

docker run -d --name pantrai-llm --restart always `
  --gpus all --shm-size=8g `
  -e NGROK_AUTHTOKEN=<your_token> `
  -e NGROK_DOMAIN=<your_static_domain> `
  -v pantrai_ollama:/root/.ollama `
  pantrai-llm-win
```

### CPU — PowerShell
```powershell
docker build --build-arg GPU=0 -t pantrai-llm-win-cpu -f Dockerfile.windows backend/llm/

docker run -d --name pantrai-llm --restart always `
  --shm-size=8g `
  -e NGROK_AUTHTOKEN=<your_token> `
  -e NGROK_DOMAIN=<your_static_domain> `
  -v pantrai_ollama:/root/.ollama `
  pantrai-llm-win-cpu
```

---

## Runtime GPU/CPU override

Force CPU mode on a GPU image without rebuilding:

```bash
# Linux
docker run ... -e USE_GPU=0 pantrai-llm

# Windows (PowerShell)
docker run ... -e USE_GPU=0 pantrai-llm-win
```

---

## Model persistence

The named volume `pantrai_ollama` stores the `gemma3:12b` model (~8 GB).
On first run the container pulls the model automatically; subsequent runs skip the pull.

To delete the volume and force a fresh download:
```bash
docker volume rm pantrai_ollama
```
