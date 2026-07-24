#!/usr/bin/env python
"""TruthNet — ChromaDB 研报分块导入脚本 (V12 baseline)

从 processed 目录读取研报 JSONL，分块后写入 ChromaDB collection。
支持幂等 upsert、流式批量处理、嵌入模型缓存、离线降级。

使用方式:
    python scripts/task3_chromadb_import.py --dry-run
    python scripts/task3_chromadb_import.py
    python scripts/task3_chromadb_import.py --verify-only
    python scripts/task3_chromadb_import.py --rebuild-collection
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# 模块级：仅常量、类型、纯函数定义。无任何副作用。
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---- 分块常量 ----
DEFAULT_CHUNK_SIZE: int = 500  # 每块约 500 字符（中文语义块）
DEFAULT_CHUNK_OVERLAP: int = 100  # 块间重叠 100 字符
CHUNKER_VERSION: str = "v1.0.0"

# 研报 JSONL 每行的必填字段
REQUIRED_FIELDS: list[str] = [
    "report_id",
    "wind_code",
    "sec_name",
    "org_name",
    "title",
    "publish_date",
    "abstract",
]


# ===================================================================
# 纯函数：配置、路径、文本处理
# ===================================================================


def resolve_repo_root() -> Path:
    """返回仓库根目录的绝对路径。"""
    return Path(__file__).resolve().parent.parent


def load_env_config(repo_root: Path) -> dict[str, str]:
    """从 .env 加载配置，返回 dict。"""
    config: dict[str, str] = {}
    try:
        from dotenv import load_dotenv

        env_file = repo_root / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
        else:
            logger.info("未找到 .env 文件，使用默认值")
    except ImportError:
        logger.warning("python-dotenv 未安装，无法加载 .env，使用默认值")

    env_map = {
        "DATA_ROOT": "DATA_ROOT",
        "PROCESSED_DATA_DIR": "PROCESSED_DATA_DIR",
        "CHROMA_PERSIST_DIR": "CHROMA_PERSIST_DIR",
        "EMBEDDING_MODEL": "EMBEDDING_MODEL",
        "EMBEDDING_CACHE_DIR": "EMBEDDING_CACHE_DIR",
        "DATASET_VERSION": "DATASET_VERSION",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key, "")
        if val:
            config[cfg_key] = val

    return config


def resolve_path(raw: str | None, fallback: str, repo_root: Path) -> Path:
    """将字符串路径转为相对于仓库根的绝对路径。"""
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = repo_root / p
        return p.resolve()
    p = repo_root / fallback
    return p.resolve()


# ===================================================================
# 文本分块
# ===================================================================


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """将文本切分为有重叠的分块。

    返回 list[dict]，每个 dict 包含 text、char_start、char_end。
    """
    if not text or not text.strip():
        return []

    cleaned = text.strip()
    total_len = len(cleaned)
    chunks: list[dict[str, Any]] = []

    if total_len <= chunk_size:
        chunks.append({"text": cleaned, "char_start": 0, "char_end": total_len})
        return chunks

    step = chunk_size - overlap
    if step <= 0:
        raise ValueError(
            f"chunk_size ({chunk_size}) must be greater than overlap ({overlap})"
        )

    pos = 0
    while pos < total_len:
        end = min(pos + chunk_size, total_len)
        chunk_text_val = cleaned[pos:end]
        chunks.append({"text": chunk_text_val, "char_start": pos, "char_end": end})
        if end >= total_len:
            break
        pos += step

    return chunks


# ===================================================================
# 块 ID 生成（确定性）
# ===================================================================


def make_chunk_id(report_id: str, chunk_index: int, content_hash: str) -> str:
    """生成确定性块 ID。

    组成：report_id + chunk_index + content_hash → SHA-256 前 32 位 hex。
    相同输入始终生成相同 ID，支持幂等 upsert。
    """
    raw = f"{report_id}::{chunk_index}::{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def content_sha256(text: str) -> str:
    """文本内容的 SHA-256 哈希（前 16 位 hex）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ===================================================================
# JSONL 流式读取
# ===================================================================


