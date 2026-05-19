#!/bin/bash

set -e

MODELS_DIR="${1:-$HOME/parakeet/models}"
mkdir -p "$MODELS_DIR"
CONTAINER_NAME="parakeet-v2"
PORT="${2:-5092}"

echo "=== Parakeet v2 (English only) Setup ==="

mkdir -p "$MODELS_DIR"

echo "Downloading v2 models to $MODELS_DIR..."
cd "$MODELS_DIR"

curl -L -f -o config.json "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/main/config.json"
curl -L -f -o vocab.txt "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/main/vocab.txt"
curl -L -f -o nemo128.onnx "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/main/nemo128.onnx"
curl -L -f -o encoder-model.int8.onnx "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/main/encoder-model.int8.onnx"
curl -L -f -o decoder_joint-model.int8.onnx "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/main/decoder_joint-model.int8.onnx"

echo "Models downloaded."

echo "Stopping existing container if any..."
podman rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "Starting parakeet container..."
podman run -d --name "$CONTAINER_NAME" \
    -p "$PORT":5092 \
    -v "$MODELS_DIR:/models:Z" \
    ghcr.io/achetronic/parakeet:latest

echo "Waiting for server to start..."
sleep 5

if curl -s http://localhost:"$PORT"/health | grep -q "ok"; then
    echo "=== Parakeet v2 is running at http://localhost:$PORT ==="
else
    echo "Container failed to start. Check logs with: podman logs $CONTAINER_NAME"
    exit 1
fi