import google.oauth2.credentials
import google_auth_oauthlib.flow
import json
import base64
import os

# --- VERSÃO 1:  Se você usar arquivos .base64 (MANTENHA ESTA, COMENTE A OUTRA) ---
def load_credentials(client_secret_path, token_path):
    """Carrega credenciais do YouTube a partir de arquivos Base64."""
    try:
        # Decodifica client_secret
        with open(client_secret_path, 'r') as file:
            client_secret_content = base64.b64decode(file.read()).decode('utf-8')
            client_secret = json.loads(client_secret_content)


        # Verifica se o token já existe e está válido
        if os.path.exists(token_path):
            with open(token_path, 'r') as file:
                token_content = base64.b64decode(file.read()).decode('utf-8')
                credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(
                    json.loads(token_content),
                    scopes=client_secret['installed']['scopes'] if 'installed' in client_secret else client_secret['web']['scopes']
                )
                if credentials.valid:
                    return credentials

        # Se o token não existe ou não é válido, faz o fluxo de autenticação
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
            client_secret,
            scopes=client_secret['installed']['scopes'] if 'installed' in client_secret else client_secret['web']['scopes']
        )
        credentials = flow.run_local_server(port=0)


        # Salva o token (codificado em Base64)
        with open(token_path, 'w') as file:
            token_json = credentials.to_json()
            token_base64 = base64.b64encode(token_json.encode('utf-8')).decode('ascii')
            file.write(token_base64)

        return credentials

    except Exception as e:
        print(f"Erro ao carregar ou criar credenciais: {e}")
        raise

# --- VERSÃO 2: Se você usar arquivos .json PUROS (COMENTE ESTA, SE USAR A DE CIMA) ---
# def load_credentials(client_secret_path, token_path):
#     """Carrega credenciais do YouTube a partir de arquivos JSON puros."""
#     try:
#         # Carrega client_secret
#         with open(client_secret_path, 'r') as file:
#             client_secret = json.load(file)
#
#         # Verifica se o token existe e é válido
#         if os.path.exists(token_path):
#             with open(token_path, 'r') as file:
#                 credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(
#                     json.load(file),
#                      scopes=client_secret['installed']['scopes'] if 'installed' in client_secret else client_secret['web']['scopes']
#                 )
#             if credentials.valid:
#                 return credentials
#
#         # Se o token não existe ou não é válido, autentica
#         flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
#             client_secret,
#             scopes=client_secret['installed']['scopes'] if 'installed' in client_secret else client_secret['web']['scopes']
#         )
#         credentials = flow.run_local_server(port=0)
#
#         # Salva o token (JSON puro)
#         with open(token_path, 'w') as file:
#             json.dump(json.loads(credentials.to_json()), file, indent=2)  # Salva formatado
#
#         return credentials
#
#     except Exception as e:
#         print(f"Erro ao carregar ou criar credenciais: {e}")
#         raise
