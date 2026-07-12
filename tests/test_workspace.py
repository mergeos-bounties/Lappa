import pytest
from lappa.server.api.workspace import WorkspaceManager

def test_register_valid_path():
    manager = WorkspaceManager("/tmp/workspace")
    result = manager.register_external_path("/tmp/workspace/external")
    assert result["status"] == "success"

def test_register_path_escape():
    manager = WorkspaceManager("/tmp/workspace")
    with pytest.raises(ValueError, match="Path escape blocked"):
        manager.register_external_path("/etc/passwd")
