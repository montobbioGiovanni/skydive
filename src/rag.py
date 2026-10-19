"""RAG (Retrieval-Augmented Generation): cerca i chunk pertinenti, li passa a Claude insieme alla domanda,
restituisce la risposta con le fonti.

Prova veloce, dalla radice del progetto:
    python src/rag.py "What is the stdio transport?"            # chiama Claude (costa ~1-2 centesimi)
    python src/rag.py --dry-run "What is the stdio transport?"  # mostra solo il prompt, senza chiamare Claude (gratis)
"""
import sys
from functools import lru_cache

import anthropic

from config import CLAUDE_MODEL, TOP_K
from search import search_docs

# La frase fissa per il "non lo so". È una costante perché la useremo anche altrove:
# nella tappa 6 potremo riconoscere automaticamente le risposte "non trovato" cercando questa frase.
NOT_FOUND = "Non lo trovo nella documentazione."

# Le regole fisse, uguali per ogni domanda. Per ogni regola diciamo anche il PERCHÉ:
# i modelli recenti seguono meglio le istruzioni quando ne capiscono lo scopo.
# Le triple virgolette permettono di andare a capo liberamente (niente "\" e niente spazi dimenticati).
SYSTEM_PROMPT = f"""Sei un assistente che risponde a domande sulla documentazione di MCP (Model Context Protocol) \
e del Claude Agent SDK.

Nel messaggio dell'utente trovi alcuni documenti, dentro i tag <documents>, seguiti dalla domanda.
I documenti sono estratti della documentazione ufficiale, scelti da un sistema di ricerca automatico:
alcuni possono essere pertinenti, altri no.

Regole:
- Rispondi usando solo le informazioni contenute nei documenti, non le tue conoscenze pregresse.
  La documentazione cambia spesso e quello che ricordi potrebbe essere superato; inoltre l'utente
  deve poter verificare ogni affermazione andando a leggere la fonte.
- Ignora i documenti che non c'entrano con la domanda.
- Alla fine della risposta elenca le fonti che hai usato: l'URL che trovi nel tag <source> di ciascun documento.
  Cita solo i documenti da cui hai preso davvero delle informazioni.
- Se i documenti non contengono la risposta, rispondi esattamente "{NOT_FOUND}" e non aggiungere altro.
  Una risposta inventata o tirata a indovinare è peggio di nessuna risposta: l'utente si fiderebbe di un'informazione sbagliata.
  Se i documenti rispondono solo in parte, rispondi alla parte coperta e di' chiaramente cosa manca.
- Rispondi nella lingua della domanda, anche se i documenti sono in inglese.
  Lascia invariati i nomi tecnici (nomi di funzioni, parametri, comandi), perché l'utente li deve poter cercare nella documentazione.
- Sii conciso: vai dritto alla risposta, con un esempio di codice solo se è nei documenti e aiuta a capire."""


def build_context(hits: list[dict]) -> str:
    """Trasforma i risultati di search_docs nel blocco <documents> da mettere nel messaggio per Claude."""
    s = "<documents>\n"
    for i, hit in enumerate(hits, start=1):                    # numeriamo i documenti da 1, come nell'output della CLI
        title = f"{hit['page_title']} — {hit['section_title']}"   # titolo pagina + sezione: aiuta Claude a orientarsi
        s += f'<document index="{i}">\n'                       # apici singoli fuori, così dentro possiamo usare le doppie
        s += f"<source>{hit['url']}</source>\n"                # l'URL da citare
        s += f"<title>{title}</title>\n"
        s += f"<content>\n{hit['text']}\n</content>\n"         # il testo INTERO del chunk: questa volta lo legge Claude
        s += "</document>\n"
    s += "</documents>"
    return s


def build_user_message(question: str, hits: list[dict]) -> str:
    """Il messaggio completo per Claude: prima i documenti, la domanda alla fine (come consiglia Anthropic)."""
    return f"{build_context(hits)}\n\nDomanda: {question}"


@lru_cache(maxsize=1)                          # un solo client per tutto il programma, creato al primo uso
def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()               # legge ANTHROPIC_API_KEY dall'ambiente (caricata da config.py)


def answer(question: str, k: int = TOP_K) -> dict:
    """Risponde a una domanda con il RAG. Restituisce la risposta, le fonti e i token usati; non stampa niente."""
    hits = search_docs(question, k)                          # 1. RETRIEVAL: i k chunk più simili (locale, gratis)
    user_message = build_user_message(question, hits)        # 2. AUGMENTATION: chunk + domanda in un unico messaggio

    response = _get_client().messages.create(                # 3. GENERATION: Claude legge e risponde (questo costa)
        model=CLAUDE_MODEL,                                 
        max_tokens=16000,                                   
        system=SYSTEM_PROMPT,                               
        output_config={"effort": "low"},                     
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason == "refusal":                   
        text = "Claude ha rifiutato di rispondere a questa domanda."
    else:
        # content è una lista di blocchi (thinking, text...): uniamo solo quelli di testo, come nella tappa 0
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":             # risposta tagliata: meglio dirlo che mostrarla come completa
            text += "\n\n[Risposta interrotta: raggiunto il limite di max_tokens]"

    return {
        "answer": text,
        "sources": hits,                                    
        "stop_reason": response.stop_reason,
        "input_tokens": response.usage.input_tokens,         # documenti + domanda + system prompt
        "output_tokens": response.usage.output_tokens,       # risposta + ragionamento (anche se non lo vediamo)
    }


if __name__ == "__main__":
    args = sys.argv[1:]                                      # le parole dopo "python src/rag.py"
    dry_run = "--dry-run" in args                            # modalità gratuita: mostra il prompt senza chiamare Claude
    words = [a for a in args if a != "--dry-run"]
    question = " ".join(words) or "What is the stdio transport?"   # domanda di default se non ne passi una

    if dry_run:
        hits = search_docs(question)
        message = build_user_message(question, hits)
        print(SYSTEM_PROMPT, "\n\n----- MESSAGGIO UTENTE -----\n")
        print(message)
        chars = len(SYSTEM_PROMPT) + len(message)
        print(f"\n[dry-run] {chars} caratteri, circa {chars // 4} token in input. Nessuna chiamata a Claude.")
    else:
        result = answer(question)
        print(result["answer"])
        print(f"\n[stop_reason: {result['stop_reason']} | "
              f"token in input: {result['input_tokens']} | token in output: {result['output_tokens']}]")
