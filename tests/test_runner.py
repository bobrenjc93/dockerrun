"""Tests for dockerrun."""

import pytest
from dockerrun import DockerRunner, ContainerResult, StreamType


class TestDockerRunner:
    """Tests for DockerRunner class."""

    @pytest.fixture
    def runner(self):
        """Create a DockerRunner instance."""
        return DockerRunner()

    def test_simple_echo(self, runner):
        """Test running a simple echo command."""
        result = runner.run("alpine:latest", ["echo", "hello"])

        assert result.exit_code == 0
        assert result.success is True
        assert result.stdout_text.strip() == "hello"
        assert result.stderr_text == ""

    def test_exit_code(self, runner):
        """Test that exit codes are captured correctly."""
        result = runner.run("alpine:latest", ["sh", "-c", "exit 42"])

        assert result.exit_code == 42
        assert result.success is False

    def test_stderr(self, runner):
        """Test that stderr is captured."""
        result = runner.run("alpine:latest", ["sh", "-c", "echo error >&2"])

        assert result.exit_code == 0
        assert result.stderr_text.strip() == "error"

    def test_environment_variables(self, runner):
        """Test passing environment variables."""
        result = runner.run(
            "alpine:latest",
            ["sh", "-c", "echo $MY_VAR"],
            environment={"MY_VAR": "test_value"},
        )

        assert result.exit_code == 0
        assert result.stdout_text.strip() == "test_value"

    def test_streaming(self, runner):
        """Test streaming output."""
        chunks = list(
            runner.run_stream("alpine:latest", ["sh", "-c", "echo one; echo two; echo three"])
        )

        assert len(chunks) > 0
        combined = b"".join(chunk.data for chunk in chunks)
        assert b"one" in combined
        assert b"two" in combined
        assert b"three" in combined

    def test_with_callback(self, runner):
        """Test run_with_callback method."""
        received_chunks = []

        def callback(chunk):
            received_chunks.append(chunk)

        result = runner.run_with_callback(
            "alpine:latest",
            ["echo", "callback test"],
            on_output=callback,
        )

        assert result.exit_code == 0
        assert len(received_chunks) > 0
        assert b"callback test" in result.stdout

    def test_context_manager(self):
        """Test using DockerRunner as context manager."""
        with DockerRunner() as runner:
            result = runner.run("alpine:latest", ["echo", "context"])
            assert result.exit_code == 0


class TestContainerResult:
    """Tests for ContainerResult dataclass."""

    def test_stdout_text_decoding(self):
        """Test stdout_text property."""
        result = ContainerResult(exit_code=0, stdout=b"hello\n", stderr=b"")
        assert result.stdout_text == "hello\n"

    def test_stderr_text_decoding(self):
        """Test stderr_text property."""
        result = ContainerResult(exit_code=0, stdout=b"", stderr=b"error\n")
        assert result.stderr_text == "error\n"

    def test_success_property(self):
        """Test success property."""
        assert ContainerResult(exit_code=0).success is True
        assert ContainerResult(exit_code=1).success is False
        assert ContainerResult(exit_code=-1).success is False

