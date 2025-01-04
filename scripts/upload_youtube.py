# scripts/upload_youtube.py

import argparse
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

# Scopes necessários para a API do YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def upload_video(file, client_secret, token, title, description, category, tags):
    """
    Faz o upload do vídeo para o YouTube usando OAuth 2.0 com Refresh Token.
    """
    creds = None
    if os.path.exists(token):
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    # Se não houver credenciais válidas, inicie o fluxo de autenticação
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao renovar o token: {e}")
                exit(1)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            creds = flow.run_console()
        # Salve as credenciais para a próxima execução
        with open(token, 'w') as token_file:
            token_file.write(creds.to_json())

    try:
        youtube = googleapiclient.discovery.build(
            "youtube", "v3", credentials=creds
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "categoryId": category,
                    "description": description,
                    "title": title,
                    "tags": tags.split(',')
                },
                "status": {
                    "privacyStatus": "public"  # Pode ser ajustado para 'private' ou 'unlisted'
                }
            },
            media_body=MediaFileUpload(file, chunksize=-1, resumable=True)
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploading... {int(status.progress() * 100)}%")
        print(f"Upload Complete! Video ID: {response['id']}")
    except googleapiclient.errors.HttpError as e:
        print(f"Erro ao fazer upload: {e}")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="Fazer upload de vídeo no YouTube.")
    parser.add_argument("--video-file", required=True, help="Caminho para o arquivo de vídeo.")
    parser.add_argument("--client-secret-file", required=True, help="Caminho para client_secret.json.")
    parser.add_argument("--token-file", required=True, help="Caminho para token.json.")
    parser.add_argument("--title", required=True, help="Título do vídeo.")
    parser.add_argument("--description", required=True, help="Descrição do vídeo.")
    parser.add_argument("--category", required=True, help="ID da categoria do vídeo.")
    parser.add_argument("--tags", required=True, help="Tags do vídeo, separadas por vírgula.")
    args = parser.parse_args()

    # Verificar se o arquivo de vídeo existe
    if not os.path.exists(args.video_file):
        print(f"Erro: O arquivo de vídeo '{args.video_file}' não existe.")
        exit(1)

    upload_video(
        args.video_file,
        args.client_secret_file,
        args.token_file,
        args.title,
        args.description,
        args.category,
        args.tags
    )

if __name__ == "__main__":
    main()
