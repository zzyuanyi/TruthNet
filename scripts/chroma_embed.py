#!/usr/bin/env python
"""Step 1: Generate embeddings from MySQL research reports (NO chromadb import).

Outputs: data/processed/embeddings.npy + data/processed/chunks_meta.json
"""

import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU, avoid segfault
os.environ["OMP_NUM_THREADS"] = "4"

import sys
import json
import hashlib
import logging
import argparse
from pathlib import Path
import torch

torch.set_num_threads(4)
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app.core.config import settings  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--limit", type=int, default=0, help="Max reports (0=all)")
    p.add_argument("--output-dir", default="data/processed")
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Connect MySQL
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)

    limit_clause = f"LIMIT {args.limit}" if args.limit > 0 else ""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT report_id, wind_code, sec_name, org_name, title, publish_date, "
                f"abstract, rating_change FROM research_reports {limit_clause}"
            )
        ).fetchall()
    engine.dispose()
    log.info("Read %d research reports", len(rows))

    # Chunk and collect texts
    texts, metas = [], []
    for r in rows:
        rid, wc, sn, org, title, pd_date, abstract, rc = r
        content = (str(abstract or ""))[:2000]
        if not content.strip():
            content = str(title or "")[:500]
        if not content.strip():
            continue
        chunks = [content[i : i + 400] for i in range(0, len(content), 350)]
        for ci, chunk in enumerate(chunks):
            if len(chunk) < 30:
                continue
            cid = hashlib.sha256(f"{rid}:{ci}:{chunk}".encode()).hexdigest()[:32]
            texts.append(chunk)
            metas.append(
                {
                    "chunk_id": cid,
                    "report_id": str(rid),
                    "wind_code": str(wc or ""),
                    "sec_name": str(sn or ""),
                    "org_name": str(org or ""),
                    "title": str(title or ""),
                    "publish_date": str(pd_date or ""),
                    "rating_change": str(rc or ""),
                    "chunk_index": ci,
                    "char_start": ci * 350,
                    "char_end": min(ci * 350 + 400, len(content)),
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest()[:16],
                }
            )

    log.info("Chunks: %d", len(texts))
    if not texts:
        log.warning("No chunks generated!")
        return 1

    # Load model and embed in batches
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        "BAAI/bge-small-zh-v1.5", cache_folder="data/model_cache", device="cpu"
    )
    log.info("Model loaded, embedding %d chunks...", len(texts))

    all_embeddings = []
    bs = args.batch_size
    for i in range(0, len(texts), bs):
        batch = texts[i : i + bs]
        emb = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        all_embeddings.append(emb)
        if (i + bs) % 10000 < bs or i + bs >= len(texts):
            log.info("  Embedded: %d/%d", min(i + bs, len(texts)), len(texts))

    embeddings = np.concatenate(all_embeddings, axis=0)
    log.info("Embeddings shape: %s", embeddings.shape)

    # Save
    np.save(str(out_dir / "embeddings.npy"), embeddings)
    with open(out_dir / "chunks_meta.json", "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False)
    log.info("Saved embeddings.npy + chunks_meta.json (%d chunks)", len(metas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
