# Contributing

## Development

```text
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
mypy
```

Keep the default path safe: preview before writes, refuse conflicts, and make
any destructive operation explicit and reversible. Do not add telemetry,
network calls, shell execution, or process control without a separate design
discussion.

## Pull requests

Explain the user pain, include a focused test, update the changelog when user
behavior changes, and run the full CI command set before requesting review.
