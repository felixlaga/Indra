#!/bin/bash
# Lambda Labs A10 GPU Instance Setup Script
#
# Run this script on a fresh Lambda Labs instance to set up HaluGate:
#   curl -fsSL <raw-url-to-this-script> | bash
#
# Or clone the repo first:
#   git clone <repo-url> && cd <repo-name>
#   ./deploy/lambda-labs-setup.sh
#
# Cost: ~$0.75/hr for A10 GPU
# Performance: ~100-500ms per validation (vs 1-3s on CPU)

set -e

echo "=== HaluGate Lambda Labs Setup ==="

# Check if we're in the repo already
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Run this script from the repository root"
    echo "  git clone <repo-url> && cd <repo-name>"
    echo "  ./deploy/lambda-labs-setup.sh"
    exit 1
fi

# Check for NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "Warning: nvidia-smi not found. GPU may not be available."
else
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install dependencies
echo "Installing dependencies..."
uv pip install --system .
uv pip install --system fastapi uvicorn

# Set environment
export HALUGATE_DEVICE=cuda
export HALUGATE_USE_SENTINEL=true

# Print info
echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the server:"
echo "  HALUGATE_DEVICE=cuda uvicorn src.halugate.server:app --host 0.0.0.0 --port 8000"
echo ""
echo "To test:"
echo "  curl -X POST http://localhost:8000/validate \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"context\": \"The sky is blue.\", \"question\": \"What color is the sky?\", \"answer\": \"The sky is blue.\"}'"
echo ""
echo "From your local machine, use the instance's public IP:"
echo "  export HALUGATE_URL=http://<instance-ip>:8000"
echo "  MODEL_PROFILE=research-remote python main.py"
echo ""

# Start the server
echo "Starting HaluGate server..."
exec uvicorn src.halugate.server:app --host 0.0.0.0 --port 8000
