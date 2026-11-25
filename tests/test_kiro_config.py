"""Kiro configuration checks (spec kiro-surfaces, Requirement 7).

Task 3.1 covers one check: every MCP tool name mentioned in
``plugin/skills/*/SKILL.md`` and ``.kiro/agents/*.json`` is a key of
``mcp_server.server.TOOLS`` (Requirements 5.1, 7.1, 7.2). No LibreOffice, no network.

How a "tool name mention" is detected
-------------------------------------
A token is a *tool-like identifier* when it is lower-case snake_case with at least
one underscore (``^[a-z][a-z0-9]*(_[a-z0-9]+)+$``) AND its first word is one of the
first words of the real tool names (``analyze``, ``verify``, ``record``, ...,
derived from ``TOOLS`` at run time). The first-word rule is what keeps ordinary
snake_case such as ``rule_id``, ``migration_dir``, ``batch_size`` and
``finding_id`` (argument names, not tools) from counting, while a misspelt or
retired tool such as ``verify_impl`` or ``analyze_sheet`` is still caught. A tool
invented with a brand-new first word is not detected; that is the known blind
spot of this rule.

Where tokens are looked for:

* ``SKILL.md``: only inside Markdown backticks. A trailing call suffix such as
  ``record_decision(...)`` is stripped before matching. Plain prose is ignored.
* Agent JSON, ``tools`` / ``allowedTools`` / ``excludedTools`` lists: a selector
  ``@ghost/<tool>`` yields ``<tool>`` (any other server's selectors are ignored,
  as are built-ins such as ``read``, ``@ghost`` and ``*``). A bare entry yields
  itself when it is tool-like.
* Agent JSON, ``prompt`` and ``description`` strings: backticked spans, single or
  double quoted spans, and bare words, all subject to the tool-like rule above,
  plus ``@ghost/<tool>`` selectors.

Hyphenated names (``verify-migration``, ``record-decision``) are skill names, not
tools, and never match because the pattern allows underscores only. Command-line
flags, file names and paths never match for the same reason.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mcp_server.server import TOOLS

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = sorted((ROOT / "plugin" / "skills").glob("*/SKILL.md"))
AGENT_FILES = sorted((ROOT / ".kiro" / "agents").glob("*.json"))

TOOL_LIKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
# A bare word is not a tool mention when it is part of a file name or path: no word,
# '@', '/', '\', '.' or '-' before it; no word, '-', '/', '\' or '.<word>' (extension)
# after it. A sentence-final '.' (followed by space or end) still lets it match.
BARE_WORD = re.compile(
    r"(?<![\w@/\\.\-])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\w\-/\\])(?!\.\w)")
BACKTICKED = re.compile(r"`([^`\n]+)`")
QUOTED = re.compile(r"""(['"])([^'"\n]+)\1""")
SELECTOR = re.compile(r"@ghost/([A-Za-z0-9_\-]+)")
TOOL_LIST_FIELDS = ("tools", "allowedTools", "excludedTools")


def _tool_prefixes() -> set[str]:
    return {name.split("_", 1)[0] for name in TOOLS}


def _is_tool_like(token: str) -> bool:
    return bool(TOOL_LIKE.match(token)) and token.split("_", 1)[0] in _tool_prefixes()


def _strip_call(span: str) -> str:
    return re.sub(r"\(.*\)\s*$", "", span.strip())


def tools_in_markdown(text: str) -> set[str]:
    """Tool-like tokens inside backticks (call suffix stripped), plus ``@ghost/<tool>``."""
    found = {_strip_call(m) for m in BACKTICKED.findall(text)}
    found = {t for t in found if _is_tool_like(t)}
    return found | set(SELECTOR.findall(text))


def tools_in_agent(config: dict) -> set[str]:
    """Tool names mentioned by one parsed agent config (rule in the module docstring)."""
    found: set[str] = set()
    for field in TOOL_LIST_FIELDS:
        for entry in config.get(field, []) or []:
            if not isinstance(entry, str):
                continue
            m = SELECTOR.fullmatch(entry)
            if m:
                found.add(m.group(1))
            elif _is_tool_like(entry):
                found.add(entry)
    for field in ("prompt", "description"):
        text = config.get(field)
        if not isinstance(text, str):
            continue
        found |= tools_in_markdown(text)
        found |= {m[1] for m in QUOTED.findall(text) if _is_tool_like(m[1])}
        found |= {w for w in BARE_WORD.findall(text) if _is_tool_like(w)}
    return found


def mentioned_tools() -> dict[str, set[str]]:
    """Map 'relative/path' -> tool names it mentions, for every skill and agent file."""
    out: dict[str, set[str]] = {}
    for path in SKILL_FILES:
        out[str(path.relative_to(ROOT))] = tools_in_markdown(path.read_text(encoding="utf-8"))
    for path in AGENT_FILES:
        config = json.loads(path.read_text(encoding="utf-8"))
        out[str(path.relative_to(ROOT))] = tools_in_agent(config)
    return out


# --- the detection rule itself (inline fixtures) -------------------------------------

def test_markdown_detection_counts_backticked_tools_only():
    text = (
        "Call `verify_implementation` then `record_decision(migration_dir)`.\n"
        "Plain prose about mutation_check is ignored. Args: `rule_id`, `batch_size`.\n"
        "Skills: `verify-migration`. Path `.kiro/specs/<migration>/decisions.yaml`."
    )
    assert tools_in_markdown(text) == {"verify_implementation", "record_decision"}


def test_markdown_detection_catches_a_misspelt_tool():
    assert tools_in_markdown("Use `verify_impl`.") == {"verify_impl"}
    assert "verify_impl" not in TOOLS


def test_agent_detection_reads_selectors_lists_and_prompt():
    config = {
        "tools": ["read", "@ghost/analyze_workbook", "@other/fetch_url", "@ghost", "*"],
        "excludedTools": ["mutation_check"],
        "description": "Uses 'verify_implementation'.",
        "prompt": "Call record_decision, not rule_id or ghost verify. See `get_dependencies`.",
    }
    assert tools_in_agent(config) == {
        "analyze_workbook", "mutation_check", "verify_implementation",
        "record_decision", "get_dependencies",
    }


def test_agent_detection_ignores_ordinary_words():
    config = {"prompt": "Write rule_id values into traceability.yaml; use the exit_code and "
                        "not_converted lists. Run 'ghost autopsy'."}
    assert tools_in_agent(config) == set()


# --- Requirement 7.2: every mentioned tool is a key of TOOLS -------------------------

def test_discovers_skill_and_agent_files():
    assert SKILL_FILES, "no plugin/skills/*/SKILL.md found"
    assert AGENT_FILES, "no .kiro/agents/*.json found"


def test_skills_mention_at_least_one_tool():
    """Guards against a detection rule that silently matches nothing."""
    mentions = mentioned_tools()
    skill_mentions = set().union(*(v for k, v in mentions.items() if k.endswith("SKILL.md")))
    assert skill_mentions


@pytest.mark.parametrize("rel", sorted(mentioned_tools()))
def test_every_mentioned_tool_name_is_a_declared_mcp_tool(rel: str):
    unknown = sorted(mentioned_tools()[rel] - set(TOOLS))
    assert not unknown, f"{rel} mentions tool names not in mcp_server.server.TOOLS: {unknown}"


# --- Property 3 (Hypothesis, no LibreOffice) -----------------------------------------
# Feature: kiro-surfaces, Property 3: Every mentioned tool name is a declared MCP tool
# Validates: Requirements 5.1, 7.2
# Strategies: st.sampled_from over TOOLS (real names), real first word + generated wrong
# suffix (near-misses), argument names and hyphenated skill names (never tool-like), and
# filler text. Explicit seed via derandomize plus @seed.
from hypothesis import HealthCheck, assume, given, seed, settings, strategies as st

_PREFIXES = sorted({n.split("_", 1)[0] for n in TOOLS})
_ARG_NAMES = ["rule_id", "migration_dir", "batch_size", "finding_id", "exit_code",
              "not_converted", "source_path", "max_examples"]
_SKILL_NAMES = ["verify-migration", "record-decision", "analyze-workbook", "generate-proof-report"]
_NOISE = ["Run", "then", "the", "result", "see", "`ghost autopsy`", "`.kiro/specs/x/rules.md`",
          "`--trust-macros`", "plain_prose_word", "mutation_check_notes.md", "42"]


@st.composite
def _near_miss(draw) -> str:
    token = draw(st.sampled_from(_PREFIXES)) + "_" + draw(
        st.from_regex(r"[a-z][a-z0-9]{0,8}(_[a-z0-9]{1,6}){0,2}", fullmatch=True))
    return token


_near_miss_unknown = _near_miss().filter(lambda t: t not in TOOLS)

_piece = st.one_of(
    st.tuples(st.just("real"), st.sampled_from(sorted(TOOLS))),
    st.tuples(st.just("near"), _near_miss_unknown),
    st.tuples(st.just("arg"), st.sampled_from(_ARG_NAMES)),
    st.tuples(st.just("skill"), st.sampled_from(_SKILL_NAMES)),
    st.tuples(st.just("noise"), st.sampled_from(_NOISE)),
)


def _render(kind: str, value: str, call: bool) -> str:
    if kind in ("real", "near"):
        return f"`{value}(x)`" if call else f"`{value}`"
    if kind in ("arg", "skill"):
        return f"`{value}`"
    return value


@seed(20261204)
@settings(max_examples=200, deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow])
@given(pieces=st.lists(_piece, min_size=0, max_size=12),
       calls=st.lists(st.booleans(), min_size=12, max_size=12))
