"""Riga di comando del progetto:  python src/cli.py <comando> ..."""
import argparse

from config import TOP_K
from search import search_docs


def format_hits(hits: list[dict]) -> str:
    s = ""
    for i, hit in enumerate(hits, start=1):
        preview = hit["text"][:200].replace("\n", " ")        # i primi 200 caratteri, su una riga
        s += f"[{i}] {hit['score']}  {hit['section_title']} — {hit['page_title']}\n"
        s += f"    {hit['url']}\n"
        s += f"    {preview}\n\n"
        
    return s


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Docs Assistant")     # il "programma" nel suo insieme
    subparsers = parser.add_subparsers(dest="command", required=True)      # i sotto-comandi: search, (poi ask, chat...)

    search_parser = subparsers.add_parser("search", help="Ricerca semantica nella documentazione")
    search_parser.add_argument("query", help="La domanda, tra virgolette")                     # argomento obbligatorio
    search_parser.add_argument("-k", type=int, default=TOP_K, help="Quanti risultati (default: 5)")   # opzione facoltativa

    args = parser.parse_args()          # legge cosa hai scritto nel terminale; se è sbagliato, stampa l'errore ed esce

    if args.command == "search":
        print(format_hits(search_docs(args.query, args.k)))


if __name__ == "__main__":
    main()