"""Custom exceptions for dockerrun."""


class DockerRunError(Exception):
    """Base exception for dockerrun errors."""

    pass


class ContainerError(DockerRunError):
    """Error running container."""

    def __init__(self, message: str, exit_code: int | None = None):
        super().__init__(message)
        self.exit_code = exit_code


class ImageNotFoundError(DockerRunError):
    """Docker image not found."""

    pass

