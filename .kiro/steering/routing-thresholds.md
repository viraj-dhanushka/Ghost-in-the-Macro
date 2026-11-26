---
inclusion: manual
---

# Routing thresholds

The Router (`ghost.router`) reads the fenced YAML block below to choose between "Ghost converts", "AWS Transform custom", "Split" and "Over Ghost's limits". Edit the numbers to tune routing. Keep the block fenced and keep the key names.

```yaml
routing_thresholds:
  version: 1
  # VBA lines above this value mean the VBA part is too large for Ghost.
  vba_line_threshold: 2000
  # UserForm count above this value routes to AWS Transform custom.
  userform_threshold: 3
  # Windows API Declare call count above this value routes to AWS Transform custom.
  declare_threshold: 5
  # A batch with at least this many workbooks routes to AWS Transform custom.
  batch_size_threshold: 10
  # Optional keys (defaults shown). A size threshold never raises Ghost's ingest limit: the smaller value applies.
  # A workbook over one of these is routed from its measured sizes without being loaded.
  max_file_bytes: 5242880
  max_cells: 200000
  max_formulas: 20000
  # The AWS Transform definition named in the suggested command (the AWS-managed, Early-access one).
  transform_definition: AWS/vba-to-python-migration
```

## Rules

1. Calculator shape (formula-heavy, or VBA lines at or below `vba_line_threshold`) with UserForms and Declares within their thresholds and a batch smaller than `batch_size_threshold`: **Ghost converts**.
2. VBA lines above `vba_line_threshold`, or UserForms above `userform_threshold`, or Declares above `declare_threshold`, or a batch of at least `batch_size_threshold` workbooks: **AWS Transform custom**.
3. A workbook that mixes convertible formulas with VBA above the threshold: **Split** (Ghost converts the formulas, AWS Transform custom handles the VBA).

4. A workbook over `max_file_bytes`, `max_cells` or `max_formulas` is not loaded. It gets **AWS Transform custom** (for the VBA part only) when its VBA is above the VBA, UserForm or Declare thresholds, and otherwise **Over Ghost's limits**. In both cases the formulas are not sent to AWS Transform and Ghost does not convert them at that size; AWS Transform custom's documentation describes migrating VBA code and says nothing about worksheet formulas, cell counts or workbook size.
Routes involving AWS Transform custom produce an `atx custom def exec ... -g atx-config.yaml -x -t` command, labelled "suggested command, not run". Ghost never executes it. `-p` must be a Git repository, a non-interactive run exits 0 even when the transformation failed, and `ghost handoff` writes the kit (the `-g` file, the contract, the VBA as text) the command needs. Facts and sources: `docs/AWS_TRANSFORM_FACTS.md`. The owner may hand the kit to the AWS Transform Kiro Power only when AWS credentials exist and that power is installed (it is documented by AWS; not installed or tested with Ghost; see `docs/AWS_TRANSFORM_FACTS.md`). The Verifier can referee returned code only for a workbook within Ghost's limits and an output not fed by a VBA function.
