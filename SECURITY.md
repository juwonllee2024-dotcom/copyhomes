# Security policy

## Scope

CopyHomes is a local file-copy utility. It has no runtime dependencies, no
network client, no telemetry, no clipboard access, no shell execution, and no
process control.

## Safe-by-default boundaries

- `plan` is read-only and never creates directories or files.
- `save` requires an explicit receipt path, refuses differing targets by
  default, and only replaces with explicit `--replace`.
- New files are created with exclusive-create semantics; replacements use a
  temporary file followed by an atomic rename.
- Every copied target is verified with SHA-256 before success is reported.
- `undo` checks the current target hash first and refuses to delete or restore
  a file that changed after the receipt.
- Recovery files are stored under a receipt-local, validated directory.

## Limitations

CopyHomes cannot protect against another process changing a file immediately
after its final verification. Do not use it as a substitute for backups,
access control, or encrypted storage. Receipts contain absolute local paths and
hashes; treat them as sensitive operational metadata.

## Reporting

Do not open public issues for undisclosed vulnerabilities. Contact the
maintainer privately through the GitHub profile before publishing exploit
details. Include reproduction steps, platform, Python version, and whether a
receipt or `--replace` was involved.
