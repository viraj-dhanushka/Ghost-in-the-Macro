# Prompt for round 3 of the agent migration (the repair demonstration)

Written 2026-11-26 and passed to a fresh agent session (no earlier conversation). The only other text the agent
received was a one-line pointer to this file.

You are an agent working in the Ghost in the Macro repository, using the Ghost Power. The migration folder
`.kiro/specs/haunted-delivery-migration/` holds a `logic.py` that passed Faithful verification in round 2. The
rules in `agent-prompt.md` still apply, including what you must not read.

## What happened
The latest verification round (round 3) failed. This failure is a **planted test bug**: someone changed `logic.py`
on purpose, to show the repair loop working. It is not your earlier work, and the log labels it as planted. The
log's label says where the change was made, which would skip the Referee's evidence, so **do not open
`repair-log.md` this round**. Use `repair-brief.json`, `rules.md` and `logic.py`.

## What to do
Follow the "Repair loop" section of `plugin/skills/implement-from-rules/SKILL.md` (read it first):
1. Read `repair-brief.json`.
2. Change only what the brief demonstrates, in `logic.py`. Do not touch anything else.
3. Run the same command as before and read the new brief:

       echo '{"path": ".kiro/specs/haunted-delivery-migration/logic.py"}' | scripts/ghost-py scripts/ghost_hook.py verify

4. Stop after a pass or after "not converged".

## Report back (plain text)
1. What the brief showed, in your own words, and which line you changed and why.
2. The files you changed and every file you opened (including anything on the "must not read" list).
3. The output of the last verification command, verbatim, and how many rounds you ran.
4. Anything you could not do or did not understand.
