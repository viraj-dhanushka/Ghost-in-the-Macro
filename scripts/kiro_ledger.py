#!/usr/bin/env python3
"""Kiro ledger: count, from the working tree, how Kiro was used on this project (read-only).

Writes four files, byte-identical for the same working tree (no timestamps, sorted everywhere):
  docs/KIRO_STORY.md            one section per topic the hackathon rules ask about; every number is followed by the
                                path it was counted from
  docs/KIRO_PROPERTY_LEDGER.md  one row per (spec, property number): the test file that covers it, or "not covered"
  web/kiro_facts.json           the small file the /kiro page renders (the container has no .kiro/ or docs/)
  README.md                     only the table between the kiro-table markers; the rest of the README is never touched

Usage:  scripts/ghost-py scripts/kiro_ledger.py            write the three files
        scripts/ghost-py scripts/kiro_ledger.py --check    exit 1 when a committed file is stale (writes nothing)

Honesty rules: it counts and quotes; it does not judge. A topic with no evidence says so. Anything only the Owner can
know is a marked placeholder `[OWNER: ...]`. A "caught" cell names a bug only where docs/KIRO_USAGE.md says a property
caught it; otherwise it says "none recorded".
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = "docs/KIRO_USAGE.md"
OUT_STORY = "docs/KIRO_STORY.md"
OUT_LEDGER = "docs/KIRO_PROPERTY_LEDGER.md"
OUT_FACTS = "web/kiro_facts.json"
OUT_README = "README.md"
TABLE_BEGIN = "<!-- kiro-table:begin -->"
TABLE_END = "<!-- kiro-table:end -->"

SPEC_TOKENS = {
    "ghost-in-the-macro": ["main spec", "ghost-in-the-macro"],
    "front-door": ["front-door", "front_door"],
    "kiro-surfaces": ["kiro-surfaces", "kiro_surfaces"],
    "live-fixes-2026-11-24": ["live-fixes"],
    "review-fixes-2026-11-24": ["review-fixes"],
    "readable-proof": ["readable-proof", "readable_proof"],
    "trial-by-workbook": ["trial-by-workbook"],
    "vba-on-screen": ["vba-on-screen"],
    "large-workbook-lane": ["large-workbook-lane"],
}


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


# --------------------------------------------------------------------------------------------- specs
def design_properties(design: str) -> list[tuple[int, str]]:
    """Properties of a design.md: `### Property N: title` or `Property N: title` lines, else the numbered list under
    a "Correctness properties" heading. Each spec numbers its own from 1."""
    found = [(int(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(?:#{2,4} )?Property (\d+): (.+)$", design, re.M)]
    if found:
        return found
    m = re.search(r"^## Correctness properties\s*\n(.*?)(?=^## |\Z)", design, re.M | re.S | re.I)
    if not m:
        return []
    return [(int(n), t.strip()) for n, t in re.findall(r"^(\d+)\. (.+)$", m.group(1), re.M)]


def specs() -> list[dict]:
    out = []
    for d in sorted((ROOT / ".kiro" / "specs").iterdir()):
        if not d.is_dir():
            continue
        cfg = {}
        if (d / ".config.kiro").is_file():
            try:
                cfg = json.loads((d / ".config.kiro").read_text(encoding="utf-8"))
            except ValueError:
                cfg = {}
        tasks = read(rel(d / "tasks.md"))
        design = read(rel(d / "design.md"))
        reqs = read(rel(d / "requirements.md")) or read(rel(d / "bugfix.md"))
        props = design_properties(design)
        out.append({
            "name": d.name,
            "path": rel(d),
            "type": cfg.get("specType") or "not a Kiro spec folder (no .config.kiro)",
            "workflow": cfg.get("workflowType") or "n/a",
            "has_requirements": (d / "requirements.md").is_file(),
            "has_bugfix": (d / "bugfix.md").is_file(),
            "has_design": (d / "design.md").is_file(),
            "has_tasks": (d / "tasks.md").is_file(),
            "requirements": len(re.findall(r"^#{2,4} Requirement \d+", reqs, re.M)),
            "properties": props,
            "tasks_done": len(re.findall(r"^\s*- \[x\]", tasks, re.M)),
            "tasks_open": len(re.findall(r"^\s*- \[ \]", tasks, re.M)),
            "tasks_optional_open": len(re.findall(r"^\s*- \[ \]\*", tasks, re.M)),
        })
    return out


# --------------------------------------------------------------------------------------------- the rest
def steering() -> list[dict]:
    out = []
    for p in sorted((ROOT / ".kiro" / "steering").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        fm = m.group(1) if m else ""
        inc = re.search(r"^inclusion:\s*(\S+)", fm, re.M)
        out.append({"file": rel(p), "inclusion": inc.group(1) if inc else "not stated"})
    return out


def hooks() -> list[dict]:
    out = []
    for p in sorted((ROOT / ".kiro" / "hooks").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for h in data.get("hooks", []):
            out.append({"file": rel(p), "name": h.get("name", ""), "trigger": h.get("trigger", ""),
                        "action": (h.get("action") or {}).get("type", "")})
    return out


def agents() -> list[dict]:
    out = []
    for p in sorted((ROOT / ".kiro" / "agents").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        out.append({"file": rel(p), "name": data.get("name", p.stem), "description": data.get("description", ""),
                    "tools": data.get("tools", [])})
    return out


def mcp_tools() -> list[str]:
    tree = ast.parse(read("mcp_server/server.py"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TOOLS":
            target = node.value
        elif isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "TOOLS" for t in node.targets):
            target = node.value
        if isinstance(target, ast.Dict):
            return sorted(k.value for k in target.keys if isinstance(k, ast.Constant))
    return []


def skills() -> list[str]:
    return sorted(p.parent.name for p in (ROOT / "plugin" / "skills").glob("*/SKILL.md"))


def property_test_files() -> list[dict]:
    out = []
    for p in sorted((ROOT / "tests").rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        if re.search(r"^\s*(from|import) hypothesis", text, re.M):
            out.append({"file": rel(p), "given": len(re.findall(r"@given\(", text))})
    return out


# --------------------------------------------------------------------------------------------- the log
def log_lines() -> list[str]:
    return read(LOG).splitlines()


def log_mentions(words: list[str]) -> int:
    pat = re.compile("|".join(re.escape(w) for w in words), re.I)
    return sum(1 for ln in log_lines() if pat.search(ln))


def excerpts(regex: str, limit: int = 3, width: int = 260, where: str | None = None) -> list[str]:
    """The first ``limit`` log lines matching ``regex`` (case-insensitive), trimmed at a word boundary, each with the
    heading of its entry instead of a line number (line numbers move when the log grows)."""
    pat = re.compile(regex, re.I)
    heading, out = "", []
    for ln in log_lines():
        if ln.startswith("#"):
            heading = ln.lstrip("# ").strip()
            continue
        if heading.startswith("YYYY"):
            continue  # the log's own template entry
        if ln.startswith("- ") and pat.search(ln) and (where is None or where.lower() in heading.lower()):
            text = ln[2:].strip()
            if len(text) > width:
                text = text[:width].rsplit(" ", 1)[0] + " ..."
            out.append(f'"{text}" (entry "{heading}")')
            if len(out) == limit:
                break
    return out


def caught_in_log() -> list[dict]:
    """(spec guess, property number, entry heading) where the log says 'Property N caught'."""
    out, heading = [], ""
    for ln in log_lines():
        if ln.startswith("#"):
            heading = ln.lstrip("# ").strip()
        for m in re.finditer(r"Propert(?:y|ies) (\d+) (?:also )?caught", ln):
            spec = None
            for name, tokens in SPEC_TOKENS.items():
                if any(t in heading.lower() for t in tokens):
                    spec = name
            out.append({"spec": spec, "n": int(m.group(1)), "entry": heading})
    return out


# --------------------------------------------------------------------------------------------- property ledger
def property_ledger(spec_list: list[dict]) -> list[dict]:
    test_files = sorted(p for p in (ROOT / "tests").rglob("*.py"))
    spec_text = {s["name"]: " ".join(read(f"{s['path']}/{n}") for n in ("tasks.md", "design.md", "requirements.md", "bugfix.md"))
                 for s in spec_list}
    mentions = []
    for p in test_files:
        text = p.read_text(encoding="utf-8")
        nums = {int(n) for n in re.findall(r"Property\s+(\d+)", text)}
        for group in re.findall(r"Properties\s+([0-9][0-9, and\u2013\-to]*)", text):
            nums |= {int(n) for n in re.findall(r"\d+", group)}
        if not nums:
            continue
        low = text.lower()
        named = sorted(n for n, toks in SPEC_TOKENS.items() if any(t in low for t in toks))
        by_ref = sorted(s for s, t in spec_text.items() if rel(p) in t or p.name in t)
        owner = named if len(named) == 1 else (by_ref if len(by_ref) == 1 else [])
        mentions.append({"file": rel(p), "nums": nums, "spec": owner[0] if len(owner) == 1 else None,
                         "candidates": sorted(set(named) | set(by_ref))})
    caught = caught_in_log()
    rows = []
    for s in spec_list:
        for n, title in s["properties"]:
            covering = sorted(m["file"] for m in mentions if m["spec"] == s["name"] and n in m["nums"])
            maybe = sorted(m["file"] for m in mentions
                           if m["spec"] is None and n in m["nums"] and (not m["candidates"] or s["name"] in m["candidates"]))
            if covering:
                status = "covered: " + ", ".join(covering)
            elif maybe:
                status = "ambiguous: " + ", ".join(maybe) + " (names Property %d, not the spec)" % n
            else:
                status = "not covered"
            hits = [c for c in caught if c["n"] == n and c["spec"] == s["name"]]
            rows.append({"spec": s["name"], "n": n, "title": title, "status": status,
                         "caught": ("; ".join(f'entry "{c["entry"]}" in {LOG}' for c in hits) if hits else "none recorded")})
    return rows


# --------------------------------------------------------------------------------------------- rendering
def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return out


def collect() -> dict:
    sp = specs()
    return {
        "specs": sp,
        "steering": steering(),
        "hooks": hooks(),
        "agents": agents(),
        "tools": mcp_tools(),
        "skills": skills(),
        "ptests": property_test_files(),
        "ledger": property_ledger(sp),
    }


def render_ledger(f: dict) -> str:
    rows = f["ledger"]
    n = len(rows)
    cov = sum(1 for r in rows if r["status"].startswith("covered"))
    amb = sum(1 for r in rows if r["status"].startswith("ambiguous"))
    lines = [
        "# Property ledger",
        "",
        "Generated by `scripts/kiro_ledger.py` from the working tree. Do not edit by hand.",
        "",
        "One row per (spec, property number): each spec numbers its own properties from 1, so the key is the pair. "
        "A property is \"covered\" when a test file that names that property number also names that spec (or is "
        "listed in that spec's tasks, design or requirements). \"ambiguous\" means a test file names the number but "
        "nothing ties it to this spec. \"caught\" holds a bug only where `docs/KIRO_USAGE.md` says the property caught "
        "it; otherwise \"none recorded\". A covered row means a test cites the property; it does not mean the test is "
        "strong. It was counted from `.kiro/specs/*/design.md` and `tests/**/*.py`.",
        "",
        f"Rows: {n}. Covered: {cov}. Ambiguous: {amb}. Not covered: {n - cov - amb}.",
        "",
    ]
    lines += table(["Spec", "No.", "Property", "Covered by", "Caught"],
                   [[r["spec"], r["n"], r["title"], r["status"], r["caught"]] for r in rows])
    return "\n".join(lines) + "\n"


def facts(f: dict) -> dict:
    sp = f["specs"]
    rows = f["ledger"]
    kiro_specs = [s for s in sp if s["type"] in ("feature", "bugfix")]
    by_trigger: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for h in f["hooks"]:
        by_trigger[h["trigger"]] = by_trigger.get(h["trigger"], 0) + 1
        by_action[h["action"]] = by_action.get(h["action"], 0) + 1
    by_inclusion: dict[str, int] = {}
    for s in f["steering"]:
        by_inclusion[s["inclusion"]] = by_inclusion.get(s["inclusion"], 0) + 1
    return {
        "generated_by": "scripts/kiro_ledger.py",
        "note": "Counted from the working tree when the file was written. Each item names its source path.",
        "items": [
            {"label": "Kiro specs", "count": len(kiro_specs), "source": ".kiro/specs/*/.config.kiro",
             "detail": ", ".join(f"{s['name']} ({s['type']})" for s in kiro_specs)},
            {"label": "Spec folders that are not specs", "count": len(sp) - len(kiro_specs), "source": ".kiro/specs",
             "detail": ", ".join(s["name"] for s in sp if s["type"] not in ("feature", "bugfix")) or "none"},
            {"label": "Requirements headings", "count": sum(s["requirements"] for s in sp), "source": ".kiro/specs/*/requirements.md"},
            {"label": "Correctness properties written in design.md", "count": sum(len(s["properties"]) for s in sp),
             "source": ".kiro/specs/*/design.md"},
            {"label": "Spec tasks done", "count": sum(s["tasks_done"] for s in sp), "source": ".kiro/specs/*/tasks.md"},
            {"label": "Spec tasks open", "count": sum(s["tasks_open"] for s in sp), "source": ".kiro/specs/*/tasks.md"},
            {"label": "Steering files", "count": len(f["steering"]), "source": ".kiro/steering/*.md",
             "detail": ", ".join(f"{k}: {v}" for k, v in sorted(by_inclusion.items()))},
            {"label": "Hooks", "count": len(f["hooks"]), "source": ".kiro/hooks/*.json",
             "detail": "triggers " + ", ".join(f"{k}: {v}" for k, v in sorted(by_trigger.items()))
                       + "; actions " + ", ".join(f"{k}: {v}" for k, v in sorted(by_action.items()))},
            {"label": "Custom agents", "count": len(f["agents"]), "source": ".kiro/agents/*.json",
             "detail": ", ".join(a["name"] for a in f["agents"])},
            {"label": "MCP tools", "count": len(f["tools"]), "source": "mcp_server/server.py (TOOLS)"},
            {"label": "Power skills", "count": len(f["skills"]), "source": "plugin/skills/*/SKILL.md"},
            {"label": "Test files that use Hypothesis", "count": len(f["ptests"]), "source": "tests/**/*.py"},
            {"label": "Property ledger rows", "count": len(rows), "source": "docs/KIRO_PROPERTY_LEDGER.md",
             "detail": "covered %d, ambiguous %d, not covered %d" % (
                 sum(1 for r in rows if r["status"].startswith("covered")),
                 sum(1 for r in rows if r["status"].startswith("ambiguous")),
                 sum(1 for r in rows if r["status"] == "not covered"))},
        ],
    }


def section(title: str, facts_lines: list[str], log: list[str], not_used: list[str], owner: list[str]) -> list[str]:
    out = [f"## {title}", "", "**Counted from the working tree**", ""]
    out += [f"- {x}" for x in facts_lines]
    out += ["", "**From docs/KIRO_USAGE.md** (quoted, not paraphrased)", ""]
    out += [f"- {x}" for x in log] if log else ["- No entry in the usage log matches this topic."]
    out += ["", "**Not used, or not verified**", ""] + [f"- {x}" for x in not_used]
    out += [""] + [f"{x}" for x in owner] + [""]
    return out


def render_story(f: dict) -> str:
    sp = f["specs"]
    kiro_specs = [s for s in sp if s["type"] in ("feature", "bugfix")]
    not_specs = [s for s in sp if s["type"] not in ("feature", "bugfix")]
    ids: dict[str, list[str]] = {}
    for s in kiro_specs:
        cfg = json.loads(read(f"{s['path']}/.config.kiro"))
        ids.setdefault(cfg.get("specId", ""), []).append(s["name"])
    dup = {k: v for k, v in ids.items() if len(v) > 1}
    rows = f["ledger"]
    cov = sum(1 for r in rows if r["status"].startswith("covered"))
    caught = [r for r in rows if r["caught"] != "none recorded"]
    L: list[str] = [
        "# Built with Kiro: the story, counted",
        "",
        "Generated by `scripts/kiro_ledger.py` from the working tree. Do not edit by hand: `scripts/kiro_ledger.py --check` "
        "fails when this file is stale. Every number is followed by the path it was counted from. Anything only the "
        "Owner can know is a placeholder in the form `[OWNER: ...]`. Nothing here is an opinion of the Owner.",
        "",
    ]
    # 1 surfaces
    ide, cli_n, web_n, crew = (log_mentions(["Kiro IDE"]), log_mentions(["Kiro CLI"]),
                               log_mentions(["Kiro Web"]), log_mentions(["Kiro Crew", "Crew"]))
    L += section(
        "1. Which Kiro surfaces were used, and how they differed",
        [f"Lines in the usage log that name Kiro IDE: {ide}; Kiro CLI: {cli_n}; Kiro Web: {web_n}; Kiro Crew: {crew} ({LOG})",
         f"Workspace files Kiro reads: {len(f['steering'])} steering files (.kiro/steering), {len(f['hooks'])} hooks (.kiro/hooks), "
         f"{len(f['agents'])} agents (.kiro/agents), {len(kiro_specs)} specs (.kiro/specs)"],
        excerpts(r".", 2, where="Hooks confirmed firing in the Kiro IDE") + excerpts(r"Analyze Requirements", 1),
        ["Kiro Crew: " + ("named in the usage log" if crew else "no entry in the usage log names it, so it is not claimed."),
         "Kiro Web: " + ("named in the usage log" if web_n else "no entry in the usage log names it, so it is not claimed."),
         "The log does not compare surfaces. Whether the surfaces differed for this project is not recorded here."],
        ["[OWNER: which surfaces you used, and how they differed for you (speed, feel, what you preferred and why).]"])
    # 2 agents
    L += section(
        "2. Custom agents",
        [f"{len(f['agents'])} custom agents (.kiro/agents/*.json): {', '.join(a['name'] for a in f['agents'])}"]
        + [f"{a['name']}: {a['description']} (tools: {', '.join(a['tools']) if a['tools'] else 'not listed'}; {a['file']})"
           for a in f["agents"]],
        excerpts(r"custom agents|`skeptic`|sub-agent", 3, where="agents"),
        ["Whether each agent loads and answers in the Kiro IDE is a row in docs/KIRO_OWNER_CHECKLIST.md with an empty Result "
         "cell: not checked in Kiro.",
         "The Skeptic reviews named in the usage log were run by a sub-agent that could read files but not run commands; "
         "what a review could not check is stated in each entry."],
        ["[OWNER: which agent you found most useful, and what you would change.]"])
    # 3 hooks
    hk = f["hooks"]
    L += section(
        "3. Agent hooks",
        [f"{len(hk)} hooks (.kiro/hooks/*.json): " + ", ".join(f"{h['name']} ({h['trigger']}, {h['action']} action)" for h in hk)],
        excerpts(r".", 2, where="Hooks confirmed firing") + excerpts(r"Property 2 caught", 1),
        ["The usage log records that four of the five original hooks were seen to fire in the Kiro IDE (shown by side effects) "
         "and that the agent-action hook was not checked. The guard hook (PreToolUse) was observed blocking a shell command "
         "once in this IDE; a real `atx` or `aws` block was not tried (docs/KIRO_SURFACES_FORMATS.md).",
         "Hook output was not attached to the agent's tool results in this IDE (docs/KIRO_SURFACES_FORMATS.md), although "
         "Kiro's documentation says stdout is added to the context."],
        ["[OWNER: what hooks changed about how you worked, and which one you would keep.]"])
    # 4 spec vs vibe
    tdone = sum(s["tasks_done"] for s in sp)
    topen = sum(s["tasks_open"] for s in sp)
    L += section(
        "4. Spec-driven development compared with vibe coding",
        [f"{len(kiro_specs)} Kiro specs, {sum(1 for s in kiro_specs if s['type'] == 'feature')} feature and "
         f"{sum(1 for s in kiro_specs if s['type'] == 'bugfix')} bugfix (.kiro/specs/*/.config.kiro)",
         f"{sum(s['requirements'] for s in sp)} requirements headings (.kiro/specs/*/requirements.md), "
         f"{sum(len(s['properties']) for s in sp)} correctness properties (.kiro/specs/*/design.md), "
         f"{tdone} tasks done and {topen} open (.kiro/specs/*/tasks.md)"]
        + [f"{s['name']}: {s['type']}, {s['requirements']} requirements, {len(s['properties'])} properties, "
           f"{s['tasks_done']} done / {s['tasks_open']} open ({s['path']})" for s in kiro_specs]
        + ([f"Folders in .kiro/specs that are not Kiro specs: {', '.join(s['name'] for s in not_specs)} (no .config.kiro)"]
           if not_specs else []),
        excerpts(r"test-first|spec task execution", 2),
        ["The log has no vibe-coded run of the same work to compare against, so it makes no measured comparison of the two.",
         "Not checked: Analyze Requirements (a Kiro IDE action left to the Owner; named as not run in the usage log)."]
        + ([f"Two or more specs share one specId in .kiro/specs/*/.config.kiro: {sorted(map(sorted, dup.values()))}. "
            "Reported to the Owner, not changed."] if dup else []),
        ["[OWNER: how spec-driven work felt compared with vibe coding, in your words.]"])
    # 5 steering
    st = f["steering"]
    L += section(
        "5. Steering documents",
        [f"{len(st)} steering files (.kiro/steering/*.md): " + ", ".join(f"{Path(s['file']).name} ({s['inclusion']})" for s in st)],
        excerpts(r"steering", 2),
        ["Whether Kiro loaded each steering file in the way its inclusion mode says was not observed here.",
         "The guardrails file is also copied into the Power's skill references; a test keeps the copies identical."],
        ["[OWNER: which steering file changed the agent's behaviour most.]"])
    # 6 MCP
    L += section(
        "6. MCP",
        [f"{len(f['tools'])} MCP tools (mcp_server/server.py, TOOLS): {', '.join(f['tools'])}",
         "Workspace server config: .kiro/settings/mcp.json (one server, `ghost`, over stdio)"],
        excerpts(r".", 2, where="workspace MCP registration") + excerpts(r"serv", 1, where="MCP (workspace)"),
        ["The Owner observed the `ghost` server Connected with 13 tools in the Kiro MCP panel on 2026-11-25 "
         "(docs/KIRO_OWNER_CHECKLIST.md). The 14th tool was added afterwards and is a checklist row.",
         "No MCP tool is reachable from the web app. `ghost challenge` and `ghost receipt` have no MCP tool, by design; "
         "`prepare_handoff` writes files and runs nothing."],
        ["[OWNER: how the MCP tools worked for you inside Kiro.]"])
    # 7 PBT
    pt = f["ptests"]
    L += section(
        "7. Property-based testing, and whether it caught issues unit tests missed",
        [f"{len(pt)} test files use Hypothesis (tests/**/*.py), with {sum(p['given'] for p in pt)} `@given` decorators (tests/**/*.py)",
         f"{len(rows)} correctness properties (.kiro/specs/*/design.md), {cov} covered by a test file that names them "
         f"(docs/KIRO_PROPERTY_LEDGER.md)",
         ("Property rows with a recorded catch: " + "; ".join(f"{r['spec']} property {r['n']} ({r['title']})" for r in caught))
         if caught else "Property rows with a recorded catch: none"],
        excerpts(r"Property \d+ caught|property test.*(found|caught)|Hypothesis.*(found|counterexample)", 4),
        ["The usage log says three real bugs were caught by properties (two hook matchers, one detector). It does not say "
         "whether a unit test would also have caught them, so \"caught what unit tests missed\" is not claimed.",
         "The L-04 exact-hit gap was found by a live test of the deployed app, not by a property test; the log records that "
         "the product-input property for it stayed an expected failure until the fix (entry \"Task 3.10 (live-fixes-2026-11-24)\").",
         "Most of the main spec's property tasks are optional and open; the ledger lists which are not covered."],
        ["[OWNER: whether property tests changed how you wrote code.]"])
    # 8 Powers
    L += section(
        "8. Kiro Powers",
        [f"{len(f['skills'])} skills (plugin/skills/*/SKILL.md): {', '.join(f['skills'])}",
         "Power manifest: plugin/plugin.json; MCP config: plugin/mcp.json"],
        excerpts(r".", 2, where="Power layout") + excerpts(r".", 1, where="R-15 Power packaging"),
        ["Installing the Power through the Kiro Powers panel is a row in docs/KIRO_OWNER_CHECKLIST.md with an empty Result "
         "cell: not checked in Kiro.",
         "The AWS Transform Kiro Power is documented by AWS; not installed or tested with Ghost (docs/AWS_TRANSFORM_FACTS.md)."],
        ["[OWNER: your experience installing and using the Power.]"])
    return "\n".join(L).rstrip("\n") + "\n"


def render_readme(f: dict) -> str:
    """README.md with the Kiro table between its markers replaced; nothing else changes."""
    text = read(OUT_README)
    if TABLE_BEGIN not in text or TABLE_END not in text:
        raise SystemExit(f"{OUT_README} has no {TABLE_BEGIN} ... {TABLE_END} block")
    rows = [[i["label"], i["count"], f"`{i['source']}`"] for i in facts(f)["items"]]
    block = "\n".join(table(["What", "Count", "Counted from"], rows))
    head, rest = text.split(TABLE_BEGIN, 1)
    _, tail = rest.split(TABLE_END, 1)
    return f"{head}{TABLE_BEGIN}\n{block}\n{TABLE_END}{tail}"


def outputs() -> dict[str, str]:
    f = collect()
    return {
        OUT_README: render_readme(f),
        OUT_STORY: render_story(f),
        OUT_LEDGER: render_ledger(f),
        OUT_FACTS: json.dumps(facts(f), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    }


def main(argv: list[str]) -> int:
    out = outputs()
    if "--check" in argv:
        stale = [p for p, text in out.items() if read(p) != text]
        if stale:
            print("stale (run scripts/ghost-py scripts/kiro_ledger.py): " + ", ".join(stale), file=sys.stderr)
            return 1
        print("the Kiro ledger outputs are current")
        return 0
    for rel_path, text in out.items():
        (ROOT / rel_path).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {rel_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
