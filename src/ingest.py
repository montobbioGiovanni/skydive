import requests
import re # espressioni regolari, per leggere le righe di llms.txt
import json
import time
from pathlib import Path

''' QUESTO FILE SERVE PER SCARICARE LE PAGINE DELLE DOCUMENTAZIONI E METTERLE DENTRO data/raw'''

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Ogni sorgente: dove sta l'indice, e quale pezzo di URL deve contenere una pagina per essere tenuta
SOURCES = [
    {"index": "https://modelcontextprotocol.io/llms.txt", "keep": "/2026-07-28/"},
    {"index": "https://code.claude.com/docs/llms.txt",    "keep": "/agent-sdk/"},
]

LINK_RE = re.compile(r"\[([^\]]+)\]\((https://[^)\s]+\.md)\)")   # cattura [Titolo]

def parse_llms_txt(text: str, keep: str) -> list[dict]:
    pages = []
    seen = set()                                  
    for title, url in LINK_RE.findall(text):      # findall restituisce coppie (titolo, url)
        if keep in url and url not in seen:
            seen.add(url)
            pages.append({"title": title, "url": url})
    return pages

def url_to_filename(url: str) -> str:
    return url.replace("https://", "").replace("/", "__")
    

# funzione per scaricare la pagina
def fetch(url: str) -> str:
    response = requests.get(url, timeout=30)   # timeout: senza, se il server non risponde lo script resta appeso per sempre
    response.raise_for_status()                # se lo status è 4xx/5xx lancia un'eccezione invece di salvare una pagina d'errore
    return response.text


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)   # crea data/raw (e le cartelle sopra) se non esiste

    manifest = []                                # la "rubrica": per ogni file salvato, da quale URL e titolo viene

    for source in SOURCES:                       # prima MCP, poi Agent SDK
        index_text = fetch(source["index"])                      # scarica il file llms.txt (solo testo, l'elenco)
        pages = parse_llms_txt(index_text, source["keep"])       # tiene solo le pagine che ci interessano, senza doppioni
        print(f"{source['index']}: {len(pages)} pagine")         # controllo a colpo d'occhio: ~57 e ~32

        for page in pages:                       # ora scarichiamo davvero ogni pagina dell'elenco
            text = fetch(page["url"])                            # il Markdown della pagina
            filename = url_to_filename(page["url"])              # nome univoco, costruito dal percorso dell'URL
            (RAW_DIR / filename).write_text(text, encoding="utf-8")   # salva su disco; utf-8 per accenti e simboli
            manifest.append({"title": page["title"], "url": page["url"], "file": filename})
            time.sleep(0.3)                      # pausa di cortesia: non bombardare il server con richieste a raffica

    manifest_path = RAW_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    # indent=2 -> JSON leggibile a occhio; ensure_ascii=False -> scrive "è" e non "è"
    print(f"Salvate {len(manifest)} pagine in {RAW_DIR}")


if __name__ == "__main__":   # vero solo se lanci "python src/ingest.py", falso se un altro file fa "import ingest"
    main()