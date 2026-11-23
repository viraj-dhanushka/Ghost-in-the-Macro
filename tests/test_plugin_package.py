"""Power packaging checks (Requirements 12.1, 12.2, 12.10)."""
import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"


def test_plugin_manifest_name_and_keywords():
    m = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "ghost-in-the-macro"
    for kw in ["excel", "xlsx", "xlsm", "vba", "macro", "spreadsheet", "workbook migration"]:
        assert kw in m["keywords"]
    assert "github.com" in m["repository"]


def test_mcp_json_uses_ghost_prefix_and_real_module():
    cfg = json.loads((PLUGIN / "mcp.json").read_text(encoding="utf-8"))
    server = cfg["mcpServers"]["ghost"]
    assert server["toolPrefix"].startswith("ghost_")
    assert server["args"] == ["-m", "mcp_server.server"]
    assert (PLUGIN.parent / "mcp_server" / "server.py").is_file()
