import importlib

import pytest

PACKAGES = [
    "ghost",
    "ghost.ingest",
    "ghost.autopsy",
    "ghost.rules",
    "ghost.referee",
    "ghost.converter",
    "ghost.runtime",
    "ghost.verifier",
    "ghost.mutation",
    "ghost.report",
    "ghost.decisions",
    "ghost.router",
    "mcp_server",
    "web",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name):
    importlib.import_module(name)


def test_version_is_set():
    import ghost

    assert ghost.__version__
