# dockerrun

Run commands in Docker containers with streaming stdin/stdout support.

## Installation

```bash
pip install dockerrun
```

## Quick Start

```python
from dockerrun import DockerRunner

# Create a runner
runner = DockerRunner()

# Run a simple command
result = runner.run("ubuntu:20.04", ["echo", "Hello, World!"])
print(result.stdout_text)  # "Hello, World!\n"
print(f"Exit code: {result.exit_code}")  # Exit code: 0
```

## Features

- **Simple API** - Just pick an image, pass a command, get results
- **Streaming output** - Process stdout/stderr as it arrives
- **Stdin support** - Send input to your containers
- **Full result access** - Exit codes, stdout, stderr all available
- **Context manager support** - Clean resource management

## Usage

### Basic Run

```python
from dockerrun import DockerRunner

runner = DockerRunner()

# Run a command and get the result
result = runner.run("python:3.11", ["python", "-c", "print('hello')"])

print(result.stdout_text)   # "hello\n"
print(result.stderr_text)   # ""
print(result.exit_code)     # 0
print(result.success)       # True
```

### Streaming Output

Process output in real-time as it's generated:

```python
from dockerrun import DockerRunner

runner = DockerRunner()

# Stream output as it arrives
for chunk in runner.run_stream("ubuntu:20.04", ["bash", "-c", "for i in 1 2 3; do echo $i; sleep 1; done"]):
    print(chunk.decode(), end="", flush=True)
```

### With Callback

Get streaming output while also collecting the final result:

```python
from dockerrun import DockerRunner

runner = DockerRunner()

def handle_output(chunk):
    print(f"[LIVE] {chunk.decode()}", end="")

result = runner.run_with_callback(
    "python:3.11",
    ["python", "-c", "import time; [print(i) or time.sleep(0.5) for i in range(5)]"],
    on_output=handle_output
)

print(f"\nFinal exit code: {result.exit_code}")
```

### Sending Stdin

```python
from dockerrun import DockerRunner

runner = DockerRunner()

# Send input to the container
result = runner.run(
    "python:3.11",
    ["python"],
    stdin=b"print('Hello from stdin!')\n"
)
print(result.stdout_text)  # "Hello from stdin!\n"
```

### Environment Variables

```python
from dockerrun import DockerRunner

runner = DockerRunner()

result = runner.run(
    "ubuntu:20.04",
    ["bash", "-c", "echo $MY_VAR"],
    environment={"MY_VAR": "my_value"}
)
print(result.stdout_text)  # "my_value\n"
```

### Volume Mounts

```python
from dockerrun import DockerRunner

runner = DockerRunner()

result = runner.run(
    "ubuntu:20.04",
    ["cat", "/data/myfile.txt"],
    volumes={"/host/path": {"bind": "/data", "mode": "ro"}}
)
```

### Context Manager

```python
from dockerrun import DockerRunner

with DockerRunner() as runner:
    result = runner.run("alpine:latest", ["echo", "hello"])
    print(result.stdout_text)
# Connection automatically closed
```

### Configuration

```python
from dockerrun import DockerRunner

runner = DockerRunner(
    docker_url="unix:///var/run/docker.sock",  # Custom Docker socket
    timeout=120,                                 # Default timeout in seconds
    auto_remove=True                             # Auto-remove containers after exit
)
```

## API Reference

### `DockerRunner`

#### `__init__(docker_url=None, timeout=60, auto_remove=True)`

- `docker_url`: Docker daemon URL. If None, uses default socket.
- `timeout`: Default timeout for container operations in seconds.
- `auto_remove`: Automatically remove containers after exit.

#### `run(image, command, stdin=None, environment=None, working_dir=None, volumes=None, timeout=None, pull=True, **kwargs) -> ContainerResult`

Run a command and wait for completion.

- `image`: Docker image name (e.g., "ubuntu:20.04")
- `command`: Command as list or string
- `stdin`: Optional bytes to send to stdin
- `environment`: Dict of environment variables
- `working_dir`: Working directory inside container
- `volumes`: Volume mount configuration
- `timeout`: Override default timeout
- `pull`: Whether to pull image if not available locally
- `**kwargs`: Additional arguments for Docker

#### `run_stream(image, command, ...) -> Iterator[StreamChunk]`

Run a command with streaming output. Same parameters as `run()`.

#### `run_with_callback(image, command, on_output, ...) -> ContainerResult`

Run with a callback for each output chunk. Same parameters as `run()` plus:

- `on_output`: Callback function `(StreamChunk) -> None`

### `ContainerResult`

- `exit_code: int` - Container exit code
- `stdout: bytes` - Raw stdout bytes
- `stderr: bytes` - Raw stderr bytes
- `stdout_text: str` - Decoded stdout string
- `stderr_text: str` - Decoded stderr string
- `success: bool` - True if exit_code == 0

### `StreamChunk`

- `data: bytes` - Chunk data
- `stream_type: StreamType` - STDOUT or STDERR
- `decode(encoding="utf-8") -> str` - Decode to string

## Error Handling

```python
from dockerrun import DockerRunner, DockerRunError, ContainerError, ImageNotFoundError

runner = DockerRunner()

try:
    result = runner.run("nonexistent:image", ["echo", "hello"])
except ImageNotFoundError as e:
    print(f"Image not found: {e}")
except ContainerError as e:
    print(f"Container error (exit code {e.exit_code}): {e}")
except DockerRunError as e:
    print(f"Docker error: {e}")
```

## Requirements

- Python 3.8+
- Docker installed and running
- `docker` Python package

## License

MIT License

