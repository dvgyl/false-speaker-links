from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


QuestionKey = tuple[str, str, str]
RunKey = tuple[str, str, str, str | None, str]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class _AnswerKey:
    options: frozenset[str]
    correct: str


@dataclass(frozen=True)
class _Record:
    key: RunKey
    shortlist: tuple[str, ...]
    context: tuple[str, ...]
    context_sha256: str
    answer: str | None
    reached: frozenset[str] | None
    references: frozenset[str] | None


@dataclass(frozen=True)
class AuditReport:
    _data: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        """Return a JSON-ready copy of the report. Rates are fractions, not percentages."""
        return json.loads(json.dumps(self._data, allow_nan=False))


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _ids(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of unique strings")
    result = tuple(_text(item, name) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} contains duplicate IDs")
    return result


def _rows(path: str | Path) -> list[dict[str, Any]]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"duplicate JSON field {name!r}")
            result[name] = value
        return result

    result = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                row = json.loads(line, object_pairs_hook=unique_object)
                if not isinstance(row, dict):
                    raise ValueError("each line must be a JSON object")
            except ValueError as error:
                raise ValueError(f"{path}, line {line_number}: {error}") from error
            result.append(row)
    if not result:
        raise ValueError(f"{path} is empty")
    return result


def _question(row: dict[str, Any]) -> QuestionKey:
    return tuple(_text(row.get(name), name) for name in ("workload", "history", "question"))


def _answer_keys(path: str | Path) -> dict[QuestionKey, _AnswerKey]:
    keys = {}
    fields = {"workload", "history", "question", "option_ids", "correct_answer_id"}
    for row in _rows(path):
        if set(row) != fields:
            raise ValueError("answer-key fields must match the documented schema")
        key = _question(row)
        options = frozenset(_ids(row["option_ids"], "option_ids"))
        correct = _text(row["correct_answer_id"], "correct_answer_id")
        if len(options) < 2 or correct not in options:
            raise ValueError(f"{key}: the answer key needs at least two options and a valid correct ID")
        if key in keys:
            raise ValueError(f"duplicate answer key {key}")
        keys[key] = _AnswerKey(options, correct)
    return keys


def _run(
    path: str | Path, keys: dict[QuestionKey, _AnswerKey], *, broadcast: bool, no_memory: bool = False
) -> dict[RunKey, _Record]:
    required = {"workload", "history", "question", "order", "shortlist_ids", "context_ids",
                "context_sha256", "status", "answer_id"}
    if not broadcast:
        required.add("draw")
    optional = {"context_text", "reached_person_ids", "reference_ids", "correct_answer_id",
                "option_map", "answer_label"}
    result = {}
    for row in _rows(path):
        if not required <= set(row) or set(row) - required - optional:
            raise ValueError(f"{path}: run fields do not match the schema or draw declaration")
        question = _question(row)
        if question not in keys:
            raise ValueError(f"{path}: no answer key for {question}")
        answer_key = keys[question]
        key = (*question, None if broadcast else _text(row["draw"], "draw"), _text(row["order"], "order"))
        if key in result:
            raise ValueError(f"{path}: duplicate run key {key}")
        if "correct_answer_id" in row and row["correct_answer_id"] != answer_key.correct:
            raise ValueError(f"{key}: inconsistent answer key")
        status, answer = row["status"], row["answer_id"]
        if status not in ("valid", "invalid"):
            raise ValueError(f"{key}: status must be valid or invalid; unavailable responses are unsupported")
        if status == "invalid" and answer is not None:
            raise ValueError(f"{key}: an invalid response must have a null answer_id")
        if status == "valid" and (not isinstance(answer, str) or answer not in answer_key.options):
            raise ValueError(f"{key}: answer_id must be a semantic option ID from the answer key")
        if ("option_map" in row) != ("answer_label" in row):
            raise ValueError(f"{key}: displayed labels need both option_map and answer_label")
        if "option_map" in row:
            option_map = row["option_map"]
            if not isinstance(option_map, dict) or not all(isinstance(k, str) and k for k in option_map):
                raise ValueError(f"{key}: option_map must map displayed labels to semantic IDs")
            values = tuple(option_map.values())
            if not all(isinstance(v, str) for v in values) or len(values) != len(answer_key.options) or set(values) != answer_key.options:
                raise ValueError(f"{key}: option_map must map each semantic option exactly once")
            label = row["answer_label"]
            if status == "valid" and (not isinstance(label, str) or option_map.get(label) != answer):
                raise ValueError(f"{key}: answer_label and answer_id disagree")
            if status == "invalid" and label is not None:
                raise ValueError(f"{key}: an invalid response must have a null answer_label")
        context_hash = row["context_sha256"]
        if not isinstance(context_hash, str) or not _SHA256.fullmatch(context_hash):
            raise ValueError(f"{key}: context_sha256 must contain 64 lowercase hexadecimal characters")
        if "context_text" in row:
            if not isinstance(row["context_text"], str) or hashlib.sha256(row["context_text"].encode("utf-8")).hexdigest() != context_hash:
                raise ValueError(f"{key}: context_text does not match context_sha256")
        shortlist = _ids(row["shortlist_ids"], "shortlist_ids")
        context = _ids(row["context_ids"], "context_ids")
        if no_memory and (shortlist or context or context_hash != hashlib.sha256(b"").hexdigest()):
            raise ValueError(f"{key}: no_memory requires empty shortlist, context IDs, and context text")
        result[key] = _Record(
            key, shortlist, context, context_hash, answer,
            frozenset(_ids(row["reached_person_ids"], "reached_person_ids")) if "reached_person_ids" in row else None,
            frozenset(_ids(row["reference_ids"], "reference_ids")) if "reference_ids" in row else None,
        )
    return result


