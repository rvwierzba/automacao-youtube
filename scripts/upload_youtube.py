#!/usr/bin/env python3

import os
import sys
import json
import argparse
import time

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def load_channel_config(name: str):
    with open(os.path.join(os.path.dirname(__file__), "channels_config.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    for c in data["channels"]:
        if c["name"] == name:
            return c
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="YouTube API Key")
    parser.add_argument("--channel", required=True, help="Channel name or ID (ex: fizzquirk)")
    parser.add_argument("--client-secret-file", required=True, help="Conteúdo ou path do client secret JSON")
    parser.add_argument("--token-file", required=True, help="Conteúdo ou path do token JSON")
    parser.add_argument("--video-file", default="video_final.mp4", help="Caminho do vídeo gerado")
    args = parser.parse_args()

    channel_config = load_channel_config(args.channel)
    if not channel_config:
        print(f"Canal {args.channel} não encontrado em channels_config.json!")
        sys.exit(1)

    # Caso o --client-secret-file e --token-file SEJAM O CONTEÚDO do JSON,
    # você pode salvar em disco e usar. Exemplo:
    with open("temp_client_secret.json", "w", encoding="utf-8") as f:
        f.write(args.client_secret_file)
    with open("temp_token.json", "w", encoding="utf-8") as f:
        f.write(args.token_file)

    # Então, credencia-se com googleapiclient
    creds = None
    # Carrega o token
    try:
        creds = Credentials.from_authorized_user_file("temp_token.json", ["https://www.googleapis.com/auth/youtube.upload"])
    except:
        pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Token inválido ou expirado. Necessária nova autenticação.")
            # Ou busque outro fluxo de OAuth2 aqui.
            sys.exit(1)

    youtube = build("youtube", "v3", credentials=creds)

    # Título, descrição etc. do canal, do channels_config.json
    title_str = channel_config["title"] + " " + time.strftime("%Y-%m-%d %H:%M:%S")
    desc_str = channel_config["description"]
    tags_str = channel_config["keywords"].split(",")

    print(f"Enviando vídeo '{args.video_file}' para canal '{channel_config['name']}'...")

    request_body = {
        "snippet": {
            "title": title_str,
            "description": desc_str,
            "tags": tags_str,
            "categoryId": "28"  # Exemplo "Science & Technology"
        },
        "status": {
            "privacyStatus": "private"  # ou "public", "unlisted"
        }
    }

    media_body = googleapiclient.http.MediaFileUpload(args.video_file, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_body
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress()*100)}%")

    if "id" in response:
        print(f"Vídeo enviado com sucesso: https://youtube.com/watch?v={response['id']}")
    else:
        print("Erro ao enviar vídeo:", response)
        sys.exit(1)


if __name__ == "__main__":
    main()
