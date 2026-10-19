"""Riga di comando del progetto:  python src/cli.py <comando> ..."""
import argparse

from config import TOP_K
from search import search_docs
from rag import answer


def format_hits(hits: list[dict]) -> str:
    s = ""
    for i, hit in enumerate(hits, start=1):
        preview = hit["text"][:200].replace("\n", " ")        # i primi 200 caratteri, su una riga
        s += f"[{i}] {hit['score']}  {hit['section_title']} — {hit['page_title']}\n"
        s += f"    {hit['url']}\n"
        s += f"    {preview}\n\n"
        
    return s

def format_answer(result: dict) -> str:
    """La risposta di Claude, seguita dai chunk che gli abbiamo passato e dal costo della chiamata."""
    s = result["answer"] + "\n\n"
    s += "--- Documenti passati a Claude ---\n"
    for i, hit in enumerate(result["sources"], start=1):
        s += f"[{i}] {hit['score']}  {hit['url']}\n"         
    cost = result["input_tokens"] * 4 / 1_000_000 + result["output_tokens"] * 20 / 1_000_000   # prezzi di Opus 5.5
    s += (f"\n[token: {result['input_tokens']} in, {result['output_tokens']} out | "
          f"costo ≈ {cost:.4f} $ | stop_reason: {result['stop_reason']}]")
    return s

def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Docs Assistant")     # il "programma" nel suo insieme
    subparsers = parser.add_subparsers(dest="command", required=True)      # i sotto-comandi: search, (poi ask, chat...)

    search_parser = subparsers.add_parser("search", help="Ricerca semantica nella documentazione")
    search_parser.add_argument("query", help="La domanda, tra virgolette")                     # argomento obbligatorio
    search_parser.add_argument("-k", type=int, default=TOP_K, help="Quanti risultati (default: 5)")   # opzione facoltativa

    ask_parser = subparsers.add_parser("ask", help="Fai una domanda: ricerca + risposta di Claude (costa)")
    ask_parser.add_argument("question", help="La domanda, tra virgolette")
    ask_parser.add_argument("-k", type=int, default=TOP_K, help="Quanti chunk passare a Claude (default: 5)")

    args = parser.parse_args()          # legge cosa hai scritto nel terminale; se è sbagliato, stampa l'errore ed esce

    if args.command == "search":
        print(format_hits(search_docs(args.query, args.k)))
    elif args.command == "ask":
        print(format_answer(answer(args.question, args.k)))


if __name__ == "__main__":
    main()