# Kiro usage log

Running log of how Kiro is used in this repository. Add one entry per notable use. Newest entries go at the bottom.

## Entry template

```
### YYYY-MM-DD: <short title>
- Feature: spec | steering | hook | agent | power | vibe
- Goal: what I wanted
- What Kiro did: files created or changed
- Outcome: what worked, what needed correction
- Spec or task reference: e.g. tasks.md 2.1
```

## Entries

### Spec creation: ghost-in-the-macro
- Feature: spec
- Goal: turn the product idea into a requirements-first spec for the whole project.
- What Kiro did: created `.kiro/specs/ghost-in-the-macro/requirements.md`, `design.md` and `tasks.md` (P0 core engine, Kiro Power and web app; P1 mutation self-check and routing; P2 stretch VBA and TypeScript).
- Outcome: spec drives the task list that is executed task by task.
- Spec or task reference: `.kiro/specs/ghost-in-the-macro/`

### Steering files and repository setup
- Feature: steering
- Goal: give Kiro the product, technology, structure and guardrail context for every session.
- What Kiro did: workspace rules `product`, `tech`, `structure` and `ghost-guardrails` under `.kiro/steering/`.
- Outcome: generated code follows Decimal, determinism and "not converted" conventions.
- Spec or task reference: tasks.md 1.x

### 2026-11: Public deployment on ECS Express Mode (task 14)
- Feature: spec, hooks, agents
- Goal: put the web app at a public URL and check the demo flow end to end.
- What Kiro did: the first target was AWS App Runner, but it is closed to new customers, so the deployment moved to ECS Express Mode. App Runner files were deleted; `scripts/deploy_ecs_express.sh` and `docs/DEPLOY_ECS_EXPRESS.md` were added. The first deployed container could not start the Referee. Using `ldd` on LibreOffice's pyuno showed that the `python:3.11-slim` image's `/usr/local` libpython was loaded instead of the system one. The `Dockerfile` now uses `debian:bookworm-slim` with the app's Python venv kept off `PATH`, so LibreOffice uses the system Python.
- Verification on the live service: `/healthz` reports the Referee available; the haunted sample shows F-001; recording D-001 gives a Faithful run that passes (300 cases) and an Intended run with one expected difference at quantity=50; report.html, report.json and module.zip download. The web flow reports the mutation score as "not checked" because `web/flow.py` does not pass mutation cases.
- Kiro features used: the spec (`.kiro/specs/ghost-in-the-macro/`) defined and tracked the task; sub-agents (`.kiro/agents/`) were used for spec task execution; hooks in `.kiro/hooks/` (autopsy on graveyard add, regenerate report on decision, golden tests on converter save, reverify on logic save) are part of the repository workflow.
- Spec or task reference: tasks.md 14
