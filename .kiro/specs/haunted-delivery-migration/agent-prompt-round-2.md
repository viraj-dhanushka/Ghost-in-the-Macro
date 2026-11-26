# Prompt for round 2 of the agent migration

Written 2026-11-26 and passed to a fresh agent session (no earlier conversation). The only other text the agent
received was a one-line pointer to this file.

You are an agent working in the Ghost in the Macro repository, using the Ghost Power. The migration folder
`.kiro/specs/haunted-delivery-migration/` already holds `logic.py` and `mapping.yaml` written by an earlier agent
session from `rules.md` (see `agent-prompt.md` for its instructions, which still apply, including what you must
not read), and the first verification round has been logged in `repair-log.md` and `repair-brief.json`.

## What happened in round 1 (read `repair-log.md` and `repair-brief.json`)
Faithful verification failed on `quantity=50.1`, `unit_price=-192381013.90`, `delivery_distance_km=-1000000`: the
Referee gave -10409351900.100002 and the module -10409351900.100. The earlier agent's `mapping.yaml` declared no
input types or minimums, because the skill's example showed none and was in a format the engine rejects. The skill
`plugin/skills/implement-from-rules/SKILL.md` has since been corrected (read it again, including the "Repair loop").

## What the user confirms
The user confirms these input domains for this workbook (they come from the autopsy of the sample, not from the
rules, and are the user's decision): `quantity` is an integer with minimum 0; `unit_price` and
`delivery_distance_km` are decimals with minimum 0.

## What to do
1. Update `mapping.yaml` only: declare `type` and `min` for each input as confirmed above, in the format the
   corrected skill shows. The user is telling you to change `mapping.yaml`; that is the one exception in the
   Repair loop. Do not change `logic.py` unless the new verification demonstrates a problem in it.
2. Run the same command as before and read `repair-brief.json`:

       echo '{"path": ".kiro/specs/haunted-delivery-migration/logic.py"}' | scripts/ghost-py scripts/ghost_hook.py verify

   (this verifies `logic.py`; it also runs when `mapping.yaml` is saved).
3. If it reports a difference, follow the "Repair loop" and run again. Stop after a pass or after "not converged".

## Report back (plain text)
1. The files you changed, and a statement of whether `logic.py` is byte-for-byte the same as before.
2. The tools and commands you used, and every file you opened (including anything on the "must not read" list).
3. The output of the last verification command, verbatim, and how many rounds you ran.
4. Anything you could not do or did not understand.