def iter_reports(jsonl_dir: Path) -> Iterator[dict[str, Any]]:
    """流式迭代 processed 目录下的所有 .jsonl 文件中的研报记录。

    每个 JSONL 文件每行为一个 JSON 对象。
    读取一条 yield 一条，不将整个文件加载到内存。
    """
    if not jsonl_dir.exists():
        logger.error(f"processed 目录不存在: {jsonl_dir}")
        return

    jsonl_files = sorted(jsonl_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.warning(f"processed 目录中没有 .jsonl 文件: {jsonl_dir}")
        return

    logger.info(f"找到 {len(jsonl_files)} 个 JSONL 文件")

    total_lines = 0
    skipped = 0

    for jf in jsonl_files:
        logger.info(f"  读取: {jf.name}")
        with open(jf, "r", encoding="utf-8", newline="\n") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(f"  {jf.name}:{line_no} JSON 解析失败: {exc}")
                    skipped += 1
                    continue

                # 校验必填字段
                missing = [
                    f for f in REQUIRED_FIELDS if f not in record or record[f] is None
                ]
                if missing:
                    logger.warning(
                        f"  {jf.name}:{line_no} report_id="
                        f"{record.get('report_id', '?')} "
                        f"缺少字段: {missing}"
                    )
                    skipped += 1
                    continue

                total_lines += 1
                yield record

    logger.info(f"共读取 {total_lines} 条记录，跳过 {skipped} 条")


# ===================================================================
# JSONL → Chunks 生成器（流式）
# ===================================================================


def generate_chunks(
    jsonl_dir: Path,
    dataset_version: str,
    embedding_model: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Iterator[dict[str, Any]]:
    """生成所有分块记录（id、content、metadata）。

    流式操作：读一条记录 → 分块 → yield，不一次性加载全部数据。
    """
    for report in iter_reports(jsonl_dir):
        abstract = report.get("abstract", "") or ""
        if not abstract.strip():
            logger.debug(f"  report_id={report['report_id']} abstract 为空，跳过")
            continue

        chunks = chunk_text(abstract, chunk_size=chunk_size, overlap=overlap)

        for idx, chunk in enumerate(chunks):
            chunk_text_val: str = chunk["text"]
            text_hash = content_sha256(chunk_text_val)
            chunk_id = make_chunk_id(
                report_id=report["report_id"],
                chunk_index=idx,
                content_hash=text_hash,
            )

            metadata = {
                "report_id": report["report_id"],
                "wind_code": report["wind_code"],
                "sec_name": report.get("sec_name", ""),
                "org_name": report.get("org_name", ""),
                "title": report.get("title", ""),
                "publish_date": str(report.get("publish_date", "")),
                "rating_change": str(report.get("rating_change", "")),
                "chunk_index": idx,
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"],
                "content_hash": text_hash,
                "source_record_id": report.get("report_id", ""),
                "dataset_version": dataset_version,
                "embedding_model": embedding_model,
                "embedding_version": CHUNKER_VERSION,
                "language": "zh",
                "chunker_version": CHUNKER_VERSION,
            }

            yield {
                "id": chunk_id,
                "content": chunk_text_val,
                "metadata": metadata,
            }


# ===================================================================
# 嵌入模型（懒加载 + 缓存）
# ===================================================================

_embedding_model = None


def _get_embedding_model(model_name: str, cache_dir: str | None = None):
    """懒加载 sentence-transformers 模型，支持缓存目录。

    首次调用时加载模型并缓存在模块私有变量中。
    返回模型对象，或 None（模型不可用，fail-closed）。
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error(
            "sentence-transformers 未安装。请运行: pip install sentence-transformers"
        )
        return None

    try:
        logger.info(f"加载嵌入模型: {model_name}")
        kwargs: dict[str, Any] = {}
        if cache_dir:
            kwargs["cache_folder"] = cache_dir
            logger.info(f"  模型缓存目录: {cache_dir}")

        _embedding_model = SentenceTransformer(model_name, **kwargs)
        dim = _embedding_model.get_sentence_embedding_dimension()
        logger.info(f"  模型加载成功，维度={dim}")
        return _embedding_model
    except Exception as exc:
        logger.error(f"加载嵌入模型失败: {exc}")
        return None


def embed_batch(
    model, texts: list[str], sub_batch: int = 32
) -> list[list[float]] | None:
    """对一批文本进行嵌入向量计算。

    Args:
        model: SentenceTransformer 实例。
        texts: 待嵌入的文本列表。
        sub_batch: 每次 encode 的微批次大小。

    Returns:
        list[list[float]] 或 None（失败）。
    """
    if model is None:
        return None
    try:
        embeddings = model.encode(
            texts,
            batch_size=sub_batch,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()
    except Exception as exc:
        logger.error(f"嵌入计算失败: {exc}")
        return None


# ===================================================================
# ChromaDB 客户端 & Collection
# ===================================================================


def get_chroma_client(persist_dir: str):
    """创建 ChromaDB PersistentClient。返回 None 表示不可用（fail-closed）。"""
    try:
        import chromadb
    except ImportError:
        logger.error("chromadb 未安装。请运行: pip install chromadb")
        return None

    try:
        persist_path = Path(persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_path))
        logger.info(f"ChromaDB 客户端已创建, persist_dir={persist_path}")
        return client
    except Exception as exc:
        logger.error(f"创建 ChromaDB 客户端失败: {exc}")
        return None


def get_or_create_collection(client, collection_name: str, rebuild: bool = False):
    """获取或创建 collection。

    Args:
        client: ChromaDB 客户端。
        collection_name: collection 名称。
        rebuild: 如果为 True，先删除再创建。

    Returns:
        Collection 对象或 None。
    """
    try:
        if rebuild:
            try:
                client.delete_collection(collection_name)
                logger.info(f"已删除旧 collection: {collection_name}")
            except Exception:
                logger.info(f"collection 不存在，无需删除: {collection_name}")

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection 就绪: {collection_name}")
        return collection
    except Exception as exc:
        logger.error(f"获取/创建 collection 失败: {exc}")
        return None


# ===================================================================
# 批量写入辅助
# ===================================================================


class BatchWriter:
    """累积 chunk 并批量写入 ChromaDB，支持 dry-run 和 fail-closed。"""

    def __init__(
        self,
        collection,
        batch_size: int,
        dry_run: bool = False,
        model=None,
    ):
        self.collection = collection
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.model = model
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._texts: list[str] = []
        self._items: list[dict[str, Any]] = []
        self.total_written = 0

    def add(self, item: dict[str, Any]) -> None:
        """添加一个 chunk 到当前批次。"""
        self._texts.append(item["content"])
        self._items.append(item)

        if len(self._texts) >= self.batch_size:
            self._flush()

    def finish(self) -> int:
        """刷新最后一批并返回总写入数。"""
        if self._texts:
            self._flush()
        return self.total_written

    def _flush(self) -> None:
        """将当前积累的 chunks 嵌入并写入。"""
        if not self._texts:
            return

        n = len(self._texts)

        # 嵌入计算
        embeddings: list[list[float]] | None = None
        if not self.dry_run and self.model is not None:
            embeddings = embed_batch(
                self.model, list(self._texts), sub_batch=min(32, self.batch_size)
            )

        # 组装
        ids_batch: list[str] = []
        docs_batch: list[str] = []
        metas_batch: list[dict[str, Any]] = []
        embs_batch: list[list[float]] = []

        for i, item in enumerate(self._items):
            ids_batch.append(item["id"])
            docs_batch.append(item["content"])
            metas_batch.append(item["metadata"])
            if embeddings is not None and i < len(embeddings):
                embs_batch.append(embeddings[i])

        # 写入
        if self.dry_run:
            logger.info(
                f"  [DRY-RUN] 将写入 {n} 条 "
                f"(chunk_id sample: {ids_batch[0][:16]}...)"
            )
        else:
            try:
                kwargs: dict[str, Any] = {
                    "ids": ids_batch,
                    "documents": docs_batch,
                    "metadatas": metas_batch,
                }
                if embs_batch:
                    kwargs["embeddings"] = embs_batch

                self.collection.upsert(**kwargs)
                self.total_written += n
                logger.debug(f"  写入批次: {n} 条")
            except Exception as exc:
                logger.error(f"  批次写入失败: {exc}")

        # 清空
        self._texts.clear()
        self._items.clear()


# ===================================================================
# 主导入流程
# ===================================================================


def run_import(
    jsonl_dir: Path,
    persist_dir: str,
    collection_name: str,
    embedding_model_name: str,
    embedding_cache_dir: str | None,
    dataset_version: str,
    batch_size: int = 100,
    dry_run: bool = False,
    rebuild: bool = False,
    resume: bool = False,
) -> int:
    """执行导入，返回成功写入的 chunk 总数（-1 表示失败）。"""
    start_time = time.monotonic()

    # ---- 加载嵌入模型 ----
    model = _get_embedding_model(embedding_model_name, cache_dir=embedding_cache_dir)
    if model is None:
        if dry_run:
            logger.warning("嵌入模型不可用 [DRY-RUN 继续]")
        else:
            logger.error("嵌入模型不可用，导入中止（fail-closed）")
            return -1

    # ---- ChromaDB 客户端 ----
    client = get_chroma_client(persist_dir)
    if client is None:
        logger.error("ChromaDB 客户端不可用，导入中止（fail-closed）")
        return -1

    # ---- Collection ----
    collection = get_or_create_collection(client, collection_name, rebuild=rebuild)
    if collection is None:
        logger.error("无法获取 collection，导入中止")
        return -1

    # ---- 显示已存在 count ----
    try:
        existing_count = collection.count()
        logger.info(f"Collection 当前文档数: {existing_count}")
    except Exception:
        existing_count = 0

    if resume:
        logger.info(
            f"--resume 模式：将从现有 {existing_count} 条基础上继续"
            f"（upsert 自动去重）"
        )

    # ---- 流式生成 chunks ----
    chunk_generator = generate_chunks(
        jsonl_dir=jsonl_dir,
        dataset_version=dataset_version,
        embedding_model=embedding_model_name,
    )

    # ---- 批量写入 ----
    writer = BatchWriter(
        collection=collection,
        batch_size=batch_size,
        dry_run=dry_run,
        model=model,
    )

    last_log_count = 0
    for chunk_item in chunk_generator:
        writer.add(chunk_item)

        # 进度日志
        current = (
            writer.total_written
            if not dry_run
            else writer.total_written + len(writer._items)
        )
        if current - last_log_count >= batch_size * 10:
            elapsed = time.monotonic() - start_time
            logger.info(f"  进度: ~{current} chunks, {elapsed:.1f}s")
            last_log_count = current

    total_written = writer.finish()
    elapsed = time.monotonic() - start_time

    if dry_run:
        logger.info(f"[DRY-RUN] 共 {total_written} chunks 将被写入 (未实际写入)")
    else:
        final_count = collection.count()
        logger.info(
            f"导入完成: 本次写入 {total_written} chunks, "
            f"collection 总数={final_count}, "
            f"耗时={elapsed:.1f}s"
        )

    return total_written


# ===================================================================
# 验证流程
# ===================================================================


def run_verify(
    persist_dir: str,
    collection_name: str,
    embedding_model_name: str,
    embedding_cache_dir: str | None,
) -> bool:
    """验证 ChromaDB collection 的完整性和可检索性。

    执行步骤：
    1. 基本语义检索
    2. 元数据过滤测试（wind_code=600518.SH）
    3. 重启客户端再读取（验证持久化）
    4. 嵌入模型自检
    """
    import chromadb

    sep = "=" * 60

    logger.info(sep)
    logger.info("验证 ChromaDB Collection")
    logger.info(sep)

    # ---- 1. 连接并获取 collection ----
    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_collection(collection_name)
        count = collection.count()
        logger.info(f"  Collection '{collection_name}' 文档数: {count}")

        if count == 0:
            logger.warning("  Collection 为空，跳过验证")
            return False
    except Exception as exc:
        logger.error(f"  连接失败: {exc}")
        return False

    # ---- 2. 基本语义检索 ----
    logger.info("--- 测试 1: 基本语义检索 ---")
    try:
        results = collection.query(
            query_texts=["康美药业财务造假"],
            n_results=3,
        )
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        logger.info(f"  检索到 {len(ids)} 条结果")
        for i, (cid, dist) in enumerate(zip(ids, distances)):
            logger.info(f"    [{i}] id={cid}  distance={dist:.4f}")
    except Exception as exc:
        logger.error(f"  基本检索失败: {exc}")
        return False

    # ---- 3. 元数据过滤：wind_code=600518.SH ----
    logger.info("--- 测试 2: 元数据过滤 (wind_code=600518.SH) ---")
    try:
        results_filtered = collection.query(
            query_texts=["财务风险"],
            n_results=5,
            where={"wind_code": "600518.SH"},
        )
        f_ids = results_filtered.get("ids", [[]])[0]
        logger.info(f"  过滤后检索到 {len(f_ids)} 条结果")

        if f_ids:
            metadatas = results_filtered.get("metadatas", [[]])[0]
            for i, (cid, meta) in enumerate(zip(f_ids, metadatas)):
                wc = meta.get("wind_code", "?") if meta else "?"
                logger.info(f"    [{i}] id={cid}  wind_code={wc}")
        else:
            logger.info("  无匹配结果（可能数据中不包含 wind_code=600518.SH）")
    except Exception as exc:
        logger.error(f"  元数据过滤失败: {exc}")
        return False

    # ---- 4. 重启客户端再读取 ----
    logger.info("--- 测试 3: 重启客户端再读取 ---")
    try:
        del client
        client2 = chromadb.PersistentClient(path=persist_dir)
        collection2 = client2.get_collection(collection_name)
        count2 = collection2.count()
        logger.info(f"  重启后文档数: {count2} (预期: {count})")

        if count2 != count:
            logger.error(f"  文档数不一致! 预期 {count}, 实际 {count2}")
            return False

        results3 = collection2.query(
            query_texts=["上市公司财务分析"],
            n_results=2,
        )
        ids3 = results3.get("ids", [[]])[0]
        logger.info(f"  重启后检索: {len(ids3)} 条结果")
    except Exception as exc:
        logger.error(f"  重启客户端验证失败: {exc}")
        return False

    # ---- 5. 嵌入模型自检 ----
    logger.info("--- 测试 4: 嵌入模型自检 ---")
    model = _get_embedding_model(embedding_model_name, cache_dir=embedding_cache_dir)
    if model is None:
        logger.warning("  嵌入模型不可用，但 ChromaDB 数据已验证")
    else:
        logger.info("  嵌入模型可用")

    logger.info(sep)
    logger.info("验证通过")
    logger.info(sep)
    return True


# ===================================================================
# main — 所有副作用集中在此处
# ===================================================================


def _setup_encoding() -> None:
    """修复 Windows 终端编码。"""
    if sys.platform == "win32":
        # stdout
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        # stdin — 用于 --rebuild-collection 交互确认
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")


def _setup_logging() -> None:
    """配置全局日志格式。仅在 main() 中调用一次。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _confirm_rebuild(collection_name: str, persist_dir: str) -> bool:
    """打印危险操作警告并要求用户输入 'yes' 确认。"""
    logger.warning("")
    logger.warning("!" * 60)
    logger.warning("  危险操作: --rebuild-collection")
    logger.warning(f"  将删除 ChromaDB collection '{collection_name}' 中的所有数据!")
    logger.warning(f"  持久化路径: {persist_dir}")
    logger.warning("!" * 60)
    logger.warning("")

    try:
        confirm = input("  确认删除并重建? 输入 'yes' 继续: ").strip()
    except EOFError:
        logger.error("无法读取输入，操作取消")
        return False

    if confirm.lower() != "yes":
        logger.info("操作已取消")
        return False

    logger.info("确认通过，将删除旧 collection 并重建")
    return True


def main() -> int:
    """主入口 — 所有副作用集中在此函数中。"""
    _setup_encoding()
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="TruthNet — ChromaDB 研报分块导入 (V12 baseline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            环境变量（.env 或系统环境）:
              DATA_ROOT            原始数据根目录 (默认: data/raw)
              PROCESSED_DATA_DIR   JSONL 处理数据目录 (默认: data/processed)
              CHROMA_PERSIST_DIR   ChromaDB 持久化目录 (默认: data/chroma_db)
              EMBEDDING_MODEL      嵌入模型 (默认: BAAI/bge-small-zh-v1.5)
              EMBEDDING_CACHE_DIR  模型缓存目录 (默认: data/model_cache)
              DATASET_VERSION      数据集版本 (默认: v1.0.0)

            示例:
              python scripts/task3_chromadb_import.py --dry-run
              python scripts/task3_chromadb_import.py
              python scripts/task3_chromadb_import.py --verify-only
              python scripts/task3_chromadb_import.py --rebuild-collection
        """),
    )

    # ---- 路径参数 ----
    parser.add_argument(
        "--data-root",
        default=None,
        help="原始数据根目录（默认: 环境变量 DATA_ROOT 或 data/raw）",
    )
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="JSONL 处理数据目录（默认: 环境变量 PROCESSED_DATA_DIR 或 data/processed）",
    )
    parser.add_argument(
        "--chroma-persist-dir",
        default=None,
        help="ChromaDB 持久化目录（默认: 环境变量 CHROMA_PERSIST_DIR 或 data/chroma_db）",
    )

    # ---- 模型参数 ----
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="嵌入模型名称（默认: 环境变量 EMBEDDING_MODEL 或 BAAI/bge-small-zh-v1.5）",
    )
    parser.add_argument(
        "--embedding-cache-dir",
        default=None,
        help="模型缓存目录（默认: 环境变量 EMBEDDING_CACHE_DIR 或 data/model_cache）",
    )

    # ---- 操作参数 ----
    parser.add_argument(
        "--collection-name",
        default=None,
        help="ChromaDB collection 名称（默认: research_report_chunks）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="每批嵌入计算的 chunk 数量（默认: 100）",
    )
    parser.add_argument(
        "--dataset-version",
        default=None,
        help="数据集版本标签（默认: 环境变量 DATASET_VERSION 或 v1.0.0）",
    )

    # ---- 模式开关 ----
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式：读取数据、生成 chunk，但不写入 ChromaDB",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="续传模式：在现有数据基础上继续导入（upsert 自动去重）",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅验证：只运行验证步骤，不导入数据",
    )
    parser.add_argument(
        "--rebuild-collection",
        action="store_true",
        help="删除旧 collection 后重新导入 [危险操作，需输入 'yes' 确认]",
    )

    args = parser.parse_args()

    # ===== 加载配置 =====
    repo_root = resolve_repo_root()
    env_config = load_env_config(repo_root)

    # ===== 解析最终值：CLI 参数 > 环境变量 > 硬编码默认值 =====
    processed_dir = resolve_path(
        args.processed_dir,
        env_config.get("PROCESSED_DATA_DIR", "data/processed"),
        repo_root,
    )
    chroma_persist_dir = resolve_path(
        args.chroma_persist_dir,
        env_config.get("CHROMA_PERSIST_DIR", "data/chroma_db"),
        repo_root,
    )
    embedding_model = args.embedding_model or env_config.get(
        "EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    embedding_cache_dir_raw = args.embedding_cache_dir or env_config.get(
        "EMBEDDING_CACHE_DIR", "data/model_cache"
    )
    embedding_cache_dir = str(
        resolve_path(embedding_cache_dir_raw, "data/model_cache", repo_root)
    )
    collection_name = args.collection_name or "research_report_chunks"
    batch_size = args.batch_size if args.batch_size is not None else 100
    dataset_version = args.dataset_version or env_config.get(
        "DATASET_VERSION", "v1.0.0"
    )

    # 注意：--data-root 在本次导入中不直接使用（使用 --processed-dir），
    # 保留该参数用于 future 扩展（如从 raw 重新处理）。
    _data_root = resolve_path(
        args.data_root,
        env_config.get("DATA_ROOT", "data/raw"),
        repo_root,
    )

    # ===== 打印配置 =====
    sep = "=" * 60
    logger.info(sep)
    logger.info("TruthNet ChromaDB 研报导入 — V12 Baseline")
    logger.info(sep)
    logger.info(f"  数据源 (processed):  {processed_dir}")
    logger.info(f"  ChromaDB 持久化:     {chroma_persist_dir}")
    logger.info(f"  Collection:          {collection_name}")
    logger.info(f"  嵌入模型:            {embedding_model}")
    logger.info(f"  模型缓存:            {embedding_cache_dir}")
    logger.info(f"  批次大小:            {batch_size}")
    logger.info(f"  数据集版本:          {dataset_version}")
    logger.info(f"  Dry-run:             {args.dry_run}")
    logger.info(f"  Resume:              {args.resume}")
    logger.info(f"  Verify-only:         {args.verify_only}")
    logger.info(f"  Rebuild:             {args.rebuild_collection}")
    logger.info(sep)

    # ===== --rebuild-collection 危险操作确认 =====
    rebuild = args.rebuild_collection
    if rebuild:
        if not _confirm_rebuild(collection_name, str(chroma_persist_dir)):
            return 0

    # ===== --verify-only 仅验证模式 =====
    if args.verify_only:
        ok = run_verify(
            persist_dir=str(chroma_persist_dir),
            collection_name=collection_name,
            embedding_model_name=embedding_model,
            embedding_cache_dir=embedding_cache_dir,
        )
        return 0 if ok else 1

    # ===== 执行导入 =====
    result = run_import(
        jsonl_dir=processed_dir,
        persist_dir=str(chroma_persist_dir),
        collection_name=collection_name,
        embedding_model_name=embedding_model,
        embedding_cache_dir=embedding_cache_dir,
        dataset_version=dataset_version,
        batch_size=batch_size,
        dry_run=args.dry_run,
        rebuild=rebuild,
        resume=args.resume,
    )

    if result < 0:
        logger.error("导入失败")
        return 1

    if args.dry_run:
        logger.info("Dry-run 完成（未写入数据）")
        return 0

    # ===== 导入后自动验证 =====
    logger.info("")
    ok = run_verify(
        persist_dir=str(chroma_persist_dir),
        collection_name=collection_name,
        embedding_model_name=embedding_model,
        embedding_cache_dir=embedding_cache_dir,
    )

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
