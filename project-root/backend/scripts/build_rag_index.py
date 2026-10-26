"""Build the Chroma RAG index from the SQLite knowledge base.

Usage:
    python backend/scripts/build_rag_index.py [limit]
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rag import RagService


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    service = RagService()
    count = asyncio.run(service.build_index(limit=limit))
    print(f"RAG index built: {count} vectors")


if __name__ == "__main__":
    main()
