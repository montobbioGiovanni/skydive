"""Agente con tool calling: è Claude a decidere quando e cosa cercare nella documentazione.

Differenza con rag.py: là cerchiamo NOI una volta sola, con la domanda dell'utente, e poi chiamiamo Claude.
Qui diamo a Claude lo strumento search_docs e lo lasciamo cercare quante volte vuole, con le parole che sceglie lui.

Prova, dalla radice del progetto (costa: ogni passo è una chiamata a Claude):
    python src/agent.py "What is the difference between stdio and Streamable HTTP transports?"
"""
import sys
from functools import lru_cache

import anthropic

from config import CLAUDE_MODEL
from rag import NOT_FOUND, build_context    
from search import search_docs

MAX_STEPS = 6          # massimo numero di chiamate a Claude per domanda

# --- 1. LA DESCRIZIONE DELLO STRUMENTO ------------------------------------------------------------
# Claude non vede il nostro codice Python: vede SOLO questo dizionario. Nome, descrizione e schema
# sono tutto quello che ha per decidere se e come usare lo strumento, quindi la descrizione è un prompt
# a tutti gli effetti: deve dire cosa fa, quando usarlo e come scrivere bene la query.
SEARCH_TOOL = {
    "name": "search_docs",
    "description": (
        "Cerca nella documentazione ufficiale di MCP (Model Context Protocol) e del Claude Agent SDK. "
        "Restituisce i 5 estratti più simili alla query, ognuno con il suo URL (tag <source>). "
        "La ricerca è semantica (per significato) e funziona molto meglio con query brevi e IN INGLESE, "
        "perché la documentazione e il modello di ricerca sono in inglese: traduci la domanda se serve. "
        "Fai una ricerca per ogni concetto: per confrontare due cose, cerca le due cose separatamente. "
        "Se i risultati non bastano, riprova con parole diverse."
    ),
    "input_schema": {                                  # JSON Schema: la "firma" dello strumento
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "La query di ricerca, in inglese, es. 'stdio transport' o 'register a tool in a Python server'",
            },
        },
        "required": ["query"],                         # query è obbligatoria
        "additionalProperties": False,                 # nessun altro campo ammesso (richiesto da strict)
    },
    "strict": True,     # l'API garantisce che l'input di Claude rispetti lo schema (niente campi mancanti o inventati)
}

# --- 2. IL SYSTEM PROMPT --------------------------------------------------------------------------
# Le stesse regole del RAG (grounding, fonti, "non lo so"), più le istruzioni sull'uso dello strumento.
SYSTEM_PROMPT = f"""Sei un assistente che risponde a domande sulla documentazione di MCP (Model Context Protocol) \
e del Claude Agent SDK.

Per trovare le informazioni hai lo strumento search_docs. Usalo sempre prima di rispondere:
non rispondere a memoria, perché la documentazione cambia spesso e l'utente deve poter verificare ogni affermazione.
Puoi fare più ricerche: una per ogni concetto della domanda, e altre con parole diverse se i risultati non bastano.
Quando hai abbastanza informazioni, smetti di cercare e rispondi.

Regole per la risposta:
- Usa solo le informazioni trovate con le ricerche, non le tue conoscenze pregresse.
- Alla fine elenca le fonti usate: gli URL dei tag <source> da cui hai preso davvero le informazioni.
- Se dopo le ricerche la risposta non c'è, rispondi esattamente "{NOT_FOUND}" e non aggiungere altro.
  Una risposta inventata è peggio di nessuna risposta. Se trovi solo una parte, rispondi a quella e di' cosa manca.
- Rispondi nella lingua della domanda; lascia invariati i nomi tecnici (funzioni, parametri, comandi).
- Sii conciso."""


@lru_cache(maxsize=1)
def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


