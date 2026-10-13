# Stage-audit reference

`stage_audit` compares saved retrieval, context, and answer records. It uses only the Python standard library. It makes no model or network calls.

The tool accepts records from pipelines that meet the contract below. It cannot recover an unrecorded stage. A stable answer does not prove that a model used its context. Agreement with a no-memory answer does not prove that the model ignored its context.

The [toy example](../examples/stage_audit/README.md) gives an executable command and its expected results.

## Python interface

```python
from stage_audit import audit

report = audit(
    baseline="runs/baseline.jsonl",
    changed="runs/changed.jsonl",
    no_memory="runs/no_memory.jsonl",
    answer_key="runs/answer_key.jsonl",
    group_by="history",
    baseline_broadcast=(),
    no_memory_broadcast=(),
)
result = report.summary()
```

`audit` reads four local JSONL files. Each non-empty file has one JSON object per line. Blank lines and duplicate JSON fields are errors. The function returns an `AuditReport`. Its `summary()` method returns a new JSON-compatible dictionary.

`group_by` accepts only `"history"`. Each workload has a separate report. The tool does not pool workloads.

`baseline_broadcast` and `no_memory_broadcast` each accept `()` or `("draw",)`. The empty tuple requires an exact match on all five run identifiers. `("draw",)` requires the corresponding file to omit `draw`. It then reuses each question and order record across the changed run's draws. Broadcasting never applies to order, question, history, or workload.

Missing records, extra records, duplicate keys, and inconsistent answer keys raise `ValueError`. File access errors raise `OSError`. No input file changes.

## Input records

Each file represents one reader and one condition. Reader, prompt, decoding, and intervention settings need a separate experiment manifest. The tool cannot verify those settings from these records.

Each answer-key record has exactly these fields.

| Field | Type | Meaning |
| --- | --- | --- |
| `workload` | Non-empty string | Stable workload identifier. |
| `history` | Non-empty string | Stable conversation or history identifier. |
| `question` | Non-empty string | Stable question identifier within the workload and history. |
| `option_ids` | List of unique strings | All semantic option identifiers. At least two options are required. |
| `correct_answer_id` | String | One identifier from `option_ids`. |

The composite question key is `workload`, `history`, and `question`. Bare question identifiers need not be globally unique. The answer key and changed run must contain exactly the same question keys.

Each run record has these required fields.

| Field | Type | Meaning |
| --- | --- | --- |
| `workload`, `history`, `question` | Non-empty strings | The composite question key. |
| `draw` | Non-empty string | A graph, intervention, or sampling draw. Omit only under declared draw broadcasting. |
| `order` | Non-empty string | An answer-option presentation order. Use the same identifier in every run. |
| `shortlist_ids` | List of unique strings | Message identifiers in retrieval order. |
| `context_ids` | List of unique strings | Message identifiers in serialized context order. |
| `context_sha256` | String | Lowercase SHA-256 of the exact serialized context bytes in UTF-8. |
| `status` | `"valid"` or `"invalid"` | Whether the response selected a valid semantic option. |
| `answer_id` | String or `null` | A stable semantic option identifier for a valid response. Invalid responses require `null`. |

Use semantic identifiers such as `option_release_date`, not displayed letters whose meaning changes with the presentation order. Convert a displayed answer through that order's option map before comparison.

The tool rejects unavailable responses. An absent completion is not an invalid answer. The experiment must resolve coverage before this tool can report a complete comparison.

The following fields are optional. Other fields are errors.

| Field | Type | Check |
| --- | --- | --- |
| `context_text` | String | Its UTF-8 hash must equal `context_sha256`. No normalization is applied. |
| `correct_answer_id` | String | Must match the question's answer key. |
| `option_map` | Object | Maps displayed labels to every semantic option exactly once. Requires `answer_label`. |
| `answer_label` | String or `null` | Must map to `answer_id`. Invalid responses require `null`. Requires `option_map`. |
| `reached_person_ids` | List of unique strings | Treated as a set. Must appear in every baseline and changed record, or in neither run. |
| `reference_ids` | List of unique strings | Recorded reference identifiers present at the chosen stage. Treated as a set with the same availability rule. |

Reference identifiers need the same meaning in both runs. Their change rate does not measure reference coverage or factual support. The input contract has no full reference inventory.

