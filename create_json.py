import json
import base64
import os

# Dados para o channels_config.json (AJUSTE CONFORME NECESSÁRIO)
channels_config_data = {
  "channels": [
    {
      "name": "fizzquirk",  # SUBSTITUA PELO NOME DO SEU CANAL
      "client_secret_file": "canal1_client_secret.json.base64",
      "token_file": "canal1_token.json.base64",  # O token será gerado
      "title": "Título de Exemplo",  # SUBSTITUA
      "description": "Descrição de Exemplo",  # SUBSTITUA
      "keywords": "palavra1, palavra2, palavra3"  # SUBSTITUA
    }
  ]
}

# --- COLE O CONTEÚDO *COMPLETO* DO SEU NOVO client_secret.json AQUI ---
#     (aquele que você BAIXOU do Google Cloud, SEM base64)
#     DEVE SER UM JSON VÁLIDO!
client_secret_data = """
{
  "installed":{
    
    "client_id":"314158891397-q0qo0cdvu97i0g0128udmkamdo636je9.apps.googleusercontent.com",
    "project_id":"automacaoyoutube-442317",
    "auth_uri":"https://accounts.google.com/o/oauth2/auth",
    "token_uri":"https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
    "client_secret":"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",
    "redirect_uris":["http://localhost"]
  }
}
"""
# --- FIM DA COLAGEM ---.  MANTENHA AS TRÊS ASPAS DUPLAS.

# --- Cria os diretórios se não existirem ---
os.makedirs("config", exist_ok=True)
os.makedirs("credentials", exist_ok=True)

# --- Salva channels_config.json (UTF-8, sem BOM) ---
with open("config/channels_config.json", "w", encoding="utf-8") as f:
    json.dump(channels_config_data, f, indent=2)  # Formata o JSON

# --- Salva client_secret.json (UTF-8, sem BOM) ---
# Agora usando json.dumps, que é o correto!
try:
    client_secret = json.loads(client_secret_data)  # CONVERTE a string em um objeto JSON
    with open("credentials/client_secret.json", "w", encoding="utf-8") as f:
        json.dump(client_secret, f, indent=2) # Salva o objeto JSON como arquivo, formatado.
except json.JSONDecodeError as e:
    print(f"ERRO CRÍTICO: O JSON que você colou em client_secret_data é INVÁLIDO: {e}")
    print("CORRIJA O JSON ANTES DE CONTINUAR. Use um validador de JSON online se necessário.")
    exit(1) # Sai do script com erro.  Não adianta continuar se o JSON estiver errado.

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
