"""staging 单元测试（档案 v1.1 §6：原子追加、last-wins、resume fail-closed）。"""

from __future__ import annotations

import json

import pytest

from backend.app.application.services.industry_fill.staging import (
    RunMetadata,
    StagingStore,
    new_run_id,
)


def _metadata(**overrides) -> RunMetadata:
    base = dict(
        run_id="run1",
        cli_args={"limit": None},
        input_codes=["000001.SZ", "600519.SH"],
        provider="akshare",
        provider_version="1.18.91",
        mapping_version="sw-l2-to-l1-v1",
        dataset_version="official-2026-07-12",
        database="truthnet_test",
    )
    base.update(overrides)
    return RunMetadata(**base)


def _record(code: str, status: str = "success") -> dict:
    return {
        "wind_code": code,
        "security_number": code.split(".")[0],
        "query_status": status,
        "industry_l1": "食品饮料" if status == "success" else None,
        "industry_l2": "白酒Ⅱ" if status == "success" else None,
        "sw_indu_code": None,
        "provider": "akshare",
        "provider_endpoint": "test",
        "attempts": 1,
        "last_error": None,
        "queried_at": "2026-08-14T00:00:00+00:00",
        "raw_value_hash": "abc",
    }


class TestStagingStore:
    def test_append_and_last_wins(self, tmp_path):
        store = StagingStore(tmp_path / "run1", _metadata())
        store.append(_record("000001.SZ", "error"))
        store.append(_record("000001.SZ", "success"))
        records = StagingStore.load_results(store.results_path)
        assert set(records) == {"000001.SZ"}
        assert records["000001.SZ"]["query_status"] == "success"

    def test_half_line_skipped_on_load(self, tmp_path):
        store = StagingStore(tmp_path / "run1", _metadata())
        store.append(_record("000001.SZ"))
        with store.results_path.open("a", encoding="utf-8") as fh:
            fh.write("{broken json\n")
        records = StagingStore.load_results(store.results_path)
        assert set(records) == {"000001.SZ"}

    def test_resume_compatible(self, tmp_path):
        store = StagingStore(tmp_path / "run1", _metadata())
        store.append(_record("000001.SZ"))
        resumed = store.resume(_metadata())
        assert "000001.SZ" in resumed
        assert resumed["000001.SZ"].industry_l1 == "食品饮料"

    def test_resume_mismatch_fail_closed(self, tmp_path):
        store = StagingStore(tmp_path / "run1", _metadata())
        store.append(_record("000001.SZ"))
        with pytest.raises(RuntimeError, match="resume 拒绝"):
            store.resume(_metadata(dataset_version="other-version"))

    def test_input_hash_diff_rejected(self, tmp_path):
        store = StagingStore(tmp_path / "run1", _metadata())
        store.append(_record("000001.SZ"))
        with pytest.raises(RuntimeError, match="resume 拒绝"):
            store.resume(_metadata(input_codes=["000001.SZ"]))


class TestRunMetadata:
    def test_input_hash_stable_sorted(self):
        a = _metadata(input_codes=["600519.SH", "000001.SZ"])
        b = _metadata(input_codes=["000001.SZ", "600519.SH"])
        assert a.input_hash == b.input_hash

    def test_new_run_id_unique(self):
        assert new_run_id() != new_run_id()

    def test_metadata_json_roundtrip(self, tmp_path):
        meta = _metadata()
        store = StagingStore(tmp_path / "r", meta)
        raw = json.loads((store.run_dir / "metadata.json").read_text(encoding="utf-8"))
        assert raw["database"] == "truthnet_test"
        assert raw["input_codes"] == ["000001.SZ", "600519.SH"]