No-memory records use the same required schema. Their `shortlist_ids` and `context_ids` are empty. Their `context_sha256` is the SHA-256 of the empty string. The task instruction, question, and options are outside the context hash.

Each run key is the composite question key followed by `draw` and `order`. Within each changed-run question, every draw must have the same set of orders. Strict joins enforce the same observed comparison grid in all runs, subject to explicit draw broadcasting.

An entire missing draw, order, question, or history can remain undetected if every file omits it. A separate experiment manifest must establish intended coverage. The report states this limitation.

## Weights and report fields

For one workload, let `H` be the number of histories. Let `Q_h` be the question count in history `h`. Let `D_q` be the draw count for question `q`, and `O_qd` its order count for draw `d`. A paired record has weight `1 / (H Q_h D_q O_qd)`.

Thus the tool averages orders within a draw, draws within a question, and questions within a history. Each history has equal total weight. Questions with more draws or orders receive no extra weight.

Every metric has a raw paired-record `count` and a weighted `mass`. Mass is a fraction between zero and one. It is not a percentage. Raw counts include repeated logical comparisons after declared broadcasting. They are not independent sample counts.

The stage metrics have these meanings.

| Metric | Event |
| --- | --- |
| `shortlist_membership_changed` | The two sets of shortlist IDs differ. |
| `shortlist_order_only_changed` | The sets match, but their sequences differ. |
| `shortlist_sequence_changed` | Membership, order, or both differ. This is the sum of the previous two events. |
| `context_ids_changed` | The ordered context ID lists differ. |
| `context_changed` | The exact serialized context hashes differ. This hash comparison controls all context-change conditions. |
| `reached_people_changed` | The optional reached-person sets differ. |
| `reference_ids_changed` | The optional reference ID sets differ. |

Context IDs and context text can disagree about a change. For example, text can change while its source ID stays fixed. The report retains both events.

`baseline_correct` and `changed_correct` measure agreement with the answer key. An invalid response scores zero. `gain` means baseline incorrect and changed correct. `loss` means baseline correct and changed incorrect. `accuracy_difference` equals gain mass minus loss mass.

The following six categories are disjoint and sum to one.

- `valid_correct_to_correct`.
- `valid_correct_to_wrong`.
- `valid_wrong_to_correct`.
- `valid_wrong_to_same_wrong`.
- `valid_wrong_to_different_wrong`.
- `invalid_involved`.

The last category means at least one baseline or changed response is invalid. Two invalid responses are not stable semantic answers. `baseline_invalid`, `changed_invalid`, and `no_memory_invalid` also report invalid mass separately.

`stable_answer` and `changed_answer` require two valid answers. The stable event means identical semantic option IDs. The changed event means different semantic option IDs. These summary events overlap the transition categories. Do not add the two groups together. Gains and losses can also overlap `invalid_involved`.

`no_memory_given_context_change` reports separate stable-answer and changed-answer groups. Each group includes its original context-change mass, valid no-memory mass, and invalid no-memory mass. For each group, it reports both baseline and changed agreement with the no-memory answer.

An agreement rate divides original agreement mass by original valid no-memory mass in that group. It never gives the selected histories new equal weights. An empty denominator produces `null`. Invalid no-memory responses remain visible and do not count as agreement or disagreement.

The report contains no confidence intervals, causal estimates, or tests of significance. It cannot measure service nondeterminism without a separate unchanged-input replay comparison. It does not infer reader behavior from answer agreement alone.

## Command-line interface

The tool requires Python 3.11 or later and has no runtime dependencies outside
the standard library. Run `pip install .` from the repository root to install
the `stage-audit` command. You can also use `PYTHONPATH=src` to run the module
directly from the repository root.

```bash
PYTHONPATH=src python -m stage_audit \
  --baseline examples/stage_audit/baseline.jsonl \
  --changed examples/stage_audit/changed.jsonl \
  --no-memory examples/stage_audit/no_memory.jsonl \
  --answer-key examples/stage_audit/answer_key.jsonl
```

The command prints JSON to standard output. `--baseline-broadcast-draw` and `--no-memory-broadcast-draw` enable their corresponding declarations. A validation error prints an error to standard error, exits with code 2, and prints no report.
