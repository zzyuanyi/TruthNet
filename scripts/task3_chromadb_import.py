"""任务③：ChromaDB 研报分块入库 (v6 - ChromaDB 内置 embedding)
===============================================================
MySQL → 分块 → ChromaDB.add() 自动 embedding (SentenceTransformer)
"""

import sys, time
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
import chromadb
from chromadb.utils import embedding_functions

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
def log(msg): print(msg, flush=True)

# ── 配置 ──
CHROMA_PATH = Path(r"d:\projects\TruthNet\data\chroma_db")
CHROMA_PATH.mkdir(parents=True, exist_ok=True)
COLLECTION_NAME = "research_report_chunks"
CHUNK_SIZE, CHUNK_OVERLAP = 600, 80
BATCH_SIZE = 2000
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
DB_URL = "mysql+pymysql://truthnet:truthnet123@localhost:3306/truthnet"

# ── ChromaDB + 内置 Embedding ──
log("Init ChromaDB with SentenceTransformer embedding...")
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
try:
    client.delete_collection(COLLECTION_NAME)
except Exception:
    pass
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
collection = client.create_collection(
    name=COLLECTION_NAME,
    embedding_function=ef,
    metadata={"description": "研报摘要分块 BGE-small", "hnsw:space": "cosine"},
)
log(f"  Created '{COLLECTION_NAME}' with {MODEL_NAME}")

# ── 分块 ──
def chunk_text(text, chunk_size=600, overlap=80):
    if not text or not isinstance(text, str): return []
    text = text.strip()
    if len(text) <= chunk_size: return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:].strip()); break
        chunk = text[start:end]
        for sep in ["。", "；", "\n", "，"]:
            idx = chunk.rfind(sep, chunk_size // 2)
            if idx > chunk_size // 2:
                end = start + idx + 1; break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks

# ── 读取 ──
log("Reading MySQL...")
engine = create_engine(DB_URL)
df = pd.read_sql(
    "SELECT report_id, wind_code, sec_name, org_name, title, "
    "publish_date, abstract, rating_change FROM research_reports "
    "WHERE abstract IS NOT NULL AND abstract != ''", engine)
engine.dispose()
log(f"  {len(df)} reports")

# ── 分块 ──
log("Chunking...")
all_ids, all_texts, all_metas = [], [], []
for _, row in df.iterrows():
    rid = str(row["report_id"])
    for ci, chunk in enumerate(chunk_text(str(row["abstract"]), CHUNK_SIZE, CHUNK_OVERLAP)):
        all_ids.append(f"{rid}_chunk_{ci}")
        all_texts.append(chunk)
        all_metas.append({
            "report_id": rid,
            "wind_code": str(row["wind_code"]) if pd.notna(row["wind_code"]) else "",
            "sec_name": str(row["sec_name"]) if pd.notna(row["sec_name"]) else "",
            "org_name": str(row["org_name"]) if pd.notna(row["org_name"]) else "",
            "title": str(row["title"]) if pd.notna(row["title"]) else "",
            "publish_date": str(row["publish_date"]) if pd.notna(row["publish_date"]) else "",
            "rating_change": str(row["rating_change"]) if pd.notna(row["rating_change"]) else "",
            "chunk_index": ci,
        })
total = len(all_texts)
log(f"  {total} chunks")

# ── 批量写入 ChromaDB（它内部自动 embedding） ──
log(f"Storing + embedding (batch={BATCH_SIZE})...")
t0 = time.time()

for start in range(0, total, BATCH_SIZE):
    end = min(start + BATCH_SIZE, total)
    collection.add(
        ids=all_ids[start:end],
        documents=all_texts[start:end],
        metadatas=all_metas[start:end],
    )
    done = end
    e = time.time() - t0
    rate = done / e if e > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0
    log(f"  {done}/{total} | {rate:.0f} c/s | ETA {eta/60:.0f}m")

elapsed = time.time() - t0
log(f"\nDone! {total} chunks in {elapsed/60:.1f} min")

# ── 验证 ──
log(f"\nCollection count: {collection.count()}")
r = collection.query(query_texts=["财务造假风险"], n_results=3)
log(f"Query '财务造假风险': {len(r['ids'][0])} hits")
r2 = collection.query(query_texts=["财务欺诈"], where={"wind_code": "600518.SH"}, n_results=3)
log(f"Query 600518.SH: {len(r2['ids'][0])} hits")
log("Task ③ complete!")
