#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ask() {
    local prompt="$1" default="$2" var
    if [ -n "$default" ]; then
        read -rp "$prompt [$default]: " var
        echo "${var:-$default}"
    else
        read -rp "$prompt: " var
        echo "$var"
    fi
}

ask_required() {
    local prompt="$1" var
    while true; do
        read -rp "$prompt: " var
        [ -n "$var" ] && break
        echo "  This field is required." >&2
    done
    echo "$var"
}

ask_yn() {
    local prompt="$1" default="${2:-y}" var
    while true; do
        read -rp "$prompt [y/n] (default: $default): " var
        var="${var:-$default}"
        case "$var" in
            y|Y) echo "y"; return ;;
            n|N) echo "n"; return ;;
            *) echo "  Please enter y or n." >&2 ;;
        esac
    done
}

separator() { echo; echo "----------------------------------------------"; echo; }

# ---------------------------------------------------------------------------
# CUDA version detection
# ---------------------------------------------------------------------------
# Maps the host's CUDA driver version (from nvidia-smi) to the closest
# nvidia/cuda Docker image tag that supports ubuntu24.04 (requires CUDA >= 12.3).
# Falls back to the latest known tag if nvidia-smi is absent or unrecognised.

CUDA_IMAGE_DEFAULT="nvidia/cuda:12.8.0-runtime-ubuntu24.04"

detect_cuda_image() {
    if ! command -v nvidia-smi &>/dev/null; then
        echo "$CUDA_IMAGE_DEFAULT"
        return
    fi

    local cuda_ver
    cuda_ver=$(nvidia-smi 2>/dev/null | grep -oP "CUDA Version: \K[\d.]+") || true

    if [ -z "$cuda_ver" ]; then
        echo "  Warning: nvidia-smi found but CUDA version unreadable. Using default." >&2
        echo "$CUDA_IMAGE_DEFAULT"
        return
    fi

    local major minor
    major=$(echo "$cuda_ver" | cut -d. -f1)
    minor=$(echo "$cuda_ver" | cut -d. -f2)

    # ubuntu24.04 CUDA images — major.minor → latest patch tag
    case "${major}.${minor}" in
        12.8|12.9|12.10) echo "nvidia/cuda:12.8.0-runtime-ubuntu24.04" ;;
        12.6|12.7)       echo "nvidia/cuda:12.6.3-runtime-ubuntu24.04" ;;
        12.5)            echo "nvidia/cuda:12.5.1-runtime-ubuntu24.04" ;;
        12.4)            echo "nvidia/cuda:12.4.1-runtime-ubuntu24.04" ;;
        12.3)            echo "nvidia/cuda:12.3.2-runtime-ubuntu24.04" ;;
        *)
            echo "  Warning: CUDA ${major}.${minor} has no ubuntu24.04 image (need >= 12.3)." >&2
            echo "  Using default: $CUDA_IMAGE_DEFAULT" >&2
            echo "$CUDA_IMAGE_DEFAULT"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# OS detection — picks Dockerfile and adjusts gpu flag syntax
# ---------------------------------------------------------------------------

case "$(uname -s)" in
    Linux*)  OS=linux ;;
    Darwin*) OS=linux ;;   # macOS uses the Linux dockerfile
    MINGW*|MSYS*|CYGWIN*) OS=windows ;;
    *)       OS=linux ;;
esac

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

echo
echo "  PantrAI LLM — build & run"
separator

# ---------------------------------------------------------------------------
# GPU or CPU?
# ---------------------------------------------------------------------------

echo "Compute backend"
echo "  GPU requires NVIDIA Container Toolkit (+ WSL2 on Windows)."
echo "  CPU works everywhere but is significantly slower for gemma3:12b."
echo
USE_GPU_CHOICE=$(ask_yn "Use GPU?" "y")
if [ "$USE_GPU_CHOICE" = "y" ]; then
    GPU_BUILD_ARG=1
    GPU_LABEL="GPU"
    echo
    echo "Detecting host CUDA version..."
    CUDA_IMAGE=$(detect_cuda_image)
    echo "  Using image: $CUDA_IMAGE"