def _join(
    target: dict[RunKey, _Record], source: dict[RunKey, _Record], *, broadcast: bool, name: str
) -> dict[RunKey, _Record]:
    joined, used = {}, set()
    for key in target:
        source_key = (*key[:3], None, key[4]) if broadcast else key
        if source_key not in source:
            raise ValueError(f"{name}: missing join for {key}")
        joined[key] = source[source_key]
        used.add(source_key)
    if used != set(source):
        raise ValueError(f"{name}: unused run records prevent an exact join")
    return joined


def _weights(records: dict[RunKey, _Record]) -> dict[RunKey, Fraction]:
    cells = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(set))))
    for workload, history, question, draw, order in records:
        cells[workload][history][question][draw].add(order)
    result = {}
    for workload, histories in cells.items():
        for history, questions in histories.items():
            for question, draws in questions.items():
                if len({frozenset(orders) for orders in draws.values()}) != 1:
                    raise ValueError(f"{(workload, history, question)}: incomplete order-by-draw grid")
                for draw, orders in draws.items():
                    weight = Fraction(1, len(histories) * len(questions) * len(draws) * len(orders))
                    for order in orders:
                        result[(workload, history, question, draw, order)] = weight
    return result


def _events(baseline: _Record, changed: _Record, no_memory: _Record, key: _AnswerKey) -> dict[str, bool]:
    valid_pair = baseline.answer is not None and changed.answer is not None
    before_correct, after_correct = baseline.answer == key.correct, changed.answer == key.correct
    stable = valid_pair and baseline.answer == changed.answer
    switched = valid_pair and not stable
    membership_changed = set(baseline.shortlist) != set(changed.shortlist)
    events = {
        "shortlist_membership_changed": membership_changed,
        "shortlist_order_only_changed": not membership_changed and baseline.shortlist != changed.shortlist,
        "shortlist_sequence_changed": baseline.shortlist != changed.shortlist,
        "context_ids_changed": baseline.context != changed.context,
        "context_changed": baseline.context_sha256 != changed.context_sha256,
        "baseline_correct": before_correct,
        "changed_correct": after_correct,
        "gain": not before_correct and after_correct,
        "loss": before_correct and not after_correct,
        "baseline_invalid": baseline.answer is None,
        "changed_invalid": changed.answer is None,
        "no_memory_invalid": no_memory.answer is None,
        "invalid_involved": not valid_pair,
        "stable_answer": stable,
        "changed_answer": switched,
        "valid_correct_to_correct": valid_pair and before_correct and after_correct,
        "valid_correct_to_wrong": valid_pair and before_correct and not after_correct,
        "valid_wrong_to_correct": valid_pair and not before_correct and after_correct,
        "valid_wrong_to_same_wrong": stable and not before_correct,
        "valid_wrong_to_different_wrong": switched and not before_correct and not after_correct,
    }
    for name, attribute in (("reached_people_changed", "reached"), ("reference_ids_changed", "references")):
        if getattr(baseline, attribute) is not None:
            events[name] = getattr(baseline, attribute) != getattr(changed, attribute)
    return events