# --- 3. ESEGUIRE LO STRUMENTO -----------------------------------------------------------------------
def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Esegue lo strumento richiesto da Claude. Restituisce (testo del risultato, è_un_errore).

    È il NOSTRO codice a eseguire la ricerca, non Claude: lui chiede, noi facciamo e gli diamo il risultato.
    """
    if name != "search_docs":                                   # Claude ha chiesto uno strumento che non esiste
        return f"Errore: strumento sconosciuto '{name}'.", True
    query = tool_input.get("query", "").strip()
    if not query:                                               # controllo di sicurezza, anche se strict lo garantisce
        return "Errore: la query è vuota.", True
    hits = search_docs(query)                                   # la stessa ricerca della tappa 2
    return build_context(hits), False                           # lo stesso formato <documents> della tappa 3


# --- 4. IL CICLO DELL'AGENTE --------------------------------------------------------------------------
def run_agent(question: str, max_steps: int = MAX_STEPS, verbose: bool = True) -> dict:
    """Il ciclo: chiama Claude; se chiede lo strumento lo eseguiamo e gli rimandiamo il risultato; ripeti."""
    messages = [{"role": "user", "content": question}]      # la conversazione: cresce a ogni passo
    searches = []                                            # le query scelte da Claude (per vederne il ragionamento)
    input_tokens = output_tokens = 0                         # sommiamo i token di TUTTE le chiamate

    for step in range(1, max_steps + 1):
        response = _get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=[SEARCH_TOOL],                             # gli strumenti che Claude può chiedere
            tool_choice={"type": "auto"},                    # Claude decide da solo se usarli (come chiede CLAUDE.md)
            output_config={"effort": "low"},
            messages=messages,                               # TUTTA la conversazione, ogni volta: Claude non ha memoria
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        # La risposta di Claude va aggiunta alla conversazione COSÌ COM'È (anche i blocchi thinking e tool_use):
        # al passo successivo Claude deve rivedere esattamente cosa aveva chiesto.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":               # end_turn (ha finito), max_tokens, refusal...: usciamo
            break

        # stop_reason == "tool_use": Claude vuole che eseguiamo uno o più strumenti.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if verbose:
                print(f"  [passo {step}] Claude cerca: {block.input.get('query')!r}")
            searches.append(block.input.get("query"))
            result_text, is_error = run_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,                     # collega il risultato alla richiesta giusta
                "content": result_text,
                "is_error": is_error,                        # se True, Claude sa che qualcosa è andato storto
            })
        # TUTTI i risultati in UN SOLO messaggio "user": se Claude ha chiesto 2 ricerche insieme, rispondiamo insieme.
        messages.append({"role": "user", "content": tool_results})
    else:
        # Il for è finito senza "break": abbiamo esaurito i passi mentre Claude voleva ancora cercare.
        return {
            "answer": f"Limite di {max_steps} passi raggiunto senza una risposta finale.",
            "searches": searches, "steps": max_steps, "stop_reason": "max_steps",
            "input_tokens": input_tokens, "output_tokens": output_tokens,
        }

    if response.stop_reason == "refusal":
        text = "Claude ha rifiutato di rispondere a questa domanda."
    else:
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            text += "\n\n[Risposta interrotta: raggiunto il limite di max_tokens]"

    return {
        "answer": text,
        "searches": searches,                                # le query di Claude, in ordine
        "steps": step,                                       # quante chiamate a Claude sono servite
        "stop_reason": response.stop_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the difference between stdio and Streamable HTTP transports?"
    result = run_agent(question)
    print()
    print(result["answer"])
    cost = result["input_tokens"] * 4 / 1_000_000 + result["output_tokens"] * 20 / 1_000_000   # prezzi di Opus 5.5
    print(f"\n[passi: {result['steps']} | ricerche: {len(result['searches'])} | "
          f"token: {result['input_tokens']} in, {result['output_tokens']} out | costo ≈ {cost:.4f} $ | "
          f"stop_reason: {result['stop_reason']}]")
