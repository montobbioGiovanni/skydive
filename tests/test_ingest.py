from ingest import MAX_CHARS, chunk_page, split_long   # funziona grazie a pythonpath = src in pytest.ini

URL = "https://example.com/pagina.md"
TITLE = "Pagina di prova"

# Una pagina finta che contiene tutti i casi che gestiamo:
# boilerplate iniziale, introduzione, due sezioni, un tag MDX e una sezione vuota
SAMPLE = """> ## Documentation Index
> Fetch the complete documentation index at: https://example.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Pagina di prova

Questa è l'introduzione della pagina, scritta abbastanza lunga da superare il minimo.

## Prima sezione

Testo della prima sezione, anche questo abbastanza lungo da superare il minimo di caratteri.

## Seconda sezione

<Note>
Testo della seconda sezione dentro un componente MDX, abbastanza lungo anche lui.
</Note>

## Vuota
"""


def test_chunk_page_divide_sui_titoli():
    chunks = chunk_page(SAMPLE, URL, TITLE)                    # Act: chiamo la funzione
    titles = [c["section_title"] for c in chunks]              # prendo solo i titoli di sezione
    assert titles == [TITLE, "Prima sezione", "Seconda sezione"]   # l'intro prende il titolo della pagina; "Vuota" sparisce


def test_boilerplate_rimosso():
    chunks = chunk_page(SAMPLE, URL, TITLE)
    for c in chunks:                                           
        assert "Documentation Index" not in c["text"]          # il blocco iniziale "> ## Documentation Index..." non deve esserci


def test_tag_mdx_rimossi():
    chunks = chunk_page(SAMPLE, URL, TITLE)
    all_text = " ".join(c["text"] for c in chunks)             
    assert "<Note>" not in all_text                            # il tag di apertura è sparito...
    assert "</Note>" not in all_text                           # e anche quello di chiusura
    assert "Testo della seconda sezione" in all_text           # ma il contenuto che stava DENTRO il tag è rimasto


def test_metadati():
    chunks = chunk_page(SAMPLE, URL, TITLE)
    for c in chunks:
        assert c["url"] == URL                                 # ogni chunk sa da quale pagina viene (servirà per citare la fonte)
        assert c["page_title"] == TITLE


def test_split_long_rispetta_il_limite():
    long_text = "parola " * 1000                               # 7.000 caratteri: molto più di MAX_CHARS (1.500)
    pieces = split_long(long_text)
    assert len(pieces) > 1                                     # è stato davvero diviso
    assert all(len(p) <= MAX_CHARS for p in pieces)            # all(...) è True solo se OGNI pezzo rispetta il limite


def test_split_long_testo_corto():
    assert split_long("ciao") == ["ciao"]                      # un testo sotto il limite torna intatto, in una lista di un elemento