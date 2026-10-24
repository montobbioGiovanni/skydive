"""Server MCP: espone la ricerca nella documentazione come strumento standard, usabile da qualsiasi client MCP.

Non chiama Claude: esegue solo la ricerca (locale e gratuita). Il modello sta nel client (es. Claude Code).
"""
from mcp.server import MCPServer

import search                       #  così possiamo chiamare il nostro tool "search_docs"
from rag import build_context       #

mcp = MCPServer("mcp-docs")         # il nome con cui il server si presenta ai client


@mcp.tool()                         # registra la funzione come strumento MCP: nome dalla funzione, schema dai type hint
async def search_docs(query: str) -> str:
    """Search the official MCP (Model Context Protocol) and Claude Agent SDK documentation.

    Returns the 5 most relevant excerpts, each with its source URL. Works best with short queries in English.
    Use it for questions about MCP servers, clients, transports, tools, and the Claude Agent SDK.

    Args:
        query: Short search query in English, e.g. 'stdio transport' or 'register a tool in a Python server'
    """
    return build_context(search.search_docs(query))


if __name__ == "__main__":
    mcp.run(transport="stdio")      # stdio: il client ci avvia come sottoprocesso e ci parla su stdin/stdout