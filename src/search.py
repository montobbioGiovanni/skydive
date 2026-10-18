"""Ricerca semantica sull'indice Chroma: search_docs(query, k)."""
from functools import lru_cache

import chromadb

from config import CHROMA_DIR, COLLECTION_NAME, TOP_K

@lru_cache(maxsize=1)                     # ricorda il risultato: dalla seconda chiamata in poi restituisce lo stesso oggetto
def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))   # apre l'indice su disco
    return client.get_collection(COLLECTION_NAME)              # get, non create: la collezione l'ha creata index.py

def search_docs(query: str, k: int = TOP_K) -> list[dict]:
    collection = _get_collection()
    results = collection.query(
        query_texts=[query],                                  # una lista, anche se la domanda è una sola
        n_results=k,                                          # quanti risultati: il nostro top-k
        include=["documents", "metadatas", "distances"],      # cosa vogliamo indietro (gli embedding no: non servono)
    )

    documents = results["documents"][0]       # [0] = i risultati della nostra unica domanda
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    hits = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        hits.append({"text":doc,
                      "url": meta["url"], 
                      "page_title":meta["page_title"], 
                      "section_title":meta["section_title"], 
                      "score": round(1-dist, 3)
                    })
    return hits

if __name__ == "__main__":
    hits = search_docs("What is the difference between stdio and HTTP transport?")
    for hit in hits:
        print(f"{hit['text']} | {hit['score']}  {hit['url']}  |  {hit['section_title']}")