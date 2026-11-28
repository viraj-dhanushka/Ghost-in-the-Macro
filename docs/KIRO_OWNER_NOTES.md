# Owner notes for docs/KIRO_STORY.md

Write your own text under the eight headings below. `scripts/kiro_ledger.py` prints it, unedited, in place of the
`[OWNER: ...]` placeholder of the same section in `docs/KIRO_STORY.md`. A section with no text (or only a comment like
these) keeps its placeholder. Re-run `scripts/ghost-py scripts/kiro_ledger.py` after editing, so that
`scripts/kiro_ledger.py --check` passes. Nothing here is written for you.

## 1. Surfaces
I used the Kiro IDE for the whole build. I did not use the Kiro CLI, Web or Crew, so I can't compare them. The IDE kept the specs, the hooks, the steering files and the MCP panel in one place, and that is how all the work in this repository was done.

## 2. Custom agents
The Skeptic was the most useful of the four agents. It reviews read-only and has to say what it could not check, and it caught a blurb that claimed Ghost converts a cell the engine does not convert. What I would change: one invocation returned nothing and the main agent did the review in role instead, so I would want every agent run to be visible and repeatable.

## 3. Agent hooks
Hooks moved the checks to the moment of the change. Saving logic.py re-ran verification, recording a decision regenerated the report, and adding a workbook to graveyard/ ran an autopsy. The one I would keep is the PreToolUse guard. It stopped the agent from running atx or aws commands until I approved; for the deploy I approved one session and revoked it straight after.

## 4. Spec-driven development compared with vibe coding
Most features started as a spec: requirements, a design with correctness properties, then tasks. That was slower to start but easy to review, because each change could be checked against a numbered requirement. I used vibe coding once, for the visual theme of the web app. It reached a good-looking result faster, because I could look, judge and adjust in a round or two. But nothing pinned the visual behaviour, and two visual bugs, an invisible fade-in and an oversized step marker, were found only by looking at screenshots.

## 5. Steering documents
ghost-guardrails.md changed the agent's behaviour most. It holds the honesty rule: say "no difference found on N cases", never "correct" or "proven", and write "not checked" where nothing ran. The custom agents load it as a resource, so the reviews and the code use the same words.

## 6. MCP
The same engine runs as an MCP server, so Kiro could call Ghost's own tools, such as analysing a workbook, listing rules and verifying, instead of going through a shell. I saw the ghost server Connected in the Kiro MCP panel on 25 November with 13 tools; a fourteenth, prepare_handoff, was added later.

## 7. Property-based testing
The property ledger maps 68 correctness properties to tests: 41 are covered, and the ones without a test are listed as not covered instead of being hidden. Property tests found three real bugs, including two hook matchers that matched more paths than intended.

## 8. Kiro Powers
The plugin/ folder is packaged as a Power with eight skills and the MCP server. I have not installed it through the Powers panel, so I can't report on that experience. I did not install the AWS Transform Power either.