def test_property_3_detector_reports_exactly_the_embedded_tool_like_tokens(pieces, calls):
    text = " ; ".join(_render(k, v, c) for (k, v), c in zip(pieces, calls))
    expected = {v for k, v in pieces if k in ("real", "near")}
    assert tools_in_markdown(text) == expected
    # Same tokens inside an agent prompt are found too (backticked form).
    assert tools_in_agent({"prompt": text}) == expected
    # Unknown (near-miss) tokens are exactly the ones a coverage check would flag.
    assert tools_in_markdown(text) - set(TOOLS) == {v for k, v in pieces if k == "near"}


@seed(20261204)
@settings(max_examples=100, deadline=None, derandomize=True)
@given(data=st.data())
def test_property_3_every_real_file_mention_is_a_declared_tool(data):
    mentions = mentioned_tools()
    pairs = [(rel, tool) for rel, tools in sorted(mentions.items()) for tool in sorted(tools)]
    assert pairs, "no tool mentions extracted from any skill or agent file"
    rel, tool = data.draw(st.sampled_from(pairs))
    assert tool in TOOLS, f"{rel} mentions {tool!r}, not a key of mcp_server.server.TOOLS"


# --- Requirements 6.1, 7.3, 7.4: hook files parse, follow v1, matchers accept/reject ---
# Task 3.3 (example assertions only; the Hypothesis properties are task 3.4).
# Matching uses re.search against the path. Kiro may pass an absolute or a
# workspace-relative path, so each intended path is tested in both forms.
HOOK_FILES = sorted((ROOT / ".kiro" / "hooks").glob("*.json"))
ABS_PREFIX = "/work/some/project/"  # synthetic absolute workspace root, not a real path

