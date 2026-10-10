"""Tests for ``engine/hash_chain.py`` — the cross-run SHA-256 audit chain.

The invariant under test: appending is linkable, and ANY tamper with a
record's payload or its ``prev_hash`` breaks :meth:`HashChain.verify`.
"""

import json

from engine.hash_chain import GENESIS_HASH, HashChain, sha256_hex


def test_empty_chain_is_valid(tmp_path):
    chain = HashChain(str(tmp_path / "chain.json"))
    assert chain.length == 0
    assert chain.tip == GENESIS_HASH
    assert chain.verify() == (True, 0)


def test_append_links_records(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    first = HashChain(path).append({"event": "task_complete", "task_id": "0.1", "run": 1})
    assert first["prev_hash"] == GENESIS_HASH
    assert first["seq"] == 0
    assert len(first["hash"]) == 64
    assert first["event_type"] == "task_complete"

    second = HashChain(path).append({"event": "sync", "table": "state"})
    assert second["prev_hash"] == first["hash"]
    assert second["seq"] == 1

    chain = HashChain(path)
    assert chain.length == 2
    assert chain.tip == second["hash"]
    assert chain.verify() == (True, 2)


def test_tampered_payload_is_detected(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "task_complete", "task_id": "0.1"})
    chain.append({"event": "task_complete", "task_id": "0.2"})
    data = json.loads(file.read_text(encoding="utf-8"))
    data["chain"][0]["payload"]["task_id"] = "99.9"
    file.write_text(json.dumps(data), encoding="utf-8")
    ok, index = HashChain(path).verify()
    assert not ok
    assert index == 0


def test_tampered_prev_hash_is_detected(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "a"})
    chain.append({"event": "b"})
    data = json.loads(file.read_text(encoding="utf-8"))
    data["chain"][1]["prev_hash"] = "f" * 64
    file.write_text(json.dumps(data), encoding="utf-8")
    ok, index = HashChain(path).verify()
    assert not ok
    assert index == 1


def test_tampered_hash_is_detected(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "a"})
    chain.append({"event": "b"})
    data = json.loads(file.read_text(encoding="utf-8"))
    # Forging record 0's own stored hash breaks its content-hash check.
    data["chain"][0]["hash"] = "0" * 64
    file.write_text(json.dumps(data), encoding="utf-8")
    ok, index = HashChain(path).verify()
    assert not ok
    assert index == 0


def test_tampered_parent_hash_is_detected(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "a"})
    chain.append({"event": "b"})
    data = json.loads(file.read_text(encoding="utf-8"))
    # Editing record 1's content changes its hash, so its successor link
    # check fails first at index 1.
    data["chain"][1]["payload"]["event"] = "forged"
    file.write_text(json.dumps(data), encoding="utf-8")
    ok, index = HashChain(path).verify()
    assert not ok
    assert index == 1


def test_omitted_record_breaks_the_chain(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "a"})
    chain.append({"event": "b"})
    chain.append({"event": "c"})
    data = json.loads(file.read_text(encoding="utf-8"))
    del data["chain"][1]
    file.write_text(json.dumps(data), encoding="utf-8")
    ok, index = HashChain(path).verify()
    assert not ok
    assert index == 1


def test_verify_is_read_only(tmp_path):
    file = tmp_path / "chain.json"
    path = str(file)
    chain = HashChain(path)
    chain.append({"event": "a"})
    before = json.loads(file.read_text(encoding="utf-8"))
    assert chain.verify() == (True, 1)
    after = json.loads(file.read_text(encoding="utf-8"))
    assert before == after


def test_sha256_hex_is_stable():
    assert sha256_hex(b"vantia") == sha256_hex(b"vantia")
    assert sha256_hex(b"vantia") != sha256_hex(b"vantie")
    assert len(sha256_hex(b"")) == 64


def test_missing_chain_file_is_empty(tmp_path):
    assert HashChain(str(tmp_path / "missing.json")).length == 0


# ── task 4.3: cross-run audit surface ────────────────────────────────────


def test_runs_recorded_in_two_sessions_stay_chained(tmp_path):
    path = str(tmp_path / "hash_chain.json")

    chain_a = HashChain(path)
    chain_a.record_run(11, tasks=["3.6", "3.7"], notes="Phase 3 closed 7/7", usd=0.0)
    chain_a.record_run(12, tasks=["4.1"], notes="domain verification", usd=0.0)

    # a brand-new process/session over the SAME file continues the chain
    chain_b = HashChain(path)
    assert chain_b.length == 2
    assert chain_b.verify() == (True, 2)
    events = [rec["payload"]["event"] for rec in chain_b.records]
    assert events == ["run_finished", "run_finished"]
    assert [rec["payload"]["run"] for rec in chain_b.records] == [11, 12]


def test_audit_reports_a_tamper_across_sessions(tmp_path):
    path = str(tmp_path / "hash_chain.json")
    chain = HashChain(path)
    chain.record_run(11, tasks=["3.7"])
    chain.record_run(12, tasks=["4.1"])

    report = HashChain(path).audit()
    assert report["ok"] is True
    assert report["length"] == 2
    assert report["first_bad_seq"] is None
    assert report["tip"] == chain.tip

    chain._records[0]["payload"]["run"] = 99  # forged in a later session
    chain._save()
    report = HashChain(path).audit()
    assert report["ok"] is False
    assert report["first_bad_seq"] == 0


def test_append_emits_structured_log_with_run_id_and_hash(tmp_path, capsys):
    """Task 6.1: stdout carries the append's SHA-256 pair under the run id."""
    from engine.logging_config import configure_logging

    configure_logging(run_id="run61-log-test")
    chain = HashChain(str(tmp_path / "chain.json"))
    record = chain.append({"event": "sync", "table": "state"})

    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()][-1]
    entry = json.loads(line)
    assert entry["run_id"] == "run61-log-test"
    assert entry["msg"] == "hash_chain append"
    assert entry["data"]["sha256"] == record["hash"] == chain.tip
    assert entry["data"]["prev_hash"] == record["prev_hash"]
    assert len(entry["data"]["sha256"]) == 64
    assert entry["data"]["seq"] == 0
