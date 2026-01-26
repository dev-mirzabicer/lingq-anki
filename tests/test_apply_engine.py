import uuid

from apply_engine import (
    Checkpoint,
    _checkpoint_path,
    _op_identifier,
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from diff_engine import SyncOperation


def test_load_checkpoint_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile = f"pytest_{uuid.uuid4().hex}"
    assert _checkpoint_path(profile).exists() is False
    assert load_checkpoint(profile) is None


def test_save_then_load_checkpoint_round_trips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile = f"pytest_{uuid.uuid4().hex}"

    checkpoint = Checkpoint(
        run_id="run_123",
        last_processed_index=7,
        completed_ops=["op_a", "op_b"],
    )

    save_checkpoint(profile, checkpoint)

    loaded = load_checkpoint(profile)
    assert loaded == checkpoint


def test_clear_checkpoint_removes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile = f"pytest_{uuid.uuid4().hex}"

    save_checkpoint(profile, Checkpoint(run_id="run_123"))
    path = _checkpoint_path(profile)
    assert path.exists() is True

    clear_checkpoint(profile)
    assert path.exists() is False
    assert load_checkpoint(profile) is None


def test_op_identifier_is_stable_and_ignores_details():
    op1 = SyncOperation(
        op_type="create_anki",
        anki_note_id=123,
        lingq_pk=456,
        term="hello",
        details={"a": 1},
    )

    ident_1 = _op_identifier(op1)
    ident_2 = _op_identifier(op1)
    assert ident_1 == ident_2

    op2 = SyncOperation(
        op_type="create_anki",
        anki_note_id=123,
        lingq_pk=456,
        term="hello",
        details={"b": 2, "a": 1},
    )
    assert _op_identifier(op2) == ident_1

    op3 = SyncOperation(op_type="update_status")
    assert _op_identifier(op3) == "update_status:::"
