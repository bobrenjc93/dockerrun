"""End-to-end test for building PyTorch from source in a Docker container."""

import pytest
from dockerrun import DockerRunner


# PyTorch build script with repo cloning
PYTORCH_BUILD_SCRIPT = r"""#!/bin/bash
set -e

PYTHON_BIN=python3
VENV_DIR=venv
USE_NINJA=1

echo "=== Installing git ==="
apt-get update
apt-get install -y git

echo "=== Cloning PyTorch repository ==="
git clone --depth 1 https://github.com/pytorch/pytorch.git
cd pytorch

echo "=== Installing system dependencies ==="
apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-dev \
  python3-pip \
  build-essential \
  cmake \
  ninja-build \
  libopenblas-dev \
  libomp-dev \
  libffi-dev \
  libjpeg-dev \
  zlib1g-dev

echo "=== Initializing submodules ==="
git submodule sync
git submodule update --init --recursive

echo "=== Creating virtual environment ==="
$PYTHON_BIN -m venv $VENV_DIR
source $VENV_DIR/bin/activate

echo "=== Upgrading pip tooling ==="
pip install --upgrade pip setuptools wheel

echo "=== Installing Python requirements ==="
pip install -r requirements.txt
pip install --group dev
pip install pytest

echo "=== Building PyTorch in develop mode ==="
if [ "$USE_NINJA" -eq 1 ]; then
  USE_NINJA=1 python setup.py develop
else
  python setup.py develop
fi

echo "=== Verifying torch import ==="
python - <<'EOF'
import torch
print("torch version:", torch.__version__)
print(torch.rand(2))
EOF

echo "=== Running PyTorch tensor tests ==="
pytest test/test_autograd.py -q

echo "=== Build and tests completed successfully ==="
"""


class TestPyTorchBuildE2E:
    """End-to-end tests for building PyTorch from source."""

    @pytest.fixture
    def runner(self):
        """Create a DockerRunner instance with extended timeout for long builds."""
        # PyTorch build can take a very long time (hours), set timeout accordingly
        return DockerRunner(timeout=14400)  # 4 hours

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.skip(reason="Long-running test: builds PyTorch from source (~2-4 hours). Run with --run-e2e flag.")
    def test_pytorch_build_from_source(self, runner):
        """
        Test building PyTorch from source on Ubuntu.
        
        This test:
        1. Clones the PyTorch repository
        2. Installs system dependencies
        3. Initializes git submodules
        4. Creates a Python virtual environment
        5. Installs Python dependencies
        6. Builds PyTorch in develop mode
        7. Verifies torch can be imported
        8. Runs basic tensor tests
        
        Note: This is a very long-running test (2-4 hours depending on hardware).
        """
        # Use Ubuntu 22.04 LTS as the base image
        image = "ubuntu:22.04"
        
        # Collect output for debugging
        output_chunks = []
        
        def on_output(chunk):
            output_chunks.append(chunk.decode())
            # Print output in real-time for visibility during long test
            print(chunk.decode(), end="", flush=True)
        
        result = runner.run_with_callback(
            image,
            ["bash", "-c", PYTORCH_BUILD_SCRIPT],
            on_output=on_output,
            environment={
                "DEBIAN_FRONTEND": "noninteractive",
                "TZ": "UTC",
            },
        )
        
        full_output = "".join(output_chunks)
        
        # Assert build completed successfully
        assert result.exit_code == 0, f"Build failed with exit code {result.exit_code}.\nOutput:\n{full_output}"
        assert "torch version:" in full_output, "Torch version verification failed"
        assert "Build and tests completed successfully" in full_output, "Build did not complete"

    @pytest.mark.e2e
    def test_pytorch_clone_and_deps_only(self, runner):
        """
        Lighter e2e test that only clones PyTorch and installs dependencies.
        
        This is a faster sanity check that verifies the Docker runner can handle
        a substantial workload without actually building PyTorch.
        """
        # Simplified script that just clones and installs deps
        script = r"""#!/bin/bash
set -e

echo "=== Installing git ==="
apt-get update
apt-get install -y git

echo "=== Cloning PyTorch repository (shallow) ==="
git clone --depth 1 https://github.com/pytorch/pytorch.git
cd pytorch

echo "=== Installing system dependencies ==="
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip

echo "=== Creating virtual environment ==="
python3 -m venv venv
source venv/bin/activate

echo "=== Upgrading pip ==="
pip install --upgrade pip setuptools wheel

echo "=== Installing requirements.txt ==="
pip install -r requirements.txt
pip install --group dev

echo "=== Verifying installation ==="
pip list | head -20

echo "=== Clone and dependency installation completed ==="
"""
        
        image = "ubuntu:22.04"
        
        output_chunks = []
        
        def on_output(chunk):
            output_chunks.append(chunk.decode())
            print(chunk.decode(), end="", flush=True)
        
        result = runner.run_with_callback(
            image,
            ["bash", "-c", script],
            on_output=on_output,
            environment={
                "DEBIAN_FRONTEND": "noninteractive",
                "TZ": "UTC",
            },
            # 30 minute timeout for clone + deps
            timeout=1800,
        )
        
        full_output = "".join(output_chunks)
        
        assert result.exit_code == 0, f"Failed with exit code {result.exit_code}.\nOutput:\n{full_output}"
        assert "Clone and dependency installation completed" in full_output

