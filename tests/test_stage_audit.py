import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from stage_audit import audit


def record(question="q", *, history="h", draw="0", order="0", answer="option_red", text="before", workload="toy"):
    return {
        "workload": workload, "history": history, "question": question, "draw": draw, "order": order,
        "shortlist_ids": ["message_1", "message_2"], "context_ids": ["message_1"],
        "context_sha256": hashlib.sha256(text.encode()).hexdigest(), "context_text": text,
        "status": "invalid" if answer is None else "valid", "answer_id": answer,
    }


def memoryless(row, answer="option_red"):
    result = {**row, "shortlist_ids": [], "context_ids": [], "context_text": "",
              "context_sha256": hashlib.sha256(b"").hexdigest(), "answer_id": answer,
              "status": "invalid" if answer is None else "valid"}
    return result


def inputs(tmp_path, baseline=None, changed=None, no_memory=None):
    baseline = baseline or [record()]
    changed = changed or [record(text="after")]
    no_memory = no_memory or [memoryless(row) for row in baseline]
    keys = {}
    for row in changed:
        key = tuple(row[name] for name in ("workload", "history", "question"))
        keys[key] = {name: row[name] for name in ("workload", "history", "question")}
        keys[key].update(option_ids=["option_red", "option_blue", "option_green"], correct_answer_id="option_blue")
    values = dict(baseline=baseline, changed=changed, no_memory=no_memory, answer_key=list(keys.values()))
    paths = {}
    for name, rows in values.items():
        paths[name] = tmp_path / f"{name}.jsonl"
        paths[name].write_text("".join(json.dumps(row) + "\n" for row in rows))
    return paths


