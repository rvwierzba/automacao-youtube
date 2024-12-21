# scripts/youtube_auth.py

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import json
from dotenv import load_dotenv

load_dotenv()

def authenticate_youtube(client_secret_path, token_path):
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    credentials = flow.run_local_server(port=0)
    
    # Salvar as credenciais para reutilização
    with open(token_path, 'w') as token_file:
        token_file.write(credentials.to_json())
    
    print(f"Autenticação concluída para {client_secret_path}. Token salvo em {token_path}.")

def load_credentials(client_secret_path, token_path):
    if os.path.exists(token_path):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/youtube.upload'])
        youtube = build('youtube', 'v3', credentials=creds)
        return youtube
    else:
        authenticate_youtube(client_secret_path, token_path)
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/youtube.upload'])
        youtube = build('youtube', 'v3', credentials=creds)
        return youtube

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Autenticação para canal do YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal conforme definido em channels_config.json')
    args = parser.parse_args()
    
    channel_name = args.channel
    
    # Carregar configurações dos canais
    config_path = os.path.join('config', 'channels_config.json')
    if not os.path.exists(config_path):
        print(f"Arquivo de configuração '{config_path}' não encontrado.")
        exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    channels = config.get('channels', [])
    channel = next((c for c in channels if c['name'] == channel_name), None)
    
    if not channel:
        print(f"Canal '{channel_name}' não encontrado na configuração.")
        exit(1)
    
    client_secret_file = os.path.join('credentials', channel['client_secret_file'])
    token_file = os.path.join('credentials', channel['token_file'])
    
    if not os.path.exists(client_secret_file):
        print(f"Arquivo de client secret '{client_secret_file}' não encontrado.")
        exit(1)
    
    authenticate_youtube(client_secret_file, token_file)
