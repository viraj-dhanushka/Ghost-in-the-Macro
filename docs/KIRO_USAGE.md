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
