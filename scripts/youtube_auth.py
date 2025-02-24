import google.oauth2.credentials
import google_auth_oauthlib.flow
import json
import base64
import os

def load_credentials(client_secret_path, token_path):
    """Carrega credenciais do YouTube a partir de arquivos Base64,
       tentando corrigir problemas de codificação."""
    try:
        # 1. Decodifica o client_secret
        with open(client_secret_path, 'r') as file:
            client_secret_content = base64.b64decode(file.read())

        # 2. Tenta decodificar como UTF-8, removendo BOM se necessário
        try:
            client_secret_text = client_secret_content.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Se UTF-8 falhar, tenta outras codificações comuns
            for encoding in ['utf-16le', 'utf-16be', 'utf-32le', 'utf-32be', 'latin-1', 'cp1252']:
                try:
                    client_secret_text = client_secret_content.decode(encoding)
                    print(f"Decodificado com sucesso usando {encoding}")
                    break  # Sai do loop se a decodificação funcionar
                except UnicodeDecodeError:
                    continue  # Tenta a próxima codificação
            else:  # Se nenhuma codificação funcionar...
                raise ValueError("Não foi possível decodificar o client_secret com nenhuma codificação conhecida.")

        client_secret = json.loads(client_secret_text)

        # --- (Restante do código permanece o MESMO) ---
        # Verifica se o token já existe e está válido
        if os.path.exists(token_path):
            with open(token_path, 'r') as file:
                token_content = base64.b64decode(file.read()).decode('utf-8-sig')  # Decodifica, remove BOM
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
