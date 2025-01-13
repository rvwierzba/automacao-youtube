import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging

def upload_to_youtube(client_secret_path, token_path, video_path, title, description):
    # Carregar credenciais da conta de serviço
    with open(client_secret_path, 'r') as f:
        client_secret = json.load(f)

    credentials = service_account.Credentials.from_service_account_info(
        client_secret, scopes=['https://www.googleapis.com/auth/youtube.upload']
    )

    youtube = build('youtube', 'v3', credentials=credentials)

    # Preparar o arquivo de vídeo para upload
    media = MediaFileUpload(video_path, resumable=True)

    # Criar a solicitação de upload
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["automação", "youtube", "vídeo"],
                "categoryId": "22"  # Categoria: People & Blogs
            },
            "status": {
                "privacyStatus": "public"  # ou "private" ou "unlisted"
            }
        },
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logging.info(f"Upload progress: {int(status.progress() * 100)}%")

    logging.info(f"Upload concluído: {response['id']}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--gemini-api', required=True)
    parser.add_argument('--youtube-channel', required=True)
    parser.add_argument('--pixabay-api', required=True)
    parser.add_argument('--quantidade', type=int, required=True)
    args = parser.parse_args()

    # Definir caminhos para credenciais
    client_secret_path = 'credentials/canal1_client_secret.json'
    token_path = 'credentials/canal1_token.json'
    video_path = 'video_final.mp4'

    # Configurar logging
    logging.basicConfig(level=logging.INFO)

    # Chamar função de upload
    upload_to_youtube(client_secret_path, token_path, video_path, 'Título do Vídeo', 'Descrição do Vídeo')
