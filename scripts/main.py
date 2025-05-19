import os
import logging
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
# Certifique-se de que SCOPES está definido globalmente no seu script, como antes:
# SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None

    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path} usando from_authorized_user_file...")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True)
            creds = None # Garante que creds seja None se o carregamento falhar
    else:
        logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")
        # Se token.json não existir, creds permanece None. A lógica abaixo lida com isso.

    # Tenta atualizar se creds existem, estão expirados e possuem um refresh token
    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
            # Carrega client_id, client_secret e token_uri de client_secrets.json
            # Estes são autoritativos e necessários para o mecanismo de refresh.
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh.")
                return None # Falha crítica

            with open(client_secrets_path, 'r') as f:
                client_secrets_info = json.load(f)
            
            if 'installed' not in client_secrets_info:
                logging.error(f"ERRO: Estrutura 'installed' não encontrada em {client_secrets_path}. Verifique o formato do arquivo.")
                return None # Falha crítica
            
            secrets = client_secrets_info['installed']

            # Recria o objeto Credentials com todas as informações necessárias para o refresh.
            creds_for_refresh = Credentials(
                token=None, # O token de acesso atual está expirado, não é necessário para a chamada de refresh em si
                refresh_token=creds.refresh_token, # Vem do token.json carregado
                token_uri=secrets.get('token_uri', 'https://oauth2.googleapis.com/token'), # Pega de secrets ou usa um padrão comum
                client_id=secrets.get('client_id'),
                client_secret=secrets.get('client_secret'),
                scopes=creds.scopes # Mantém os escopos originais
            )
            
            # Valida se as partes essenciais para o refresh estão presentes
            if not creds_for_refresh.client_id or not creds_for_refresh.client_secret or not creds_for_refresh.refresh_token:
                missing_parts = []
                if not creds_for_refresh.client_id: missing_parts.append("client_id (de client_secrets.json)")
                if not creds_for_refresh.client_secret: missing_parts.append("client_secret (de client_secrets.json)")
                if not creds_for_refresh.refresh_token: missing_parts.append("refresh_token (do token.json)")
                logging.error(f"ERRO: Informações cruciais para refresh faltando: {', '.join(missing_parts)}. Verifique client_secrets.json e token.json.")
                return None

            logging.info(f"Tentando refresh com: client_id={creds_for_refresh.client_id}, client_secret={'***'}, refresh_token={'***'}, token_uri={creds_for_refresh.token_uri}")
            
            request_obj = Request() # Cria um novo objeto de transporte de requisição
            creds_for_refresh.refresh(request_obj) # Realiza o refresh
            
            # Se o refresh foi bem-sucedido, substitui 'creds' antigos pelas novas credenciais atualizadas
            creds = creds_for_refresh 
            logging.info("Token de acesso atualizado com sucesso usando refresh token.")

            # Salva as credenciais atualizadas (refrescadas) de volta no token.json
            logging.info(f"Salvando token atualizado em {token_path}...")
            token_data_to_save = {
                'token': creds.token, # Este é o novo token de acesso
                'refresh_token': creds.refresh_token, # O refresh token geralmente permanece o mesmo
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret, # Agora deve estar populado
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None # Salva a expiração em formato ISO
            }
            with open(token_path, 'w') as token_file:
                json.dump(token_data_to_save, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado com sucesso.")

        except FileNotFoundError:
            logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path} durante a tentativa de refresh.", exc_info=True)
            creds = None 
        except KeyError as e:
            logging.error(f"ERRO: Estrutura inesperada no arquivo {client_secrets_path} (chave faltando: {e}). Não foi possível obter informações para refresh.", exc_info=True)
            creds = None
        except Exception as e:
            logging.error(f"ERRO: Falha desconhecida ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None 

    # Após tentar carregar e possivelmente atualizar, verifica o estado final de creds
    if not creds:
        logging.error("--- Falha crítica: Não foi possível obter ou criar credenciais válidas (token.json).")
        logging.error("Se esta é a primeira execução ou o token.json está corrompido/sem refresh_token, execute a autenticação inicial LOCALMENTE para criar um token.json válido.")
        return None

    if not creds.valid:
        logging.error("--- Falha crítica: Credenciais não são válidas e não puderam ser atualizadas.")
        logging.error("Verifique o token.json ou execute a autenticação inicial LOCALMENTE.")
        return None

    # Se chegamos aqui, creds devem ser válidas
    logging.info("--- Autenticação bem-sucedida ou token válido. Construindo serviço da API do YouTube. ---")
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube com as credenciais obtidas: {e}", exc_info=True)
        return None