# Trigger names listed in docs/KIRO_SURFACES_FORMATS.md section 2 (hooks, hooks/types pages).
DOCUMENTED_TRIGGERS = {
    "SessionStart", "Stop", "UserPromptSubmit", "PreTaskExec", "PostTaskExec",
    "PreToolUse", "PostToolUse", "PostFileCreate", "PostFileSave", "PostFileDelete",
    "SubagentStop", "SessionEnd", "PreCompact", "PostCompact", "PermissionRequest",
}
DOCUMENTED_ACTION_TYPES = {"command", "agent"}

HOOK_CASES = {
    "autopsy-on-graveyard-add.json": {
        "trigger": "PostFileCreate",
        "accept": ["graveyard/x.xlsx", "graveyard/x.xlsm", "graveyard/my book v2.xlsx"],
        "reject": ["graveyard/sub/x.xlsx", "graveyard/x.csv", "graveyard/x.xlsx.bak",
                   "graveyard/.xlsx", "mygraveyard/x.xlsx", "samples/x.xlsx"],
    },
    "golden-tests-on-converter-save.json": {
        "trigger": "PostFileSave",
        "accept": ["ghost/converter/emit_python.py", "ghost/converter/parser.py"],
        "reject": ["ghost/converter/notes.md", "ghost/converter/emit_python.pyc",
                   "ghost/runtime/excel.py", "ghost/converter", "xghost/converter/a.py",
                   "tests/test_converter.py"],
    },
    "regenerate-report-on-decision.json": {
        "trigger": "PostFileSave",
        "accept": [".kiro/specs/m/decisions.yaml", ".kiro/specs/haunted-discount/decisions.yaml"],
        "reject": [".kiro/specs/decisions.yaml", ".kiro/specs/m/sub/decisions.yaml",
                   ".kiro/specs/m/decisions.yml", ".kiro/specs/m/decisions.yaml.bak",
                   ".kiro/specs/m/rules.md", "kiro/specs/m/decisions.yaml"],
    },
    "reverify-on-logic-save.json": {
        "trigger": "PostFileSave",
        "accept": [".kiro/specs/m/logic.py", ".kiro/specs/m/mapping.yaml"],
        "reject": [".kiro/specs/m/logic.pyc", ".kiro/specs/m/mapping.yml",
                   ".kiro/specs/m/rules.md", ".kiro/specs/m/sub/logic.py",
                   ".kiro/specs/logic.py", ".kiro/specs/m/decisions.yaml"],
    },
    "review-findings-on-create.json": {
        "trigger": "PostFileCreate",
        "action": "agent",
        "accept": [".kiro/specs/m/findings.yaml", ".kiro/specs/haunted-discount/findings.yaml"],
        "reject": [".kiro/specs/findings.yaml", ".kiro/specs/m/sub/findings.yaml",
                   ".kiro/specs/m/findings.yml", ".kiro/specs/m/findings.yaml.bak",
                   ".kiro/specs/m/rules.md", "x.kiro/specs/m/findings.yaml"],
    },
}


