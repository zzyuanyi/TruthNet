"""staging/cache 读写（档案 v1.1 §2.2 / §6）。

- 每个待查询代码恰好一条记录（JSONL，按 wind_code last-wins）；
- run 元数据含 run_id、参数摘要、输入清单 hash、provider/mapping/dataset 版本；
- resume 复用必须校验元数据匹配，不匹配 fail-closed；
- 每查询完一个代码即追加落盘，不等待全量结束。
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.application.services.industry_fill.constants import QueryStatus
from app.application.services.industry_fill.provider import ProviderResult


def _stable_digest(obj: object) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class RunMetadata:
    run_id: str
    cli_args: dict
    input_codes: list[str]
    provider: str
    provider_version: str
    mapping_version: str
    dataset_version: str
    database: str
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    @property
    def input_hash(self) -> str:
        return _stable_digest(sorted(self.input_codes))

    def to_dict(self) -> dict:
        return asdict(self)

    def compatible_with(self, other: "RunMetadata") -> bool:
        """复用条件（档案 §4/§6.1）：provider、口径版本、数据库与输入清单一致。"""
        return (
            self.provider == other.provider
            and self.provider_version == other.provider_version
            and self.mapping_version == other.mapping_version
            and self.dataset_version == other.dataset_version
            and self.database == other.database
            and self.input_hash == other.input_hash
        )


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"industry_fill_{ts}_{uuid.uuid4().hex[:8]}"


class StagingStore:
    """run 目录下的 staging 持久化：metadata.json + results.jsonl。"""

    def __init__(self, run_dir: Path, metadata: RunMetadata | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.metadata = metadata
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()  # 并发 provider 逐码落盘时保护追加
        if metadata is not None:
            self.write_metadata(metadata)

    def write_metadata(self, metadata: RunMetadata) -> None:
        self.metadata = metadata
        (self.run_dir / "metadata.json").write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def results_path(self) -> Path:
        return self.run_dir / "results.jsonl"

    # ── 写入 ───────────────────────────────────────────────
    def append(self, record: dict) -> None:
        """追加一条记录（每码一条，last-wins）；线程安全。"""
        with self._lock:
            self._records[record["wind_code"]] = record
            with self.results_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()

    # ── 读取 / resume ──────────────────────────────────────
    @staticmethod
    def load_results(path: Path) -> dict[str, dict]:
        """读取既有 results.jsonl；重复 wind_code 取最后一条。"""
        out: dict[str, dict] = {}
        if not Path(path).exists():
            return out
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # 半行保护：跳过损坏行（档案 §6.2 原子追加设计兜底）
            out[str(record["wind_code"])] = record
        return out

    def resume(self, metadata: RunMetadata) -> dict[str, ProviderResult]:
        """读取历史 staging；元数据不匹配 fail-closed（档案 §4）。"""
        path = self.run_dir / "metadata.json"
        if not path.exists():
            return {}
        prev = RunMetadata(**json.loads(path.read_text(encoding="utf-8")))
        if not prev.compatible_with(metadata):
            raise RuntimeError(
                "resume 拒绝：历史 staging 元数据与当前运行不匹配"
                f"（provider={prev.provider}@{prev.provider_version},"
                f" mapping={prev.mapping_version}, dataset={prev.dataset_version},"
                f" database={prev.database}, input_hash={prev.input_hash[:12]}…"
                f" vs 当前 provider={metadata.provider}@{metadata.provider_version},"
                f" mapping={metadata.mapping_version}, dataset={metadata.dataset_version},"
                f" database={metadata.database}, input_hash={metadata.input_hash[:12]}…）"
            )
        records = self.load_results(self.results_path)
        return {
            code: ProviderResult(
                wind_code=rec["wind_code"],
                security_number=rec.get("security_number", ""),
                query_status=QueryStatus(rec["query_status"]),
                industry_l1=rec.get("industry_l1"),
                industry_l2=rec.get("industry_l2"),
                sw_indu_code=rec.get("sw_indu_code"),
                provider=rec.get("provider", ""),
                provider_endpoint=rec.get("provider_endpoint", ""),
                attempts=int(rec.get("attempts", 0)),
                last_error=rec.get("last_error"),
                queried_at=rec.get("queried_at", ""),
                raw_value_hash=rec.get("raw_value_hash", ""),
            )
            for code, rec in records.items()
        }

    def records(self) -> dict[str, dict]:
        return dict(self._records)
