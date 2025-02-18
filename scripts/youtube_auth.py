import os
import json
import base64
import logging

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def load_credentials(client_secret_path, token_path):
    """
    Carrega as credenciais do OAuth2.
    """
    # Carrega o JSON decodificando o base64
    with open(client_secret_path, 'r') as file:
        base64_content = file.read()
    json_content = base64.b64decode(base64_content).decode('utf-8')
    client_secret = json.loads(json_content)  # client_secret agora é um dicionário

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            logging.error(f"Erro ao carregar o token: {e}")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Erro ao atualizar o token: {e}")
                creds = None
            if not creds:
                # Usa from_client_config em vez de from_client_secrets_file
                flow = InstalledAppFlow.from_client_config(client_secret, SCOPES)
                creds = flow.run_console()
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
    return creds