def rewrite(path, change):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    change(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def workload(paths, **kwargs):
    return audit(**paths, **kwargs).summary()["workloads"]["toy"]


def test_weights_average_orders_draws_questions_and_histories_before_conditioning(tmp_path):
    base, changed, no_memory = [], [], []
    for draw in ("0", "1"):
        for order in ("0", "1"):
            row = record(history="one", draw=draw, order=order)
            base.append(row)
            changed.append(record(history="one", draw=draw, order=order, text="after",
                                  answer="option_red" if draw == "0" else "option_blue"))
            no_memory.append(memoryless(row))
    for question in ("q1", "q2"):
        row = record(question, history="two")
        base.append(row)
        changed.append(record(question, history="two", text="after"))
        no_memory.append(memoryless(row, "option_green"))
    result = workload(inputs(tmp_path, base, changed, no_memory))
    assert result["metrics"]["stable_answer"] == {"count": 4, "mass": .75}
    assert result["metrics"]["gain"]["mass"] == .25
    conditional = result["no_memory_given_context_change"]["stable_answer"]
    assert conditional["valid_no_memory_mass"] == .75
    assert conditional["agreement"]["changed"]["mass"] == .25
    assert conditional["agreement"]["changed"]["rate"] == pytest.approx(1 / 3)


def test_semantic_options_survive_display_rotation(tmp_path):
    base = record()
    base.update(answer_label="A", option_map={"A": "option_red", "B": "option_blue", "C": "option_green"})
    changed = record(text="after")
    changed.update(answer_label="B", option_map={"A": "option_green", "B": "option_red", "C": "option_blue"})
    result = workload(inputs(tmp_path, [base], [changed]))
    assert result["metrics"]["stable_answer"]["mass"] == 1
    assert result["metrics"]["changed_answer"]["mass"] == 0


def test_same_display_letter_can_mean_a_different_answer(tmp_path):
    base = record()
    base.update(answer_label="A", option_map={"A": "option_red", "B": "option_blue", "C": "option_green"})
    changed = record(answer="option_blue")
    changed.update(answer_label="A", option_map={"A": "option_blue", "B": "option_red", "C": "option_green"})
    assert workload(inputs(tmp_path, [base], [changed]))["metrics"]["gain"]["mass"] == 1


def test_disjoint_transitions_and_invalids(tmp_path):
    pairs = [("option_blue", "option_blue"), ("option_blue", "option_red"),
             ("option_red", "option_blue"), ("option_red", "option_red"),
             ("option_red", "option_green"), ("option_blue", None),
             (None, "option_blue"), (None, None)]
    base = [record(str(i), answer=a) for i, (a, _) in enumerate(pairs)]
    changed = [record(str(i), answer=b, text="after") for i, (_, b) in enumerate(pairs)]
    result = workload(inputs(tmp_path, base, changed))
    metrics = result["metrics"]
    names = [name for name in metrics if name.startswith("valid_")] + ["invalid_involved"]
    assert sum(metrics[name]["mass"] for name in names) == 1
    assert metrics["invalid_involved"]["count"] == 3
    assert metrics["stable_answer"]["count"] == 2
    assert metrics["changed_answer"]["count"] == 3
    assert metrics["gain"]["count"] == metrics["loss"]["count"] == 2
    assert metrics["baseline_invalid"]["count"] == metrics["changed_invalid"]["count"] == 2
    assert result["accuracy_difference"] == 0


def test_invalid_no_memory_is_separate_and_empty_condition_is_null(tmp_path):
    paths = inputs(tmp_path, no_memory=[memoryless(record(), None)])
    result = workload(paths)["no_memory_given_context_change"]
    stable = result["stable_answer"]
    assert stable["context_changed_mass"] == 1
    assert stable["invalid_no_memory_mass"] == 1
    assert stable["agreement"]["changed"]["rate"] is None
    assert result["changed_answer"]["agreement"]["changed"]["rate"] is None


def test_context_hash_is_authority_and_shortlist_order_is_separate(tmp_path):
    changed = record()
    changed["shortlist_ids"] = ["message_2", "message_1"]
    changed["context_ids"] = ["another_id"]
    metrics = workload(inputs(tmp_path, changed=[changed]))["metrics"]
    assert metrics["shortlist_order_only_changed"]["mass"] == 1
    assert metrics["shortlist_membership_changed"]["mass"] == 0
    assert metrics["context_ids_changed"]["mass"] == 1
    assert metrics["context_changed"]["mass"] == 0
    changed["shortlist_ids"] = ["message_3"]
    metrics = workload(inputs(tmp_path, changed=[changed]))["metrics"]
    assert metrics["shortlist_order_only_changed"]["mass"] == 0
    assert metrics["shortlist_membership_changed"]["mass"] == 1


def test_explicit_draw_broadcast_and_no_implicit_broadcast(tmp_path):
    base = record()
    del base["draw"]
    no_memory = memoryless(base)
    changed = [record(draw=str(i), text="after") for i in range(3)]
    paths = inputs(tmp_path, [base], changed, [no_memory])
    with pytest.raises(ValueError, match="draw declaration"):
        audit(**paths)
    result = workload(paths, baseline_broadcast=("draw",), no_memory_broadcast=("draw",))
    assert result["paired_records"] == 3
    assert result["metrics"]["stable_answer"]["mass"] == 1
    with pytest.raises(ValueError, match="only broadcast"):
        audit(**paths, baseline_broadcast=("order",))


@pytest.mark.parametrize("defect,match", [
    ("duplicate", "duplicate run key"), ("missing", "missing join"), ("extra", "unused run records"),
    ("key", "inconsistent answer key"), ("bad_semantic", "semantic option ID"),
    ("unavailable", "unavailable responses"), ("bad_hash", "context_text does not match"),
    ("bare_label", "both option_map"), ("wrong_mapping", "answer_label and answer_id disagree"),
    ("duplicate_options", "duplicate IDs"), ("nonempty_no_memory", "no_memory requires"),
    ("unknown_field", "schema"), ("invalid_answer", "null answer_id"),
    ("duplicate_key", "duplicate answer key"), ("extra_key", "exactly the same questions"),
])
def test_reject_bad_inputs(tmp_path, defect, match):
    paths = inputs(tmp_path)
    if defect == "duplicate":
        rewrite(paths["baseline"], lambda rows: rows.append(copy.deepcopy(rows[0])))
    elif defect == "missing":
        rewrite(paths["baseline"], lambda rows: rows[0].update(draw="unknown"))
    elif defect == "extra":
        rewrite(paths["baseline"], lambda rows: rows.append({**rows[0], "draw": "extra"}))
    elif defect == "key":
        rewrite(paths["changed"], lambda rows: rows[0].update(correct_answer_id="option_red"))
    elif defect == "bad_semantic":
        rewrite(paths["changed"], lambda rows: rows[0].update(answer_id="A"))
    elif defect == "unavailable":
        rewrite(paths["changed"], lambda rows: rows[0].update(status="unavailable", answer_id=None))
    elif defect == "bad_hash":
        rewrite(paths["changed"], lambda rows: rows[0].update(context_text="different"))
    elif defect == "bare_label":
        rewrite(paths["changed"], lambda rows: rows[0].update(answer_label="A"))
    elif defect == "wrong_mapping":
        rewrite(paths["changed"], lambda rows: rows[0].update(answer_label="A", option_map={"A": "option_blue", "B": "option_red", "C": "option_green"}))
    elif defect == "duplicate_options":
        rewrite(paths["answer_key"], lambda rows: rows[0].update(option_ids=["option_red", "option_red", "option_blue"]))
    elif defect == "nonempty_no_memory":
        rewrite(paths["no_memory"], lambda rows: rows[0].update(context_ids=["message_1"]))
    elif defect == "unknown_field":
        rewrite(paths["changed"], lambda rows: rows[0].update(choice="A"))
    elif defect == "invalid_answer":
        rewrite(paths["changed"], lambda rows: rows[0].update(status="invalid"))
    elif defect == "duplicate_key":
        rewrite(paths["answer_key"], lambda rows: rows.append(copy.deepcopy(rows[0])))
    elif defect == "extra_key":
        rewrite(paths["answer_key"], lambda rows: rows.append({**rows[0], "question": "unused"}))
    with pytest.raises(ValueError, match=match):
        audit(**paths)


def test_reject_incomplete_grid_even_when_all_runs_share_it(tmp_path):
    base = [record(draw="0", order="0"), record(draw="0", order="1"), record(draw="1", order="0")]
    paths = inputs(tmp_path, base, copy.deepcopy(base))
    with pytest.raises(ValueError, match="incomplete order-by-draw grid"):
        audit(**paths)


def test_reject_duplicate_json_fields(tmp_path):
    paths = inputs(tmp_path)
    paths["baseline"].write_text(paths["baseline"].read_text().replace('"draw": "0"', '"draw": "0", "draw": "1"'))
    with pytest.raises(ValueError, match="duplicate JSON field"):
        audit(**paths)


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_unicode_separators_inside_context_do_not_split_json_records(tmp_path, separator):
    base = [record(str(i), text=f"before{separator}text") for i in range(4)]
    changed = [record(str(i), text=f"after{separator}text") for i in range(4)]
    paths = inputs(tmp_path, base, changed)
    for path in paths.values():
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    result = workload(paths)
    assert result["paired_records"] == 4
    assert result["metrics"]["context_changed"] == {"count": 4, "mass": 1.0}
    assert result["metrics"]["stable_answer"] == {"count": 4, "mass": 1.0}


def test_optional_stages_are_sets_with_complete_availability(tmp_path):
    base, changed = record(), record(text="after")
    base.update(reached_person_ids=["kim", "king"], reference_ids=["ref1"])
    changed.update(reached_person_ids=["king", "kim"], reference_ids=["ref2"])
    paths = inputs(tmp_path, [base], [changed])
    report = audit(**paths).summary()
    assert report["optional_stages"] == {"reached": True, "references": True}
    metrics = report["workloads"]["toy"]["metrics"]
    assert metrics["reached_people_changed"]["mass"] == 0
    assert metrics["reference_ids_changed"]["mass"] == 1
    rewrite(paths["changed"], lambda rows: rows[0].pop("reference_ids"))
    with pytest.raises(ValueError, match="availability"):
        audit(**paths)


def test_workloads_are_never_pooled(tmp_path):
    base = [record(workload="toy"), record(workload="other", answer="option_blue")]
    report = audit(**inputs(tmp_path, base, copy.deepcopy(base))).summary()
    assert report["workloads"]["toy"]["metrics"]["baseline_correct"]["mass"] == 0
    assert report["workloads"]["other"]["metrics"]["baseline_correct"]["mass"] == 1


def test_report_returns_a_copy(tmp_path):
    report = audit(**inputs(tmp_path))
    data = report.summary()
    data["workloads"].clear()
    retained = report.summary()["workloads"]["toy"]
    assert retained["histories"] == 1
    assert retained["paired_records"] == 1


def test_documented_example_api_and_cli_match_saved_output_without_network(tmp_path):
    root = Path(__file__).parents[1]
    example = root / "examples/stage_audit"
    paths = {name: example / f"{name}.jsonl" for name in ("baseline", "changed", "no_memory", "answer_key")}
    expected = json.loads((example / "expected.json").read_text())
    assert audit(**paths).summary() == expected
    guard = tmp_path / "sitecustomize.py"
    guard.write_text("import socket\ndef blocked(*args, **kwargs):\n    raise AssertionError('network access is forbidden')\nsocket.socket = blocked\nsocket.create_connection = blocked\n")
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), str(root / "src")]))
    command = [sys.executable, "-m", "stage_audit"]
    for name, path in paths.items():
        command.extend(["--" + name.replace("_", "-"), str(path)])
    result = subprocess.run(command, capture_output=True, text=True, check=True, env=environment)
    assert json.loads(result.stdout) == expected
    bad = subprocess.run(command + ["--baseline-broadcast-draw"], capture_output=True, text=True, env=environment)
    assert bad.returncode == 2
    assert not bad.stdout
    assert "draw declaration" in bad.stderr
