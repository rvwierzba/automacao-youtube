# scripts/main.py

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging
import argparse
import requests

def upload_to_youtube(client_secret_path, video_path, title, description):
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

def buscar_imagens_pixabay(api_key, quantidade):
    url = "https://pixabay.com/api/"
    params = {
        'key': api_key,
        'per_page': quantidade,
        'safesearch': 'true'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        dados = response.json()
        # Processar as imagens conforme necessário
        logging.info(f"Imagens obtidas: {len(dados.get('hits', []))}")
    else:
        logging.error(f"Falha ao buscar imagens: {response.status_code}")
        response.raise_for_status()

def main():
    parser = argparse.ArgumentParser(description='Script de Automação para YouTube')
    parser.add_argument('--gemini-api', required=True, help='Chave da API Gemini')
    parser.add_argument('--youtube-channel', required=True, help='Canal do YouTube')
    parser.add_argument('--pixabay-api', required=True, help='Chave da API Pixabay')
    parser.add_argument('--quantidade', type=int, required=True, help='Quantidade de itens a processar')
    args = parser.parse_args()

    # Definir caminhos para credenciais e vídeo
    client_secret_path = 'credentials/service_account.json'
    video_path = 'video_final.mp4'

    # Configurar logging
    logging.basicConfig(level=logging.INFO)

    # Chamar funções de automação
    try:
        buscar_imagens_pixabay(args.pixabay_api, args.quantidade)
        upload_to_youtube(client_secret_path, video_path, 'Título do Vídeo', 'Descrição do Vídeo')
    except Exception as e:
        logging.error(f"Erro durante a execução: {e}")
        exit(1)

if __name__ == "__main__":
    main()
