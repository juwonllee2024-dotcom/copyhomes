# Verification record

Status: public `v0.1.0` release published; post-release documentation update.

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

- Release commit: `a596a094d48831644e50af732b6e53103f72d53c`.
- CI: [12/12 jobs passed](https://github.com/juwonllee2024-dotcom/copyhomes/actions/runs/33985085192).
- Release: [`v0.1.0`](https://github.com/juwonllee2024-dotcom/copyhomes/releases/tag/v0.1.0)
  is public and non-draft.
- `copyhomes-0.1.0-py3-none-any.whl`: `sha256:850b321b7ae5c7e4240f8bd04d315f0ded1f3f3267f1c46d787742a8a700d677`
- `copyhomes-0.1.0.tar.gz`: `sha256:0a9a843bb318e2255370503f835f4cb7ca3f1bfff913bdb427e81d17cfcfb404`
- The release tag points to the release commit above; this documentation
  update is pushed immediately after publication.
