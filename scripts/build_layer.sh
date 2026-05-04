#!/bin/bash
set -e

LAYER_DIR="lambdas/shared_layer"
PYTHON_DIR="${LAYER_DIR}/python"

echo "Building Lambda Layer for linux/arm64..."

PIP_USER=false pip install \
  -r "${LAYER_DIR}/requirements.txt" \
  -t "${PYTHON_DIR}" \
  --platform manylinux2014_aarch64 \
  --only-binary=:all: \
  --python-version 3.12 \
  --upgrade \
  --quiet

echo "✅ Layer build complete (arm64). Run 'cdk deploy' to deploy."