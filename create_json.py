import json
import base64
import os

# Dados para o channels_config.json (AJUSTE CONFORME NECESSÁRIO)
channels_config_data = {
  "channels": [
    {
      "name": "fizzquirk",  # SUBSTITUA PELO NOME DO SEU CANAL
      "client_secret_file": "canal1_client_secret.json.base64",
      "token_file": "canal1_token.json.base64",  # O token será gerado, mantenha o nome
      "title": "Título de Exemplo",  # SUBSTITUA
      "description": "Descrição de Exemplo",  # SUBSTITUA
      "keywords": "palavra1, palavra2, palavra3"  # SUBSTITUA
    }
  ]
}

# --- COLE O CONTEÚDO *COMPLETO* DO SEU client_secret.json AQUI ---
#     (aquele que você BAIXOU do Google Cloud, SEM base64)
client_secret_data = """
{
"COLE O CONTEÚDO AQUI"
}
"""
# ---  FIM DA COLAGEM ---.  MANTENHA AS TRÊS ASPAS DUPLAS.


# --- Cria os diretórios se não existirem ---
os.makedirs("config", exist_ok=True)
os.makedirs("credentials", exist_ok=True)

# --- Salva channels_config.json (UTF-8, sem BOM) ---
with open("config/channels_config.json", "w", encoding="utf-8") as f:
    json.dump(channels_config_data, f, indent=2)  # Formata o JSON

# --- Salva client_secret.json (UTF-8, sem BOM) ---
with open("credentials/client_secret.json", "w", encoding="utf-8") as f:
    f.write(client_secret_data) # Escreve a string *diretamente*


# --- Cria os arquivos .base64 ---
def encode_to_base64(input_file, output_file):
    with open(input_file, 'rb') as infile:  # Abre em modo binário ('rb')
        file_content = infile.read() # Lê como bytes
    encoded_content = base64.b64encode(file_content).decode('ascii')  # Codifica para Base64
    with open(output_file, 'w') as outfile:
        outfile.write(encoded_content) # Escreve a string Base64.

encode_to_base64("credentials/client_secret.json", "credentials/canal1_client_secret.json.base64")
# Não gere token.json.base64 agora. O main.py/youtube_auth.py fará isso.

print("Arquivos JSON e Base64 criados/atualizados com sucesso!")