else
    GPU_BUILD_ARG=0
    GPU_LABEL="CPU"
    CUDA_IMAGE=""
fi

separator

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

echo "ngrok configuration"
echo "  NGROK_AUTHTOKEN is required to expose the API externally."
echo "  Get one at https://dashboard.ngrok.com/get-started/your-authtoken"
echo
NGROK_AUTHTOKEN=$(ask_required "NGROK_AUTHTOKEN")

echo
echo "  NGROK_DOMAIN sets a static domain (optional)."
echo "  Leave blank to get a random URL on each run."
echo
NGROK_DOMAIN=$(ask "NGROK_DOMAIN" "")

separator

# ---------------------------------------------------------------------------
# Image name
# ---------------------------------------------------------------------------

if [ "$OS" = "windows" ]; then
    DOCKERFILE="Dockerfile.windows"
    DEFAULT_IMAGE="pantrai-llm-win"
    [ "$GPU_BUILD_ARG" = "0" ] && DEFAULT_IMAGE="pantrai-llm-win-cpu"
else
    DOCKERFILE="Dockerfile"
    DEFAULT_IMAGE="pantrai-llm"
    [ "$GPU_BUILD_ARG" = "0" ] && DEFAULT_IMAGE="pantrai-llm-cpu"
fi

echo "Image name"
IMAGE_NAME=$(ask "Tag to build and run" "$DEFAULT_IMAGE")

separator

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo "Summary"
echo "  OS:              $OS"
echo "  Dockerfile:      $DOCKERFILE"
echo "  Compute:         $GPU_LABEL"
if [ -n "$CUDA_IMAGE" ]; then
    echo "  CUDA image:      $CUDA_IMAGE"
fi
echo "  Docker image:    $IMAGE_NAME"
echo "  NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN:0:6}... (truncated)"
if [ -n "$NGROK_DOMAIN" ]; then
    echo "  NGROK_DOMAIN:   $NGROK_DOMAIN"
else
    echo "  NGROK_DOMAIN:   (random)"
fi
echo

CONFIRM=$(ask_yn "Proceed?" "y")
[ "$CONFIRM" = "n" ] && { echo "Aborted."; exit 0; }

separator

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

echo "Building $IMAGE_NAME ($GPU_LABEL) ..."
BUILD_ARGS=(--build-arg GPU="$GPU_BUILD_ARG")
[ -n "$CUDA_IMAGE" ] && BUILD_ARGS+=(--build-arg CUDA_IMAGE="$CUDA_IMAGE")

docker build \
    "${BUILD_ARGS[@]}" \
    -t "$IMAGE_NAME" \
    -f "$SCRIPT_DIR/$DOCKERFILE" \
    "$SCRIPT_DIR"

separator

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

# Remove any existing stopped container with the same name
if docker ps -a --format '{{.Names}}' | grep -q "^${IMAGE_NAME}$"; then
    echo "Removing existing container: $IMAGE_NAME"
    docker rm -f "$IMAGE_NAME"
fi

RUN_ARGS=(
    -d
    --name "$IMAGE_NAME"
    --restart always
    --shm-size=8g
    -e "NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN"
    -v pantrai_ollama:/root/.ollama
)

[ -n "$NGROK_DOMAIN" ] && RUN_ARGS+=(-e "NGROK_DOMAIN=$NGROK_DOMAIN")
[ "$GPU_BUILD_ARG" = "1" ] && RUN_ARGS+=(--gpus all)

echo "Starting container ..."
docker run "${RUN_ARGS[@]}" "$IMAGE_NAME"

separator

echo "Container started: $IMAGE_NAME"
echo
echo "Logs (Ctrl-C to stop following, container keeps running):"
echo "  docker logs -f $IMAGE_NAME"
echo
echo "Stop:"
echo "  docker stop $IMAGE_NAME"
echo
docker logs -f "$IMAGE_NAME"
