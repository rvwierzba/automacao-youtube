import os
import argparse
import logging
import json
# from googleapiclient.discovery import build # Já importado abaixo
from google_auth_oauthlib.flow import InstalledAppFlow # Ainda necessário para carregar client_secrets para refresh
from google.auth.transport.requests import Request
# Não precisamos mais de pickle se estivermos usando token.json diretamente
# import pickle
from google.oauth2.credentials import Credentials # Importar a classe Credentials para carregar de token.json
import sys # Para sair do script em caso de erro crítico
# Importar a classe para upload de mídia (necessário para o upload)
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build # Importar build aqui


# A configuração de logging deve estar no início do arquivo (manter a que já colocamos)
# logging.basicConfig(...)

# Escopos necessários (manter)
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado
# Agora espera os caminhos para os arquivos JSON *já decodificados* criados pelo workflow
def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None # Inicializa credenciais como None

    # 1. Tenta carregar credenciais do token.json existente (decodificado pelo workflow)
    # Este arquivo foi decodificado pelo workflow a partir de canal1_token.json.base64
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path} usando from_authorized_user_file...")
            # Use from_authorized_user_file para carregar credenciais do token.json
            # Esta função lida automaticamente com a estrutura do token.json
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            # Logar aviso se o arquivo token.json estiver inválido/corrompido (como o erro 0xf3, AGORA RESOLVIDO!)
            # Ou outros erros de parsing.
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True) # Logar traceback para entender o erro de parsing
            creds = None # Garantir que creds seja None se a carga falhar
    else:
         logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")
         # Se token.json não existe, creds permanece None. O próximo bloco lida com isso.


    # 2. Se as credenciais foram carregadas mas estão expiradas, tenta refreshar
    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
             # Usa o refresh token contido no objeto creds para obter um novo access token
             # Esta chamada é NÃO INTERATIVA.
             creds.refresh(Request())
             logging.info("Token de acesso atualizado com sucesso usando refresh token.")

             # Salva as credenciais atualizadas de volta no token.json
             logging.info(f"Salvando token atualizado em {token_path}...")
             with open(token_path, 'w') as token_file:
                 # Extrai os atributos necessários do objeto Credentials para salvar no JSON
                 token_data = {
                     'token': creds.token,
                     'refresh_token': creds.refresh_token,
                     'token_uri': creds.token_uri,
                     'client_id': creds.client_id,
                     'client_secret': creds.client_secret,
                     'scopes': creds.scopes,
                     'expiry': creds.expiry.isoformat() if creds.expiry else None # Incluir data de expiração
                 }
                 json.dump(token_data, token_file, indent=4)
             logging.info(f"Arquivo {token_path} atualizado com sucesso.")

        except Exception as e:
            # Captura erros durante o processo de refresh
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None # A atualização falhou, credenciais não são válidas


    # 3. Se, após carregar e tentar refreshar, ainda não temos credenciais válidas
    #    (Isso acontece se token.json não existe, é inválido/corrompido, ou não tem refresh token válido,
    #     ou o refresh falhou).
    if not creds or not creds.valid:
         # Neste ponto, no ambiente headless, não há como prosseguir.
         # REMOVEMOS QUALQUER CHAMADA INTERATIVA COMO run_local_server OU run_console AQUI.
         logging.error("--- Falha crítica ao obter credenciais válidas após todas as tentativas não interativas. ---")
         logging.error("Necessário executar a autenticação inicial LOCALMENTE (com generate_token.py) para criar/atualizar um token.json válido com refresh token,")
         logging.error("e garantir que o arquivo canal1_token.json.base64 no repositório (ou Secret TOKEN_BASE64) contenha este token codificado CORRETAMENTE.")
         return None # Indica falha total na autenticação


    logging.info("--- Autenticação bem-sucedida. Construindo serviço da API do YouTube. ---")
    # Constrói o serviço da API do YouTube com as credenciais obtidas
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        # Captura falhas na construção do objeto de serviço da API
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube: {e}", exc_info=True)
        return None

# ... O restante do seu arquivo main.py deve ser mantido como estava (função main, bloco __main__, etc.) ...
# A função main deve chamar get_authenticated_service com os caminhos corretos:
# youtube = get_authenticated_service(client_secrets_path, token_path)
