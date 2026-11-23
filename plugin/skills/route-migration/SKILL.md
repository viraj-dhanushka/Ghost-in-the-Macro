---
name: route-migration
description: Recommend whether Ghost converts a workbook, AWS Transform custom does, or both (Split), and hand off to the AWS Transform power.
---

# Route a migration

1. Call `recommend_route` with `workbook`, optional `batch_size` and `migration_dir`.
2. Report the `route` and its `reasons`. The plain-English explanation is written into the migration `design.md` when `migration_dir` is given.
3. For "AWS Transform custom" and "Split", the result includes `atx_command`. It is a dry run. Never execute it yourself.
4. If AWS credentials exist and the official AWS Transform Kiro power is installed, hand `atx_command` to that power. Otherwise show the command to the user.
5. After either path, run `verify_implementation` or `generate_proof_report`. Ghost verifies the result against the original workbook in both cases.
