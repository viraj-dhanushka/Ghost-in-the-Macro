"""Power packaging checks (Requirements 12.1, 12.2, 12.10; review finding R-15)."""
import json
import tomllib
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SCHEMA = ROOT / "tests" / "fixtures" / "agent-plugins-plugin.schema.json"


def test_plugin_manifest_name_and_keywords():
    m = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "ghost-in-the-macro"
    for kw in ["excel", "xlsx", "xlsm", "vba", "macro", "spreadsheet", "workbook migration"]:
        assert kw in m["keywords"]
    assert "github.com" in m["repository"]


def test_plugin_manifest_validates_against_agent_plugins_schema():
    """The schema file is a copy of https://agent-plugins.org/schemas/1.0.0/plugin.schema.json."""
    manifest = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    assert (PLUGIN / "skills").is_dir()
    assert (PLUGIN / "mcp.json").is_file()


# R-15: this test used to assert `toolPrefix` starts with "ghost_" and that args were
# ["-m", "mcp_server.server"]. toolPrefix is not a documented Kiro field (Kiro namespaces
# Power servers itself) and `python` does not exist on a stock Mac, so the assertion now
# checks the documented fields and the launch command instead.
def test_mcp_json_uses_documented_fields_and_a_real_entry_point():
    cfg = json.loads((PLUGIN / "mcp.json").read_text(encoding="utf-8"))
    server = cfg["mcpServers"]["ghost"]
    assert "toolPrefix" not in server
    documented = {"command", "args", "env", "disabled", "autoApprove", "disabledTools", "url", "headers"}
    assert set(server) <= documented
    assert server["command"] == "uvx"
    assert server["command"] not in ("python",)
    assert server["args"][-1] == "ghost-mcp"
    assert any("github.com" in a for a in server["args"])
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    target = pyproject["project"]["scripts"]["ghost-mcp"]
    assert target == "mcp_server.server:main"
    assert (ROOT / "mcp_server" / "server.py").is_file()
