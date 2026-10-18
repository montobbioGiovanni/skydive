"""Calcola gli embedding dei chunk e li salva in un indice Chroma su disco.
load_chunks	Legge data/chunks.jsonl e restituisce la lista dei chunk, l'inverso di quello che fa build_chunks
build_index	Costruisce l'indice da zero: cancella il vecchio, crea la collezione con il coseno, e manda i chunk a Chroma a blocchi da 500. Chroma calcola gli embedding e li salva"""
import json
import shutil                                 # per cancellare la cartella del vecchio indice

import chromadb

from config import CHROMA_DIR, COLLECTION_NAME
from ingest import CHUNKS_PATH                # riusiamo il percorso già definito in ingest.py

BATCH_SIZE = 500                              # quanti chunk mandiamo a Chroma per volta

def load_chunks() -> list[dict]:
    l = []
    with open(CHUNKS_PATH, encoding="utf-8") as file:
        for line in file:
            line1 = json.loads(line)
            l.append(line1)
    return l

def build_index() -> None:
    chunks = load_chunks()
    print(f"Letti {len(chunks)} chunk da {CHUNKS_PATH}")

    # Ricostruiamo l'indice DA ZERO ogni volta: se il chunking cambia (tappa 6),
    # non vogliamo vecchi chunk mescolati ai nuovi. È un file generato: si può sempre rifare.
    shutil.rmtree(CHROMA_DIR, ignore_errors=True)            # cancella data/chroma; nessun errore se non esiste

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))  # "Persistent" = salva su disco (l'altro tipo vive solo in memoria)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},          # distanza del coseno invece della l2 di default
    )
    # Non passiamo nessun modello: Chroma usa il suo default, all-MiniLM-L6-v2, che gira in locale

    for start in range(0, len(chunks), BATCH_SIZE):           # 0, 500, 1000, 1500: un blocco alla volta
        batch = chunks[start:start + BATCH_SIZE]              # lo "slice" prende fino a 500 chunk
        collection.add(
            ids=[str(start + i) for i in range(len(batch))],  # ogni record vuole un id univoco (stringa): usiamo la posizione
            documents=[c["text"] for c in batch],             # il testo: Chroma ne calcola l'embedding da solo
            metadatas=[                                       # i metadati viaggiano col chunk ma NON entrano nell'embedding
                {"url": c["url"], "page_title": c["page_title"], "section_title": c["section_title"]}
                for c in batch
            ],
        )
        print(f"  indicizzati {start + len(batch)}/{len(chunks)}")

    print(f"Fatto: {collection.count()} chunk nella collezione '{COLLECTION_NAME}'")

if __name__ == "__main__":
    build_index()