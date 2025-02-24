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
# Cole o JSON *válido*, baixado do Google Cloud, formatado.
# Use um validador de JSON online se tiver dúvidas.
client_secret_data = {
    "installed": {
        "client_id": "SEU CLIENT ID AQUI",
        "project_id": "SEU PROJECT ID AQUI",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "SEU CLIENT SECRET AQUI",
        "redirect_uris": ["SEU REDIRECT URI AQUI"]  # Use uma lista, mesmo com um só
    }
}
# --- FIM DA COLAGEM ---


# --- Cria os diretórios se não existirem ---
os.makedirs("config", exist_ok=True)
os.makedirs("credentials", exist_ok=True)

# --- Salva channels_config.json (UTF-8, sem BOM) ---
with open("config/channels_config.json", "w", encoding="utf-8") as f:
    json.dump(channels_config_data, f, indent=2)  # Formata o JSON

# --- Salva client_secret.json (UTF-8, sem BOM) ---
with open("credentials/client_secret.json", "w", encoding="utf-8") as f:
    json.dump(client_secret_data, f, indent=2)  # Salva como JSON formatado


# --- Cria os arquivos .base64 ---
def encode_to_base64(input_file, output_file):
    with open(input_file, 'rb') as infile:  # Abre em modo binário ('rb')
        file_content = infile.read()  # Lê como bytes
    encoded_content = base64.b64encode(file_content).decode('ascii')  # Codifica para Base64
    with open(output_file, 'w') as outfile:
        outfile.write(encoded_content)  # Escreve a string Base64.

encode_to_base64("credentials/client_secret.json", "credentials/canal1_client_secret.json.base64")
# Não gere token.json.base64 agora.  O main.py/youtube_auth.py fará isso.

print("Arquivos JSON e Base64 criados/atualizados com sucesso!")
