import google.oauth2.credentials
import google_auth_oauthlib.flow
import json
import base64
import os

def load_credentials(client_secret_path, token_path):
    """Carrega credenciais do YouTube a partir de arquivos Base64."""
    try:
        # 1. Decodifica com latin1 (ou outra codificação tolerante)
        with open(client_secret_path, 'r') as file:
            client_secret_content = base64.b64decode(file.read()).decode('latin1', errors='replace')  # Usando latin1 e substituindo erros
            # --- DEBUG: IMPRIME O CONTEÚDO DECODIFICADO ---
            print("-" * 20)
            print("Conteúdo decodificado (client_secret):")
            print(client_secret_content)
            print("-" * 20)

            # --- TENTATIVA de correção (remover BOM, se presente) ---
            # Verifique se há BOMs estranhos.  Se houver, REMOVA-OS!
            if client_secret_content.startswith('\xff\xfe') or client_secret_content.startswith('\xfe\xff'):
                print("BOM inválido encontrado! Removendo...")
                client_secret_content = client_secret_content[2:]  # Remove os dois primeiros bytes
            elif client_secret_content.startswith('\xef\xbb\xbf'):
                print("BOM UTF-8 encontrado! Removendo...")
                client_secret_content = client_secret_content[3:]  # Remove os três primeiros bytes

            # --- TENTATIVA de carregar o JSON (depois da correção) ---
            try:
                client_secret = json.loads(client_secret_content)
            except json.JSONDecodeError as e:
                print(f"ERRO ao decodificar JSON após remover BOM (se houver): {e}")
                print("Por favor, inspecione o JSON manualmente, corrija e tente novamente.")
                raise  # Re-lança a exceção após imprimir o erro detalhado

        # --- (O restante do código permanece o mesmo, *mas*...) ---

        # Verifica se o token já existe e está válido
        if os.path.exists(token_path):
            with open(token_path, 'r') as file:
                token_content = base64.b64decode(file.read()).decode('utf-8-sig') #Aqui já está com utf-8-sig
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
