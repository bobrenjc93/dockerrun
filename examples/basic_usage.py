#!/usr/bin/env python3
"""Basic usage examples for dockerrun."""

from dockerrun import DockerRunner


def example_simple_run():
    """Run a simple command and get the result."""
    print("=== Simple Run ===")
    runner = DockerRunner()

    result = runner.run("ubuntu:20.04", ["echo", "Hello from Docker!"])

    print(f"stdout: {result.stdout_text}")
    print(f"stderr: {result.stderr_text}")
    print(f"exit_code: {result.exit_code}")
    print(f"success: {result.success}")
    print()


def example_streaming():
    """Stream output in real-time."""
    print("=== Streaming Output ===")
    runner = DockerRunner()

    for chunk in runner.run_stream(
        "ubuntu:20.04",
        ["bash", "-c", "for i in 1 2 3 4 5; do echo \"Count: $i\"; sleep 0.5; done"],
    ):
        print(f"[stream] {chunk.decode()}", end="")
    print()


def example_with_stdin():
    """Send stdin to the container."""
    print("=== With Stdin ===")
    runner = DockerRunner()

    python_code = b"""
import sys
print("Reading from stdin...")
for line in sys.stdin:
    print(f"Got: {line.strip()}")
"""

    result = runner.run(
        "python:3.11-slim",
        ["python", "-c", python_code.decode()],
        stdin=b"line 1\nline 2\nline 3\n",
    )

    print(result.stdout_text)
    print()


def example_with_callback():
    """Use a callback for real-time output while also getting final result."""
    print("=== With Callback ===")
    runner = DockerRunner()

    def on_output(chunk):
        print(f"  [live] {chunk.decode()}", end="")

    result = runner.run_with_callback(
        "python:3.11-slim",
        ["python", "-c", "import time; [print(f'Step {i}') or time.sleep(0.3) for i in range(5)]"],
        on_output=on_output,
    )

    print(f"\nFinal result - exit_code: {result.exit_code}, total bytes: {len(result.stdout)}")
    print()


def example_with_environment():
    """Pass environment variables to the container."""
    print("=== With Environment Variables ===")
    runner = DockerRunner()

    result = runner.run(
        "ubuntu:20.04",
        ["bash", "-c", "echo \"Hello, $NAME! The secret is: $SECRET\""],
        environment={
            "NAME": "Developer",
            "SECRET": "42",
        },
    )

    print(result.stdout_text)
    print()


def example_error_handling():
    """Handle errors from failed commands."""
    print("=== Error Handling ===")
    runner = DockerRunner()

    # Command that exits with non-zero
    result = runner.run("ubuntu:20.04", ["bash", "-c", "echo 'error!' >&2; exit 1"])

    print(f"stdout: {result.stdout_text}")
    print(f"stderr: {result.stderr_text}")
    print(f"exit_code: {result.exit_code}")
    print(f"success: {result.success}")
    print()


def example_context_manager():
    """Use DockerRunner as a context manager."""
    print("=== Context Manager ===")

    with DockerRunner() as runner:
        result = runner.run("alpine:latest", ["echo", "Using context manager!"])
        print(result.stdout_text)

    print("Connection closed automatically")
    print()


if __name__ == "__main__":
    example_simple_run()
    example_streaming()
    example_with_stdin()
    example_with_callback()
    example_with_environment()
    example_error_handling()
    example_context_manager()

