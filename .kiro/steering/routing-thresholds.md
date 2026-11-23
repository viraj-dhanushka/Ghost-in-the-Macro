---
inclusion: manual
---

# Routing thresholds

The Router (`ghost.router`) reads the fenced YAML block below to choose between "Ghost converts", "AWS Transform custom" and "Split". Edit the numbers to tune routing. Keep the block fenced and keep the key names.

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
```

## Rules

1. Calculator shape (formula-heavy, or VBA lines at or below `vba_line_threshold`) with UserForms and Declares within their thresholds and a batch smaller than `batch_size_threshold`: **Ghost converts**.
2. VBA lines above `vba_line_threshold`, or UserForms above `userform_threshold`, or Declares above `declare_threshold`, or a batch of at least `batch_size_threshold` workbooks: **AWS Transform custom**.
3. A workbook that mixes convertible formulas with VBA above the threshold: **Split** (Ghost converts the formulas, AWS Transform custom handles the VBA).

Routes involving AWS Transform custom produce an `atx custom def exec ...` command as a dry run. Ghost never executes it. The Kiro Power hands the command to the official AWS Transform power only when AWS credentials exist and that power is installed. The Verifier can check the result of either path.
