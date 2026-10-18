''' QUESTO FILE SERVE PER SCARICARE LE PAGINE DELLE DOCUMENTAZIONI E METTERLE DENTRO data/raw

parse_llms_txt	Legge l'elenco llms.txt e restituisce le pagine da tenere (titolo + URL), senza doppioni
url_to_filename	Trasforma un URL in un nome di file valido e univoco
fetch	Scarica un URL e ne restituisce il testo
download_all	Comando download: scarica tutte le pagine in data/raw/ e scrive manifest.json
clean_text	Pulisce il testo di una pagina: toglie il boilerplate “Documentation Index”
split_sections	Divide una pagina in sezioni, tagliando sui titoli ##
split_long	Taglia una sezione troppo lunga in pezzi da massimo 1.500 caratteri, con sovrapposizione
chunk_page	Crea i chunk di una pagina: pulisce, divide, taglia e attacca i metadati a ogni pezzo
build_chunks	Comando chunk: applica chunk_page a tutte le pagine e salva tutto in data/chunks.jsonl
'''
import requests
import re # espressioni regolari, per leggere le righe di llms.txt
import json
import time
from pathlib import Path



MDX_TAG_RE = re.compile(
    r"</?(?:Steps|Step|Tabs|Tab|CodeGroup|Note|Tip|Warning|Info|Check|Card|CardGroup|"
    r"Accordion|AccordionGroup|Frame|div|img|br)\b[^>]*>"
) #regex per togliere i tag dei componenti markdown
EXCLUDED_URLS = {"https://modelcontextprotocol.io/specification/2026-07-28/schema.md"}   # pagine generate, non utili
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CHUNKS_PATH = Path(__file__).resolve().parent.parent / "data"/"chunks.jsonl"
MAX_CHARS = 1500
MIN_CHARS = 50
OVERLAP_CHARS = 200

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


def download_all() -> None:
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

def clean_text(text: str) -> str:
    if text.startswith("> ## Documentation Index"):
        parti = text.split("\n\n", 1) # divide il testo una sola volta al primo "\n\n", la prima riga vuota
        text = parti[1] if len(parti) > 1 else text 
    text = MDX_TAG_RE.sub("", text)
    return text.strip()

def split_sections(text: str) -> list[tuple[str, str]]:
    sections = []
    current_title = ""        # il testo prima del primo "##" (titolo della pagina, introduzione) non ha titolo di sezione
    current_lines = []        # le righe della sezione in costruzione
    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines != []:
                text1 = "\n".join(current_lines).strip()
                sections.append((current_title, text1))

            current_title = line[3:]
            current_lines = [line]
        else:
            current_lines.append(line)
    text1 = "\n".join(current_lines).strip()
    sections.append((current_title, text1)) # alla fine del ciclo l'ultima sezione è ancora "in costruzione": è da aggiungere
    return sections

def split_long(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    if len(text) <= max_chars:            # caso facile, il più frequente: la sezione ci sta già tutta
        return [text]

    # 1) Le "unità" con cui costruiamo i pezzi sono i paragrafi (separati da una riga vuota).
    #    Un paragrafo più lungo del limite lo tagliamo a fette fisse, unico modo per rispettare il limite.
    units = []
    for paragraph in text.split("\n\n"):
        while len(paragraph) > max_chars:         # finché il paragrafo è troppo lungo
            units.append(paragraph[:max_chars])   # ne stacchiamo una fetta da max_chars caratteri
            paragraph = paragraph[max_chars:]     # e continuiamo con il resto
        if paragraph.strip():                     # saltiamo i paragrafi vuoti
            units.append(paragraph)

    # 2) Riempiamo i pezzi un paragrafo alla volta, finché ci stanno.
    pieces = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit   # come sarebbe il pezzo aggiungendo questo paragrafo
        if len(candidate) <= max_chars:
            current = candidate                                    # ci sta: lo aggiungiamo e passiamo al prossimo
        else:
            pieces.append(current)                                 # non ci sta: chiudiamo il pezzo corrente...
            tail = current[-overlap:]                              # ...e ne prendiamo gli ultimi `overlap` caratteri
            tail = tail[tail.find(" ") + 1:]   # salta il pezzo di parola iniziale: si riparte dalla prima parola intera (find restituisce la posizione del primo spazio)
            with_overlap = f"{tail}\n\n{unit}"
            # il nuovo pezzo parte dalla coda del precedente (sovrapposizione), se così non sfora il limite
            current = with_overlap if len(with_overlap) <= max_chars else unit
    if current:                                                    # di nuovo: non dimenticare l'ultimo pezzo!
        pieces.append(current)
    return pieces

def chunk_page(text: str, url: str, page_title: str) -> list[dict]:
    chunks = []
    text = clean_text(text)

    sections = split_sections(text)
    for (section_title, section_text) in sections:
        splitted = split_long(section_text)
        for split in splitted:
            if len(split.strip()) < MIN_CHARS:      # pezzo troppo corto, non lo teniamo...
                continue  
            chunks.append({"text": split, "url": url, "page_title": page_title,
                           "section_title": section_title or page_title})   # sezione iniziale senza "##": usa il titolo della pagina
    return chunks

def build_chunks() -> None:
    # 1) La "rubrica" scritta da download_all()
    manifest = json.loads((RAW_DIR / "manifest.json").read_text(encoding="utf-8"))   # testo JSON -> lista di dizionari

    all_chunks = []                                  
    for page in manifest: 
        if page["url"] in EXCLUDED_URLS:
            continue                       
        text = (RAW_DIR / page["file"]).read_text(encoding="utf-8")       # il Markdown salvato su disco
        page_chunks = chunk_page(text, page["url"], page["title"])        # tutto il lavoro vero lo fa chunk_page
        all_chunks.extend(page_chunks)                # aggiunge i singoli chunk, non la lista intera come un elemento

    # 2) Scriviamo un chunk per riga (formato JSONL)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:   # "with" chiude il file da solo, anche in caso di errore
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")   # dizionario -> una riga di testo JSON

    print(f"Creati {len(all_chunks)} chunk da {len(manifest)} pagine in {CHUNKS_PATH}")


if __name__ == "__main__":
    import sys                                   # sys.argv è la lista delle parole scritte nel terminale
    command = sys.argv[1] if len(sys.argv) > 1 else ""   # la parola dopo "python src/ingest.py", se c'è
    if command == "download":
        download_all()
    elif command == "chunk":
        build_chunks()
    else:
        print("Uso: python src/ingest.py download | chunk")