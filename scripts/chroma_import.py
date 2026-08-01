#!/usr/bin/env python
"""Step 2: Import pre-computed embeddings into ChromaDB (NO sentence-transformers).

Reads data/processed/embeddings.npy + chunks_meta.json → upsert to ChromaDB.
持久化目录和集合名与 vector_store.py 统一。
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.core.config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

COLLECTION_NAME = "research_report_chunks"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", default="data/processed")
    p.add_argument("--chroma-dir", default=None, help="默认读取 CHROMA_PERSIST_DIR")
    p.add_argument("--collection", default="research_report_chunks")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument(
        "--rebuild", action="store_true", help="Delete and recreate collection"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()

    inp = Path(args.input_dir)
    emb_file = inp / "embeddings.npy"
    meta_file = inp / "chunks_meta.json"

    if not emb_file.exists() or not meta_file.exists():
        log.error(
            "Missing embeddings.npy or chunks_meta.json in %s. Run chroma_embed.py first.",
            inp,
        )
        return 1

    # Load
    embeddings = np.load(str(emb_file))
    with open(meta_file, encoding="utf-8") as f:
        metas = json.load(f)
    log.info("Loaded %d embeddings, %d metadata entries", len(embeddings), len(metas))

    if args.verify:
        log.info("Verification only — no writes")
        q_emb = embeddings[0:1]
        log.info(
            "Sample embedding shape: %s, norm: %.4f",
            q_emb.shape,
            float(np.linalg.norm(q_emb)),
        )
        log.info("Sample meta: %s", json.dumps(metas[0], ensure_ascii=False))
        return 0

    # Connect ChromaDB
    import chromadb

    chroma_dir = args.chroma_dir or settings.CHROMA_PERSIST_DIR
    client = chromadb.PersistentClient(path=chroma_dir)
    log.info("ChromaDB 目录: %s", chroma_dir)

    if args.rebuild:
        try:
            client.delete_collection(args.collection)
            log.info("Deleted collection: %s", args.collection)
        except Exception:
            pass

    try:
        col = client.get_collection(args.collection)
        log.info("Existing collection: %s (%d chunks)", args.collection, col.count())
    except Exception:
        col = client.create_collection(
            args.collection,
            metadata={"hnsw:space": "cosine", "description": "Research report chunks"},
        )
        log.info("Created collection: %s", args.collection)

    if args.dry_run:
        log.info(
            "[dry-run] Would upsert %d chunks into %s", len(metas), args.collection
        )
        return 0

    # Upsert in batches
    total = len(metas)
    bs = args.batch_size
    for i in range(0, total, bs):
        end = min(i + bs, total)
        batch_ids = [m["chunk_id"] for m in metas[i:end]]
        batch_emb = embeddings[i:end].tolist()
        batch_docs = [m.get("chunk_text", m.get("title", "")) for m in metas[i:end]]
        batch_meta = [{k: str(v) for k, v in m.items()} for m in metas[i:end]]
        col.upsert(
            ids=batch_ids,
            embeddings=batch_emb,
            documents=batch_docs,
            metadatas=batch_meta,
        )
        log.info("  Upserted: %d/%d", end, total)

    log.info("Done! Collection %s: %d chunks", args.collection, col.count())
    return 0


if __name__ == "__main__":
    sys.exit(main())
