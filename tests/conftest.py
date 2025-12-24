"""Pytest configuration and fixtures."""

import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests (including long-running PyTorch build tests)",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "slow: slow-running tests")


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests unless --run-e2e flag is provided."""
    if config.getoption("--run-e2e"):
        # --run-e2e given: remove skip markers from e2e tests
        for item in items:
            # Remove any skip markers that mention e2e
            item.own_markers = [
                marker for marker in item.own_markers
                if not (marker.name == "skip" and "e2e" in str(marker.kwargs.get("reason", "")).lower())
            ]
        return
    
    # --run-e2e not given: skip is already applied via decorator
    # No additional action needed since we use @pytest.mark.skip decorator

