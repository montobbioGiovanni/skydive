"""Test della costruzione del prompt in rag.py. Non chiamano mai Claude: sono gratuiti e deterministici."""
from rag import NOT_FOUND, SYSTEM_PROMPT, build_context, build_user_message

# Due risultati finti, con la stessa forma di quelli restituiti da search_docs
HITS = [
    {"text": "## stdio\n\nThe client launches the server as a subprocess.",
     "url": "https://example.com/stdio.md", "page_title": "Transports", "section_title": "stdio", "score": 0.6},
    {"text": "## Sampling\n\nServers can request completions from the client.",
     "url": "https://example.com/sampling.md", "page_title": "Client", "section_title": "Sampling", "score": 0.5},
]


def test_build_context_contiene_ogni_documento():
    context = build_context(HITS)
    assert context.startswith("<documents>")                    # il blocco si apre...
    assert context.endswith("</documents>")                     # ...e si chiude
    assert '<document index="1">' in context                    # i documenti sono numerati da 1
    assert '<document index="2">' in context
    for hit in HITS:
        assert f"<source>{hit['url']}</source>" in context      # ogni URL è nel tag <source>: è quello che Claude cita
        assert hit["text"] in context                           # il testo è INTERO, non troncato come nella CLI


def test_build_context_titolo_con_pagina_e_sezione():
    context = build_context(HITS)
    assert "<title>Transports — stdio</title>" in context        # pagina e sezione insieme, per orientare Claude


def test_user_message_domanda_alla_fine():
    question = "What is stdio?"
    message = build_user_message(question, HITS)
    assert message.endswith(f"Domanda: {question}")             # la domanda è l'ultima cosa che Claude legge
    assert message.index("</documents>") < message.index("Domanda:")   # documenti PRIMA della domanda


def test_system_prompt_usa_la_frase_fissa():
    # Se qualcuno cambia NOT_FOUND, il prompt deve cambiare con lui (è una f-string):
    # così la frase che Claude scrive è sempre quella che la tappa 6 cercherà.
    assert NOT_FOUND in SYSTEM_PROMPT
