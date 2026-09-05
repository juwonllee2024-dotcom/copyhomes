# Verification record

Status: local checks passed; awaiting public CI and release verification.

## TDD

- RED: tests were written first and failed with
  `ModuleNotFoundError: No module named 'copyhomes'`.
- GREEN: plan, conflict refusal, copy receipt, replacement undo, changed-target
  refusal, JSON preview, receipt requirement, and CLI round-trip pass after
  implementation.

## Fresh commands

```text
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
mypy
python -m compileall -q src tests
python -m build
pip-audit --local
git diff --check
```

All commands above passed on 2026-09-05. `pip-audit --local` reported no known
vulnerabilities; unpublished local packages were skipped because they are not
on PyPI.

## Real input

```text
copyhomes plan examples/sample.txt ./demo-a ./demo-b --create-dirs --json
```

Expected behavior: JSON preview reports two `create` actions and does not write
either destination. A fresh temporary-directory smoke run then executed the
real CLI end to end:

```text
{"plan_states": ["create", "create"], "round_trip": "verified", "save": {"created": 2, "receipt": "<temporary receipt>", "replaced": 0, "skipped": 0}, "undo": {"receipt": "<temporary receipt>", "removed": 2, "restored": 0}}
```

The source was copied to two homes, its contents were asserted, and both
created targets were removed by `undo`.

## Security evidence

Local `rg` scans found no shell/process/network/socket calls and no common
secret patterns in source, tests, documentation, or CI. A dedicated protected
security connector is unavailable in this environment; that is not represented
as a successful scan.

## Release identity

- Commit: recorded after all checks pass.
- CI: recorded after public push and matrix success.
- Release: recorded after `v0.1.0` is published.
- Package SHA-256: recorded from exact release assets.
