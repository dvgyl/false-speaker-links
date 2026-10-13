# Run the toy stage audit

This example compares four saved question responses without model or network calls.

1. Open a terminal in the repository root.
2. Run this command with Python 3.13.

```bash
PYTHONPATH=src python -m stage_audit \
  --baseline examples/stage_audit/baseline.jsonl \
  --changed examples/stage_audit/changed.jsonl \
  --no-memory examples/stage_audit/no_memory.jsonl \
  --answer-key examples/stage_audit/answer_key.jsonl
```

3. Compare the JSON output with `examples/stage_audit/expected.json`.

The report gives each of the two histories half the total weight. The short history has one question. The long history has three questions. The short-history response therefore has weight `1/2`. Each long-history response has weight `1/6`.

All four contexts change. One answer stays the same. One answer improves. One correct answer becomes invalid. One wrong answer changes to another wrong answer. Gain and loss mass are both `1/6`, so accuracy does not change.

The stable-answer mass is `1/2`. Its no-memory agreement rate is `1`. The valid changed-answer mass is `1/3`. Both its baseline and changed no-memory agreement rates are `1/2`.

4. Run the checks. They need `pytest`.

```bash
PYTHONPATH=src python -m pytest -q tests/test_stage_audit.py
```

The checks compare the example's API and command-line output with `expected.json`. The command-line check blocks socket creation. Other checks cover semantic option rotation, input joins, invalid responses, and conditional weights.

See the [input and metric reference](../../docs/stage_audit.md) to convert records from another pipeline.
