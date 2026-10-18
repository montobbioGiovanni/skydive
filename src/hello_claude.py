import anthropic
from config import CLAUDE_MODEL # importare config fa eseguire in automatico load_dotenv()

'''Questo è l'oggetto che fa le richieste HTTP. Si può pensare come un HttpClient
 già configurato per l'API di anthropic'''
client = anthropic.Anthropic() # senza argomenti: legge ANTHROPIC_API_KEY dall'ambiente da solo

response = client.messages.create(
    model=  CLAUDE_MODEL, 
    max_tokens=1024, #tetto ai token
    system="Sei un assistente conciso. Rispondi come un pirata", # istruzioni generali
    messages=[
        {
            "role":"user", "content": "Cos'è un token, in due frasi" # la domanda
        }
    ],
)

# stampa della risposta
for block in response.content:
    if block.type == "text": # prende solo la risposta effettiva, response.content è una lista di blocchi
        print(block.text)

print("stop_reason:", response.stop_reason)
print("token in input:", response.usage.input_tokens)
print("token in output:", response.usage.output_tokens)