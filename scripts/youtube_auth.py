# scripts/youtube_auth.py

import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import json
import pickle

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def load_credentials(client_secret_path, token_path):
    creds = None
    # Se o token já existir, carregue-o
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    # Se não houver credenciais válidas disponíveis, faça o login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logging.info("Token atualizado com sucesso.")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            logging.info("Autenticação OAuth2 realizada com sucesso.")
        # Salve as credenciais para a próxima execução
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    youtube = build('youtube', 'v3', credentials=creds)
    return youtube

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Autenticar com a API do YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser autenticado.')

    args = parser.parse_args()

    config_path = 'config/channels_config.json'

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        canais = config['channels']
    except Exception as e:
        logging.error(f"Erro ao carregar o arquivo de configuração: {e}")
        raise

    canal_config = next((c for c in canais if c['name'] == args.channel), None)

    if not canal_config:
        logging.error(f"Canal {args.channel} não encontrado na configuração.")
        raise ValueError(f"Canal {args.channel} não encontrado.")

    client_secret_file = os.path.join('credentials', canal_config['client_secret_file'])
    token_file = os.path.join('credentials', canal_config['token_file'])

    youtube = load_credentials(client_secret_file, token_file)
    logging.info(f"Autenticação concluída para o canal {args.channel}.")