def _mass(events: list[tuple[Fraction, dict[str, bool]]], name: str) -> dict[str, float | int]:
    return {"count": sum(flags[name] for _, flags in events),
            "mass": float(sum(weight for weight, flags in events if flags[name]))}


def audit(
    *, baseline: str | Path, changed: str | Path, no_memory: str | Path,
    answer_key: str | Path, group_by: str = "history",
    baseline_broadcast: tuple[str, ...] = (), no_memory_broadcast: tuple[str, ...] = (),
) -> AuditReport:
    """Audit saved pipeline stages with strict joins and equal history weights.

    Inputs use the schema in docs/stage_audit.md. Only an explicitly declared
    draw dimension can broadcast. Missing or ambiguous records raise ValueError.
    The function reads local JSONL files and makes no network calls.
    """
    if group_by != "history":
        raise ValueError("group_by must be 'history'")
    if baseline_broadcast not in ((), ("draw",)) or no_memory_broadcast not in ((), ("draw",)):
        raise ValueError("only broadcast=('draw',) is supported")
    keys = _answer_keys(answer_key)
    altered = _run(changed, keys, broadcast=False)
    if {key[:3] for key in altered} != set(keys):
        raise ValueError("the answer key and changed run must contain exactly the same questions")
    base = _run(baseline, keys, broadcast=bool(baseline_broadcast))
    memoryless = _run(no_memory, keys, broadcast=bool(no_memory_broadcast), no_memory=True)
    base = _join(altered, base, broadcast=bool(baseline_broadcast), name="baseline")
    memoryless = _join(altered, memoryless, broadcast=bool(no_memory_broadcast), name="no_memory")
    weights = _weights(altered)
    capabilities = {}
    for attribute in ("reached", "references"):
        availability = {getattr(record, attribute) is not None for record in (*base.values(), *altered.values())}
        if len(availability) != 1:
            raise ValueError(f"{attribute}: optional stage availability must be consistent in both runs")
        capabilities[attribute] = availability.pop()
    workloads = {}
    for workload in sorted({key[0] for key in altered}):
        selected = [key for key in altered if key[0] == workload]
        rows = [(weights[key], _events(base[key], altered[key], memoryless[key], keys[key[:3]])) for key in selected]
        metrics = {name: _mass(rows, name) for name in rows[0][1]}
        conditional = {}
        for state in ("stable_answer", "changed_answer"):
            eligible = [key for key, (_, flags) in zip(selected, rows) if flags["context_changed"] and flags[state]]
            valid = [key for key in eligible if memoryless[key].answer is not None]
            denominator = sum((weights[key] for key in valid), Fraction())
            agreements = {}
            for name, run in (("baseline", base), ("changed", altered)):
                matched = [key for key in valid if run[key].answer == memoryless[key].answer]
                numerator = sum((weights[key] for key in matched), Fraction())
                agreements[name] = {"count": len(matched), "mass": float(numerator),
                                    "rate": float(numerator / denominator) if denominator else None}
            conditional[state] = {
                "context_changed_count": len(eligible),
                "context_changed_mass": float(sum((weights[key] for key in eligible), Fraction())),
                "valid_no_memory_count": len(valid), "valid_no_memory_mass": float(denominator),
                "invalid_no_memory_count": len(eligible) - len(valid),
                "invalid_no_memory_mass": float(sum((weights[key] for key in eligible if memoryless[key].answer is None), Fraction())),
                "agreement": agreements,
            }
        workloads[workload] = {
            "histories": len({key[1] for key in selected}),
            "questions": len({key[:3] for key in selected}), "paired_records": len(selected),
            "metrics": metrics,
            "accuracy_difference": metrics["changed_correct"]["mass"] - metrics["baseline_correct"]["mass"],
            "no_memory_given_context_change": conditional,
        }
    return AuditReport({
        "schema_version": 1,
        "weighting": "equal history, equal question within history, equal draw within question, equal order within draw; separate workloads",
        "context_change_basis": "exact serialized context SHA-256",
        "broadcast": {"baseline": list(baseline_broadcast), "no_memory": list(no_memory_broadcast)},
        "optional_stages": capabilities,
        "coverage_limit": "Joins and observed order-by-draw grids are complete. Entire missing draws, orders, questions, or histories cannot be inferred without an external design manifest.",
        "workloads": workloads,
    })
