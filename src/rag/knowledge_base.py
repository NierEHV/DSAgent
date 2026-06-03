"""
RAG 知识库 — 简易版
文件上传 → chunk → embedding → ChromaDB 检索
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """简易 RAG 知识库"""

    def __init__(self, storage_dir: str = "data/knowledge"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "index.json"
        self._docs: list[dict] = []
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self._docs = json.load(f)
        else:
            self._docs = []

    def _save_index(self):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._docs, f, ensure_ascii=False, indent=2)

    def add_document(self, title: str, content: str, metadata: dict = None) -> str:
        """添加文档 — 按段落切 chunk"""
        chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
        doc_id = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{title[:20]}"

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            # 保存 chunk
            chunk_file = self.storage_dir / f"{chunk_id}.txt"
            with open(chunk_file, "w", encoding="utf-8") as f:
                f.write(chunk)

            self._docs.append({
                "id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "chunk_index": i,
                "content": chunk[:500],  # 索引中只存前500字
                "metadata": metadata or {},
                "added_at": datetime.now().isoformat(),
            })

        self._save_index()
        logger.info(f"Added document '{title}': {len(chunks)} chunks")
        return doc_id

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """关键词搜索 (简单匹配, 无向量化)"""
        query_lower = query.lower()
        scored = []

        for doc in self._docs:
            content = doc.get("content", "")
            # 简单的词频匹配
            score = sum(1 for word in query_lower.split() if word.lower() in content.lower())
            if score > 0:
                # 读取完整 chunk
                chunk_file = self.storage_dir / f"{doc['id']}.txt"
                full_content = content
                if chunk_file.exists():
                    with open(chunk_file, "r", encoding="utf-8") as f:
                        full_content = f.read()
                scored.append((score, {**doc, "full_content": full_content}))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def search_context(self, query: str, top_k: int = 3) -> str:
        """搜索并返回拼接好的上下文字符串 (可直接拼到 LLM prompt)"""
        results = self.search(query, top_k)
        if not results:
            return ""
        parts = ["## 相关知识库内容\n"]
        for i, r in enumerate(results):
            parts.append(f"### {r['title']} (相关度: {i+1})\n{r.get('full_content', r.get('content', ''))}\n")
        return "\n".join(parts)

    def list_documents(self) -> list[dict]:
        """列出所有文档"""
        doc_ids = {}
        for d in self._docs:
            did = d.get("doc_id", "")
            if did not in doc_ids:
                doc_ids[did] = {
                    "doc_id": did,
                    "title": d.get("title", ""),
                    "chunks": 0,
                    "added_at": d.get("added_at", ""),
                }
            doc_ids[did]["chunks"] += 1
        return sorted(doc_ids.values(), key=lambda x: x.get("added_at", ""), reverse=True)

    def delete_document(self, doc_id: str):
        """删除文档及所有 chunk"""
        self._docs = [d for d in self._docs if d.get("doc_id") != doc_id]
        # 删除文件
        for f in self.storage_dir.glob(f"{doc_id}*"):
            f.unlink()
        self._save_index()


# 全局单例
kb = KnowledgeBase()
