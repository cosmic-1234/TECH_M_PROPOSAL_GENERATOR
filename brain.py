"""
brain.py - ChromaDB knowledge base (Windows-safe encoding)
"""
import os, re, sys
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class RFPKnowledgeBase:
    def __init__(self, db_path: str = "./chroma_db"):
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_func = DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="techm_proposals",
            embedding_function=self.embedding_func,
        )

    def add_document(self, md_path: str):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        chunks = self._split_by_headers(content)
        existing_ids = set(self.collection.get()["ids"])
        docs, metas, ids = [], [], []
        for i, (header, body) in enumerate(chunks):
            chunk_id = f"{os.path.basename(md_path)}__chunk_{i}"
            if chunk_id in existing_ids or len(body.strip()) < 30:
                continue
            docs.append(body.strip())
            metas.append({"source": os.path.basename(md_path), "header": header})
            ids.append(chunk_id)
        if docs:
            self.collection.add(documents=docs, metadatas=metas, ids=ids)
            print(f"Added {len(docs)} chunks from {os.path.basename(md_path)}")
        else:
            print(f"No new chunks from {os.path.basename(md_path)}")

    def add_raw_text(self, text: str, source_name: str = "inline"):
        chunks = self._split_by_headers(text)
        existing_ids = set(self.collection.get()["ids"])
        docs, metas, ids = [], [], []
        for i, (header, body) in enumerate(chunks):
            chunk_id = f"{source_name}__chunk_{i}"
            if chunk_id in existing_ids or len(body.strip()) < 30:
                continue
            docs.append(body.strip())
            metas.append({"source": source_name, "header": header})
            ids.append(chunk_id)
        if docs:
            self.collection.add(documents=docs, metadatas=metas, ids=ids)

    def list_sources(self) -> list:
        all_meta = self.collection.get()["metadatas"]
        if not all_meta:
            return []
        return sorted(set(m["source"] for m in all_meta if m))

    def query(self, text: str, n_results: int = 5) -> str:
        count = self.collection.count()
        if count == 0:
            return "No relevant past proposals found in the knowledge base."
        results = self.collection.query(
            query_texts=[text],
            n_results=min(n_results, count),
        )
        passages = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        if not passages:
            return "No relevant past proposals found."
        formatted = []
        for passage, meta in zip(passages, metas):
            source = meta.get("source", "unknown") if meta else "unknown"
            header = meta.get("header", "") if meta else ""
            label = f"[Source: {source} | Section: {header}]" if header else f"[Source: {source}]"
            formatted.append(f"{label}\n{passage}")
        return "\n\n---\n\n".join(formatted)

    def count(self) -> int:
        return self.collection.count()

    @staticmethod
    def _split_by_headers(text: str) -> list:
        pattern = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        if not matches:
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
            return [("Document", p) for p in paragraphs] if paragraphs else [("Document", text)]
        chunks = []
        for idx, match in enumerate(matches):
            header = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                chunks.append((header, body))
        return chunks


def load_knowledge_base(db_path: str = "./chroma_db") -> RFPKnowledgeBase:
    kb = RFPKnowledgeBase(db_path=db_path)
    md_dir = "data/markdown"
    os.makedirs(md_dir, exist_ok=True)
    indexed = 0
    for fname in os.listdir(md_dir):
        if fname.endswith(".md"):
            kb.add_document(os.path.join(md_dir, fname))
            indexed += 1
    if indexed == 0:
        print("No .md files found in data/markdown/")
    return kb