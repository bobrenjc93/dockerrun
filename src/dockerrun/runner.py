"""Core Docker runner functionality."""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Callable

import docker
from docker.errors import ImageNotFound, APIError, ContainerError as DockerContainerError

from .exceptions import DockerRunError, ContainerError, ImageNotFoundError


class StreamType(Enum):
    """Type of output stream."""

    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass
class StreamChunk:
    """A chunk of output from the container."""

    data: bytes
    stream_type: StreamType

    def decode(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Decode the chunk data to string."""
        return self.data.decode(encoding, errors=errors)


@dataclass
class ContainerResult:
    """Result of running a container command."""

    exit_code: int
    stdout: bytes = field(default_factory=bytes)
    stderr: bytes = field(default_factory=bytes)

    @property
    def stdout_text(self) -> str:
        """Get stdout as decoded text."""
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def stderr_text(self) -> str:
        """Get stderr as decoded text."""
        return self.stderr.decode("utf-8", errors="replace")

    @property
    def success(self) -> bool:
        """Check if command succeeded (exit code 0)."""
        return self.exit_code == 0


class DockerRunner:
    """
    Run commands in Docker containers with streaming I/O.

    Example usage:
        runner = DockerRunner()

        # Simple run with result
        result = runner.run("ubuntu:20.04", ["echo", "hello"])
        print(result.stdout_text)
        print(f"Exit code: {result.exit_code}")

        # Streaming output
        for chunk in runner.run_stream("python:3.11", ["python", "-c", "print('hello')"]):
            print(chunk.decode(), end="")

        # With stdin
        result = runner.run("python:3.11", ["python"], stdin=b"print('from stdin')")
    """

    def __init__(
        self,
        docker_url: str | None = None,
        timeout: int = 60,
        auto_remove: bool = True,
    ):
        """
        Initialize DockerRunner.

        Args:
            docker_url: Docker daemon URL. If None, uses default socket.
            timeout: Default timeout for container operations in seconds.
            auto_remove: Automatically remove containers after exit.
        """
        self.timeout = timeout
        self.auto_remove = auto_remove

        try:
            if docker_url:
                self.client = docker.DockerClient(base_url=docker_url)
            else:
                self.client = docker.from_env()
        except docker.errors.DockerException as e:
            raise DockerRunError(f"Failed to connect to Docker: {e}") from e

    def _ensure_image(self, image: str) -> None:
        """Pull image if not available locally."""
        try:
            self.client.images.get(image)
        except ImageNotFound:
            try:
                self.client.images.pull(image)
            except APIError as e:
                raise ImageNotFoundError(f"Failed to pull image '{image}': {e}") from e

    def run(
        self,
        image: str,
        command: list[str] | str,
        stdin: bytes | None = None,
        environment: dict[str, str] | None = None,
        working_dir: str | None = None,
        volumes: dict[str, dict] | None = None,
        timeout: int | None = None,
        pull: bool = True,
        **kwargs,
    ) -> ContainerResult:
        """
        Run a command in a Docker container and wait for completion.

        Args:
            image: Docker image name (e.g., "ubuntu:20.04").
            command: Command to run as list or string.
            stdin: Optional bytes to send to container stdin.
            environment: Environment variables for the container.
            working_dir: Working directory inside container.
            volumes: Volume mounts (e.g., {"/host/path": {"bind": "/container/path", "mode": "rw"}}).
            timeout: Timeout in seconds (overrides default).
            pull: Whether to pull the image if not available locally.
            **kwargs: Additional arguments passed to docker container.run().

        Returns:
            ContainerResult with exit_code, stdout, and stderr.
        """
        if pull:
            self._ensure_image(image)

        timeout = timeout or self.timeout
        stdout_data = io.BytesIO()
        stderr_data = io.BytesIO()

        try:
            container = self.client.containers.run(
                image,
                command,
                detach=True,
                stdin_open=stdin is not None,
                environment=environment,
                working_dir=working_dir,
                volumes=volumes,
                **kwargs,
            )

            try:
                # Handle stdin if provided
                if stdin is not None:
                    socket = container.attach_socket(params={"stdin": 1, "stream": 1})
                    socket._sock.sendall(stdin)
                    socket._sock.close()

                # Wait for container to finish
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", -1)

                # Get logs
                stdout_data.write(container.logs(stdout=True, stderr=False))
                stderr_data.write(container.logs(stdout=False, stderr=True))

            finally:
                if self.auto_remove:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        except DockerContainerError as e:
            raise ContainerError(f"Container error: {e}", exit_code=e.exit_status) from e
        except APIError as e:
            raise DockerRunError(f"Docker API error: {e}") from e

        return ContainerResult(
            exit_code=exit_code,
            stdout=stdout_data.getvalue(),
            stderr=stderr_data.getvalue(),
        )

    def run_stream(
        self,
        image: str,
        command: list[str] | str,
        stdin: bytes | None = None,
        environment: dict[str, str] | None = None,
        working_dir: str | None = None,
        volumes: dict[str, dict] | None = None,
        pull: bool = True,
        demux: bool = True,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """
        Run a command in a Docker container with streaming output.

        Args:
            image: Docker image name (e.g., "ubuntu:20.04").
            command: Command to run as list or string.
            stdin: Optional bytes to send to container stdin.
            environment: Environment variables for the container.
            working_dir: Working directory inside container.
            volumes: Volume mounts.
            pull: Whether to pull the image if not available locally.
            demux: Whether to separate stdout and stderr streams.
            **kwargs: Additional arguments passed to docker container.run().

        Yields:
            StreamChunk objects containing output data and stream type.
        """
        if pull:
            self._ensure_image(image)

        try:
            container = self.client.containers.run(
                image,
                command,
                detach=True,
                stdin_open=stdin is not None,
                environment=environment,
                working_dir=working_dir,
                volumes=volumes,
                **kwargs,
            )

            try:
                # Handle stdin in background thread if provided
                if stdin is not None:
                    def send_stdin():
                        try:
                            socket = container.attach_socket(params={"stdin": 1, "stream": 1})
                            socket._sock.sendall(stdin)
                            socket._sock.close()
                        except Exception:
                            pass

                    stdin_thread = threading.Thread(target=send_stdin, daemon=True)
                    stdin_thread.start()

                # Stream logs
                for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                    if chunk:
                        yield StreamChunk(data=chunk, stream_type=StreamType.STDOUT)

            finally:
                if self.auto_remove:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        except DockerContainerError as e:
            raise ContainerError(f"Container error: {e}", exit_code=e.exit_status) from e
        except APIError as e:
            raise DockerRunError(f"Docker API error: {e}") from e

    def run_with_callback(
        self,
        image: str,
        command: list[str] | str,
        on_output: Callable[[StreamChunk], None],
        stdin: bytes | None = None,
        environment: dict[str, str] | None = None,
        working_dir: str | None = None,
        volumes: dict[str, dict] | None = None,
        timeout: int | None = None,
        pull: bool = True,
        **kwargs,
    ) -> ContainerResult:
        """
        Run a command with a callback for each output chunk.

        This combines streaming with getting the final result.

        Args:
            image: Docker image name.
            command: Command to run.
            on_output: Callback function called for each output chunk.
            stdin: Optional bytes to send to container stdin.
            environment: Environment variables.
            working_dir: Working directory inside container.
            volumes: Volume mounts.
            timeout: Timeout in seconds.
            pull: Whether to pull the image if not available locally.
            **kwargs: Additional arguments passed to docker container.run().

        Returns:
            ContainerResult with exit_code, stdout, and stderr.
        """
        if pull:
            self._ensure_image(image)

        timeout = timeout or self.timeout
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []

        try:
            container = self.client.containers.run(
                image,
                command,
                detach=True,
                stdin_open=stdin is not None,
                environment=environment,
                working_dir=working_dir,
                volumes=volumes,
                **kwargs,
            )

            try:
                # Handle stdin in background thread if provided
                if stdin is not None:
                    def send_stdin():
                        try:
                            socket = container.attach_socket(params={"stdin": 1, "stream": 1})
                            socket._sock.sendall(stdin)
                            socket._sock.close()
                        except Exception:
                            pass

                    stdin_thread = threading.Thread(target=send_stdin, daemon=True)
                    stdin_thread.start()

                # Stream and collect output
                for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                    if chunk:
                        stream_chunk = StreamChunk(data=chunk, stream_type=StreamType.STDOUT)
                        stdout_chunks.append(chunk)
                        on_output(stream_chunk)

                # Wait for container to finish
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", -1)

            finally:
                if self.auto_remove:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

        except DockerContainerError as e:
            raise ContainerError(f"Container error: {e}", exit_code=e.exit_status) from e
        except APIError as e:
            raise DockerRunError(f"Docker API error: {e}") from e

        return ContainerResult(
            exit_code=exit_code,
            stdout=b"".join(stdout_chunks),
            stderr=b"".join(stderr_chunks),
        )

    def close(self) -> None:
        """Close the Docker client connection."""
        self.client.close()

    def __enter__(self) -> "DockerRunner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

