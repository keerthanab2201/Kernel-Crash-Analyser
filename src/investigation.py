"""Bounded local evidence tools. No shell execution or arbitrary file access."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def tool(name, properties):
    return {"name": name, "description": "Read evidence from the supplied log or approved documentation corpus.",
            "strict": True, "input_schema": {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}}


TOOLS = [
    tool("get_log_context", {"line_id": {"type": "integer"}, "window": {"type": "integer"}}),
    tool("search_documentation", {"query": {"type": "string"}}),
    tool("lookup_symbol", {"symbol": {"type": "string"}, "kernel_revision": {"type": "string"}}),
]


class EvidenceTools:
    def __init__(self, log: str, corpus: Path, *, excluded_family: str | None = None):
        self.lines = log.splitlines()
        raw = corpus.read_bytes()
        self.corpus_sha256 = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        self.documents = data["documents"]
        if not data.get("version") or not isinstance(self.documents, list):
            raise ValueError("corpus requires version and documents")
        ids = set()
        for doc in self.documents:
            if doc["id"] in ids or not doc.get("source_url") or not doc.get("revision"):
                raise ValueError("each corpus document needs unique id, source URL and revision")
            ids.add(doc["id"])
            if doc.get("kind") != "documentation":
                raise ValueError("benchmark corpus permits documentation only; incident reports and fixes are excluded")
            if excluded_family and doc.get("bug_family") == excluded_family:
                raise ValueError("retrieval corpus contains the held-out bug family")
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer()
        self.matrix = self.vectorizer.fit_transform([d["text"] for d in self.documents])

    def execute(self, name: str, args: dict) -> dict:
        if name == "get_log_context":
            line, window = args["line_id"], args["window"]
            if type(line) is not int or type(window) is not int or not 1 <= line <= len(self.lines) or not 0 <= window <= 20:
                raise ValueError("invalid line or window (maximum 20)")
            return {"lines": [{"line_id": i + 1, "text": self.lines[i]} for i in range(max(0, line - window - 1), min(len(self.lines), line + window))]}
        if name == "search_documentation":
            query = args["query"]
            if not isinstance(query, str) or not 1 <= len(query) <= 500:
                raise ValueError("query length must be 1..500")
            scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
            indices = sorted(range(len(scores)), key=lambda i: (-scores[i], self.documents[i]["id"]))[:3]
            return {"retriever": "tfidf", "corpus_sha256": self.corpus_sha256,
                    "matches": [{**self.documents[i], "text": self.documents[i]["text"][:3000], "score": float(scores[i])} for i in indices if scores[i] > 0]}
        if name == "lookup_symbol":
            return {"matches": [d for d in self.documents if args["symbol"] in d.get("symbols", []) and args["kernel_revision"] == d["revision"]][:3]}
        raise ValueError("unknown evidence tool")
