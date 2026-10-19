"""Lo stesso agente di agent.py, ma con il Tool Runner dell'SDK (beta) al posto del ciclo scritto a mano.

Serve per CONFRONTARE i due approcci: stesso strumento, stesso system prompt, stesso limite di passi.
Prova, dalla radice del progetto (costa come agent.py):
    python src/agent_runner.py "What is the difference between stdio and Streamable HTTP transports?"
"""
import sys

from anthropic import beta_tool

from agent import MAX_STEPS, SEARCH_TOOL, SYSTEM_PROMPT, _get_client   # riusiamo tutto: cambia solo il ciclo
from config import CLAUDE_MODEL
from rag import build_context
from search import search_docs


# --- LO STRUMENTO -------------------------------------------------------------------------------------
# Con @beta_tool non scriviamo più il dizionario con il JSON Schema: l'SDK lo genera dalla FIRMA della funzione
# (query: str -> parametro stringa obbligatorio) e dalla docstring (la descrizione del parametro, sotto "Args").
# La descrizione generale la prendiamo da agent.py, così i due agenti ricevono le stesse istruzioni.
@beta_tool(name="search_docs", description=SEARCH_TOOL["description"], strict=True)
def search_docs_tool(query: str) -> str:
    """Cerca nella documentazione di MCP e del Claude Agent SDK.

    Args:
        query: La query di ricerca, in inglese, es. 'stdio transport' o 'register a tool in a Python server'
    """
    print(f"  Claude cerca: {query!r}")          # per vedere le ricerche, come in agent.py
    return build_context(search_docs(query))     # il corpo è lo stesso di run_tool: cerca e formatta


# --- IL "CICLO" -------------------------------------------------------------------------------------------
def run_agent_runner(question: str, max_steps: int = MAX_STEPS) -> dict:
    """Esegue l'agente con il Tool Runner. Il ciclo (chiama, esegui strumenti, rimanda risultati) lo fa l'SDK."""
    runner = _get_client().beta.messages.tool_runner(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=[search_docs_tool],                 # passiamo la FUNZIONE decorata: l'SDK sa sia descriverla sia eseguirla
        tool_choice={"type": "auto"},
        output_config={"effort": "low"},
        max_iterations=max_steps,                 # il nostro MAX_STEPS: l'SDK smette dopo questo numero di chiamate
        messages=[{"role": "user", "content": question}],
    )

    input_tokens = output_tokens = steps = 0
    last = None
    for message in runner:                        # ogni giro = una risposta di Claude; gli strumenti li esegue l'SDK
        steps += 1
        input_tokens += message.usage.input_tokens
        output_tokens += message.usage.output_tokens
        last = message                            # l'ultima risposta è quella con il testo finale

    if last.stop_reason == "tool_use":            # Claude voleva ancora cercare: abbiamo esaurito i passi
        text = f"Limite di {max_steps} passi raggiunto senza una risposta finale."
    elif last.stop_reason == "refusal":
        text = "Claude ha rifiutato di rispondere a questa domanda."
    else:
        text = "".join(b.text for b in last.content if b.type == "text")

    return {"answer": text, "steps": steps, "stop_reason": last.stop_reason,
            "input_tokens": input_tokens, "output_tokens": output_tokens}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the difference between stdio and Streamable HTTP transports?"
    result = run_agent_runner(question)
    print()
    print(result["answer"])
    cost = result["input_tokens"] * 4 / 1_000_000 + result["output_tokens"] * 20 / 1_000_000
    print(f"\n[passi: {result['steps']} | token: {result['input_tokens']} in, {result['output_tokens']} out | "
          f"costo ≈ {cost:.4f} $ | stop_reason: {result['stop_reason']}]")
