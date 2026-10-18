import os
from dotenv import load_dotenv

load_dotenv() # cerca il file .env e ne carica le variabili


def _required(name:str) -> str:
    '''funzione che legge una variabile obbligatoria e restituisce un messaggio di errore se non è presente.
 Si mette il _ davanti per indicare che è una funzione interna a questo file, da non usare fuori.
'''
    value = os.getenv(name) # legge la variabile
    if not value:
        raise RuntimeError(f"Variabile mancante nel file .env: {name}")
    return value

ANTHROPIC_API_KEY = _required("ANTHROPIC_API_KEY")   # la leggiamo solo per controllare che ci sia
CLAUDE_MODEL = _required("CLAUDE_MODEL")             # es. "claude-opus-5-5"