def _load_hook(name: str) -> dict:
    return json.loads((ROOT / ".kiro" / "hooks" / name).read_text(encoding="utf-8"))


def _hook_matcher(name: str) -> "re.Pattern[str]":
    (hook,) = _load_hook(name)["hooks"]
    return re.compile(hook["matcher"])


def test_hook_case_table_covers_every_hook_file():
    assert {p.name for p in HOOK_FILES} == set(HOOK_CASES)


@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda p: p.name)
def test_hook_file_parses_and_follows_documented_v1_shape(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "v1"
    assert isinstance(data["hooks"], list) and data["hooks"]
    for hook in data["hooks"]:
        assert isinstance(hook["name"], str) and hook["name"]
        assert hook["trigger"] in DOCUMENTED_TRIGGERS
        action = hook["action"]
        assert action["type"] in DOCUMENTED_ACTION_TYPES
        if action["type"] == "command":
            assert isinstance(action.get("command"), str) and action["command"]
        else:
            assert isinstance(action.get("prompt"), str) and action["prompt"]
        if "matcher" in hook:
            re.compile(hook["matcher"])  # must be a valid regex
        if "timeout" in hook:
            assert isinstance(hook["timeout"], (int, float)) and hook["timeout"] >= 0


@pytest.mark.parametrize("name", sorted(HOOK_CASES))
def test_hook_uses_the_intended_trigger_and_ghost_hook_script(name: str):
    (hook,) = _load_hook(name)["hooks"]
    assert hook["trigger"] == HOOK_CASES[name]["trigger"]
    kind = HOOK_CASES[name].get("action", "command")
    assert hook["action"]["type"] == kind
    if kind == "command":
        assert "scripts/ghost_hook.py" in hook["action"]["command"]  # Requirement 6.2
    else:  # the one agent hook: no trigger that interferes with tasks, prompts or sessions
        assert hook["trigger"] in {"PostFileCreate", "PostFileSave", "PostFileDelete"}
        assert "matcher" in hook


def _accept_params():
    return [(n, p) for n, c in sorted(HOOK_CASES.items()) for p in c["accept"]]


def _reject_params():
    return [(n, p) for n, c in sorted(HOOK_CASES.items()) for p in c["reject"]]


@pytest.mark.parametrize("name,rel", _accept_params())
def test_hook_matcher_accepts_intended_path_relative_and_absolute(name: str, rel: str):
    matcher = _hook_matcher(name)
    assert matcher.search(rel), f"{name}: relative {rel!r} not matched"
    assert matcher.search(ABS_PREFIX + rel), f"{name}: absolute {rel!r} not matched"


@pytest.mark.parametrize("name,rel", _reject_params())
def test_hook_matcher_rejects_near_miss_path_relative_and_absolute(name: str, rel: str):
    matcher = _hook_matcher(name)
    assert not matcher.search(rel), f"{name}: relative near miss {rel!r} matched"
    assert not matcher.search(ABS_PREFIX + rel), f"{name}: absolute near miss {rel!r} matched"


@pytest.mark.parametrize("name", sorted(HOOK_CASES))
def test_each_hook_has_at_least_three_near_misses(name: str):
    assert len(HOOK_CASES[name]["reject"]) >= 3


# --- Properties 1 and 2 (Hypothesis, no LibreOffice): hook matcher accept / reject -----
# Task 3.4. Parameterised over the five hook files (task 8 added review-findings-on-create).
#
# Path conventions (docs/KIRO_SURFACES_FORMATS.md does not say paths use backslashes, so
# Windows-style `\` separators are OUT OF SCOPE and never generated). Paths are
# workspace-relative or absolute, always with `/`. Matching is case-sensitive, as the
# regexes are, so case variants (`Graveyard`, `.XLSX`) are treated as near misses.
# Generated names avoid control characters (a trailing newline would slip past `$`;
# real file names do not contain one) and contain dots, spaces, hyphens and unicode.
#
# The oracle `_is_intended` splits on "/" and compares segments and suffixes. It never
# uses the matcher regex, so a regex bug cannot hide behind a copy of itself.
_NAME_CHAR = st.one_of(
    st.characters(whitelist_categories=("L", "N"), blacklist_characters="/\\"),
    st.sampled_from(list(" .-_()+,")),
)
_NAME = st.text(alphabet=_NAME_CHAR, min_size=1, max_size=12)
_PREFIX = st.one_of(
    st.just(""),
    st.lists(_NAME, min_size=0, max_size=3).map(lambda s: "/" + "".join(x + "/" for x in s)),
    st.lists(_NAME, min_size=1, max_size=3).map(lambda s: "".join(x + "/" for x in s)),
)

_KIRO_NAMES = {
    "regenerate-report-on-decision.json": ["decisions.yaml"],
    "reverify-on-logic-save.json": ["logic.py", "mapping.yaml"],
    "review-findings-on-create.json": ["findings.yaml"],
}


def _is_intended(name: str, path: str) -> bool:
    """Independent oracle: does `path` have the hook's intended shape?"""
    parts = path.split("/")
    last = parts[-1]
    if name == "autopsy-on-graveyard-add.json":
        return (len(parts) >= 2 and parts[-2] == "graveyard"
                and last.endswith((".xlsx", ".xlsm")) and len(last) > 5)
    if name == "golden-tests-on-converter-save.json":
        return (last.endswith(".py") and len(last) > 3
                and any(parts[i:i + 2] == ["ghost", "converter"] and i + 2 < len(parts)
                        for i in range(len(parts) - 2)))
    return (len(parts) >= 4 and parts[-4] == ".kiro" and parts[-3] == "specs"
            and parts[-2] != "" and last in _KIRO_NAMES[name])


@st.composite
def _intended_path(draw):
    name = draw(st.sampled_from(sorted(HOOK_CASES)))
    prefix, stem, mig = draw(_PREFIX), draw(_NAME), draw(_NAME)
    if name == "autopsy-on-graveyard-add.json":
        path = prefix + "graveyard/" + stem + draw(st.sampled_from([".xlsx", ".xlsm"]))
    elif name == "golden-tests-on-converter-save.json":
        sub = "".join(x + "/" for x in draw(st.lists(_NAME, max_size=2)))
        path = prefix + "ghost/converter/" + sub + stem + ".py"
    else:
        path = prefix + ".kiro/specs/" + mig + "/" + draw(st.sampled_from(_KIRO_NAMES[name]))
    return name, path


_GY_EXT = [".csv", ".xls", ".xlsb", ".xlsx.bak", ".xlsm.bak", ".xlsx~", ".xlsxx", ".XLSX",
           ".xlsm.pyc", ".xlsx.xlsx.bak"]
_GY_DIR = ["graveyards", "Graveyard", "graveyard_old", "mygraveyard", "samples", "xgraveyard"]
_CV_EXT = [".md", ".pyc", ".py.bak", ".PY", ".pyi", ".pyw", ".py~"]
_CV_DIR = ["ghost/convertor", "ghost/converters", "xghost/converter", "ghost/runtime",
           "converter", "ghost/Converter", "ghost/converter_old", "ghost-converter"]
_KIRO_DIR = ["kiro/specs", ".kiro/spec", ".kiro/Specs", "x.kiro/specs", ".kiro/specs2",
             ".Kiro/specs", ".kiro/steering"]
_KIRO_FILES = {
    "regenerate-report-on-decision.json": [
        "decisions.yml", "decisions.yaml.bak", "decisions.yaml~", "Decisions.yaml",
        "xdecisions.yaml", "decisions.YAML", "rules.md"],
    "reverify-on-logic-save.json": [
        "logic.pyc", "logic.py.bak", "mapping.yml", "mapping.yaml.bak", "Logic.py",
        "xlogic.py", "logic.pyi", "rules.md", "decisions.yaml"],
    "review-findings-on-create.json": [
        "findings.yml", "findings.yaml.bak", "findings.yaml~", "Findings.yaml",
        "xfindings.yaml", "findings.YAML", "rules.md"],
}


_NEAR_MISS_KINDS = {
    "autopsy-on-graveyard-add.json": ["subfolder", "ext", "dir", "nodir"],
    "golden-tests-on-converter-save.json": ["ext", "dir", "nofile"],
    "regenerate-report-on-decision.json": ["subfolder", "nomig", "file", "dir"],
    "reverify-on-logic-save.json": ["subfolder", "nomig", "file", "dir"],
    "review-findings-on-create.json": ["subfolder", "nomig", "file", "dir"],
}
_NEAR_MISS_PARAMS = [(n, k) for n, ks in sorted(_NEAR_MISS_KINDS.items()) for k in ks]


@st.composite
def _near_miss_path(draw, name: str, kind: str):
    prefix, stem, mig, seg = draw(_PREFIX), draw(_NAME), draw(_NAME), draw(_NAME)
    if name == "autopsy-on-graveyard-add.json":
        good = stem + ".xlsx"
        path = {
            "subfolder": prefix + "graveyard/" + seg + "/" + good,
            "ext": prefix + "graveyard/" + stem + draw(st.sampled_from(_GY_EXT)),
            "dir": prefix + draw(st.sampled_from(_GY_DIR)) + "/" + good,
            "nodir": prefix + good,
        }[kind]
    elif name == "golden-tests-on-converter-save.json":
        path = {
            "ext": prefix + "ghost/converter/" + stem + draw(st.sampled_from(_CV_EXT)),
            "dir": prefix + draw(st.sampled_from(_CV_DIR)) + "/" + stem + ".py",
            "nofile": prefix + draw(st.sampled_from(["ghost/converter", "ghost/converter.py"])),
        }[kind]
    else:
        good = _KIRO_NAMES[name][0]
        path = {
            "subfolder": prefix + ".kiro/specs/" + mig + "/" + seg + "/" + good,
            "nomig": prefix + ".kiro/specs/" + good,
            "file": prefix + ".kiro/specs/" + mig + "/" + draw(st.sampled_from(_KIRO_FILES[name])),
            "dir": prefix + draw(st.sampled_from(_KIRO_DIR)) + "/" + mig + "/" + good,
        }[kind]
    return path


# Feature: kiro-surfaces, Property 1: Hook matcher accepts every path matching its intended shape
# Validates: Requirements 6.1, 6.3, 7.3
@seed(20261204)
@settings(max_examples=300, deadline=None, derandomize=True)
@given(case=_intended_path())
def test_property_1_hook_matcher_accepts_every_path_matching_its_intended_shape(case):
    name, path = case
    assert _is_intended(name, path), f"generator bug: {path!r} is not the intended shape"
    assert _hook_matcher(name).search(path), f"{name} rejected intended path {path!r}"


# Feature: kiro-surfaces, Property 2: Hook matcher rejects every generated near-miss path
# Validates: Requirements 6.1, 6.7, 7.4
# One test per (hook, near-miss kind) so every kind gets its own 200 examples and a
# failure names the kind.
@pytest.mark.parametrize("name,kind", _NEAR_MISS_PARAMS)
def test_property_2_hook_matcher_rejects_every_generated_near_miss_path(name: str, kind: str):
    @seed(20261204)
    @settings(max_examples=200, deadline=None, derandomize=True)
    @given(path=_near_miss_path(name, kind))
    def check(path):
        assume(not _is_intended(name, path))  # a random prefix may, rarely, complete the shape
        assert not _hook_matcher(name).search(path), f"{name} [{kind}] accepted near miss {path!r}"

    check()


# --- Task 3.5: steering copies, POWER.md, agent tool limits, workspace MCP -------------
# Requirements 3.3-3.5, 4.2, 4.3, 4.5, 5.1-5.9, 7.5-7.8. Field names come from
# docs/KIRO_SURFACES_FORMATS.md: agents use `name`, `description`, `prompt`, `tools`
# (selectors `@ghost/<tool>`), `resources` (`file://` URIs), `includeMcpJson` /
# `mcpServers`. The doc says "not documented" for: POWER.md front-matter field names,
# `plugin/steering/` as a Power location, and `cwd` for MCP entries. Those are asserted
# only as far as the requirements demand (POWER.md `name`/`keywords` equal plugin.json's;
# the steering copies are byte-identical if present; mcp.json must not use `cwd`).
#
# Each failing test carries xfail(strict=True) naming the task that fixes it. When the
# config lands, strict mode turns the XPASS into a failure, forcing the marker's removal.
# Task 4: the Owner decided plugin/steering/ and POWER.md are not used; see STEERING_COPY_DIR.
STEERING_NAMES = ["ghost-guardrails.md", "excel-semantics.md"]
PLUGIN_DIR = ROOT / "plugin"
MCP_JSON = ROOT / ".kiro" / "settings" / "mcp.json"

COMMON_AGENT_TOOLS = {
    "coroner": {"analyze_workbook", "find_inconsistencies", "extract_vba",
                "boundary_cases", "get_dependencies", "check_against_excel_cache"},
    "skeptic": {"verify_implementation", "mutation_check", "evaluate_original"},
    "clerk": {"record_decision", "generate_proof_report"},
}
VERIFICATION_TOOLS = {"verify_implementation", "mutation_check", "evaluate_original"}
CLI_SUBCOMMANDS = ("autopsy", "verify", "report", "mutation", "mutate", "route", "convert",
                   "decide", "decision", "rules", "referee", "sanity", "migrate", "evaluate")
CLI_CALL = re.compile(r"\bghost\s+(?:" + "|".join(CLI_SUBCOMMANDS) + r")\b"
                      r"|\bghost-py\b|\bpython\d?\s+-m\s+ghost\b")


def _agent(name: str) -> dict:
    path = ROOT / ".kiro" / "agents" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _selectors(config: dict) -> set[str]:
    return {e for e in (config.get("tools") or []) if isinstance(e, str)}


def _allowed_ghost_tools(config: dict) -> set[str]:
    """Ghost tools the agent can call: named by `@ghost/<tool>`, or all via a wildcard,
    minus `excludedTools`."""
    sel = _selectors(config)
    allowed = set(TOOLS) if sel & {"*", "@mcp", "@ghost"} else set()
    allowed |= {s.split("/", 1)[1] for s in sel if s.startswith("@ghost/")}
    excluded = {e.split("/", 1)[-1] for e in (config.get("excludedTools") or [])
                if isinstance(e, str)}
    return allowed - excluded


# Owner decision (task 4): the copies live in the guardrails skill's references/ folder,
# the documented skill layout, not in an undocumented plugin/steering/ folder.
STEERING_COPY_DIR = PLUGIN_DIR / "skills" / "guardrails" / "references"


@pytest.mark.parametrize("name", STEERING_NAMES)
def test_steering_copy_is_byte_identical_to_original(name: str):
    original = ROOT / ".kiro" / "steering" / name
    copy = STEERING_COPY_DIR / name
    assert original.is_file(), f"steering original missing: {original}"
    assert copy.is_file(), f"steering copy missing: {copy}"
    assert copy.read_bytes() == original.read_bytes()


def _power_md_fields(text: str) -> dict:
    import yaml
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    assert m, "plugin/POWER.md has no YAML front matter"
    return yaml.safe_load(m.group(1)) or {}


def test_power_md_name_and_keywords_equal_plugin_json():
    power_md = PLUGIN_DIR / "POWER.md"
    if not power_md.exists():
        pytest.skip("plugin/POWER.md absent (legacy, optional per docs/KIRO_SURFACES_FORMATS.md)")
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    fields = _power_md_fields(power_md.read_text(encoding="utf-8"))
    assert fields.get("name") == manifest["name"]
    assert fields.get("keywords") == manifest["keywords"]


AGENT_NAMES = ["coroner", "skeptic", "clerk", "medium"]


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agent_files_use_only_documented_field_names(name: str):
    documented = {"name", "description", "prompt", "mcpServers", "tools", "permissions",
                  "resources", "hooks", "includeMcpJson", "includePowers", "excludedTools",
                  "model", "welcomeMessage"}
    config = _agent(name)
    assert set(config) <= documented, f"undocumented fields: {sorted(set(config) - documented)}"
    for field in ("name", "description", "prompt"):
        assert isinstance(config.get(field), str) and config[field]


def test_coroner_is_limited_to_its_six_ghost_tools_with_no_write_or_shell():
    config = _agent("coroner")
    sel = _selectors(config)
    assert sel == {f"@ghost/{t}" for t in COMMON_AGENT_TOOLS["coroner"]}
    assert not sel & {"write", "shell", "*", "@builtin", "@mcp", "@ghost"}


def test_skeptic_is_limited_to_three_verification_tools_plus_read():
    # Owner decision (front-door task 17 follow-up): the Skeptic could not review wording because it
    # had no way to read a file. It gets the built-in `read` and still no `write`, `shell` or wildcard.
    sel = _selectors(_agent("skeptic"))
    assert sel == {"read"} | {f"@ghost/{t}" for t in COMMON_AGENT_TOOLS["skeptic"]}
    assert not sel & {"write", "shell", "*", "@builtin", "@mcp", "@ghost"}


def test_clerk_is_limited_to_record_decision_and_generate_proof_report():
    assert _selectors(_agent("clerk")) == {f"@ghost/{t}" for t in COMMON_AGENT_TOOLS["clerk"]}


def test_clerk_prompt_says_record_only_decisions_a_human_dictated():
    prompt = _agent("clerk")["prompt"].lower()
    assert "human" in prompt and ("dictat" in prompt)


def test_medium_has_ghost_tools_but_none_of_the_verification_tools():
    config = _agent("medium")
    assert any(s.startswith("@ghost/") for s in _selectors(config)), "no @ghost/<tool> selector"
    assert not _allowed_ghost_tools(config) & VERIFICATION_TOOLS


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agent_references_both_steering_files_as_file_resources(name: str):
    resources = _agent(name).get("resources") or []
    uris = [r for r in resources if isinstance(r, str) and r.startswith("file://")]
    for steering in STEERING_NAMES:
        assert any(u.endswith("steering/" + steering) for u in uris), \
            f"{name}: no file:// resource for steering/{steering}"


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agent_references_the_ghost_mcp_server(name: str):
    config = _agent(name)
    assert config.get("includeMcpJson") is True or "ghost" in (config.get("mcpServers") or {})


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agent_prompt_names_mcp_tools_and_not_the_cli(name: str):
    prompt = _agent(name)["prompt"]
    assert not CLI_CALL.search(prompt), f"{name} prompt instructs the Ghost CLI"
    wanted = COMMON_AGENT_TOOLS.get(name, set(TOOLS))
    assert set(re.findall(r"[a-z]+(?:_[a-z]+)+", prompt)) & wanted, \
        f"{name} prompt names none of its MCP tools"


def _load_mcp_json() -> dict:
    assert MCP_JSON.is_file(), f"missing {MCP_JSON.relative_to(ROOT)}"
    return json.loads(MCP_JSON.read_text(encoding="utf-8"))


def test_workspace_mcp_registers_local_ghost_server_without_cwd_or_github():
    text = MCP_JSON.read_text(encoding="utf-8") if MCP_JSON.is_file() else ""
    data = _load_mcp_json()
    servers = data["mcpServers"]
    assert list(servers) == ["ghost"]
    entry = servers["ghost"]
    assert isinstance(entry["command"], str) and entry["command"]
    args = entry.get("args", [])
    assert isinstance(args, list) and all(isinstance(a, str) for a in args)
    launch = " ".join([entry["command"], *args])
    assert "mcp_server.server" in launch or "ghost-mcp" in launch, launch
    assert "cwd" not in entry, "docs/KIRO_SURFACES_FORMATS.md: cwd is not documented"
    assert "github" not in text.lower() and "git+" not in text
    assert "url" not in entry, "must be a local command server, not a remote URL"


def test_getting_started_skill_exists_and_is_covered_by_the_tool_name_check():
    path = PLUGIN_DIR / "skills" / "getting-started" / "SKILL.md"
    assert path.is_file()
    assert path in SKILL_FILES
    text = path.read_text(encoding="utf-8")
    assert re.match(r"\A---\nname: getting-started\ndescription: .+\n---\n", text)
    named = tools_in_markdown(text)
    assert named and named <= set(TOOLS)
    assert named == set(TOOLS), f"getting-started should list all tools; missing {sorted(set(TOOLS) - named)}"


# --- Task 10 (Skeptic review): SKILL.md prose mentions -------------------------------
# tools_in_markdown() reads backticked spans only. This test also reads bare words, so a
# retired or misspelt tool name written as plain prose in a SKILL.md cannot slip through.
@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_prose_has_no_unknown_tool_like_words(path: Path):
    text = path.read_text(encoding="utf-8")
    words = {w for w in BARE_WORD.findall(text) if _is_tool_like(w)}
    assert words <= set(TOOLS), f"{path.parent.name}: unknown tool-like words {sorted(words - set(TOOLS))}"
