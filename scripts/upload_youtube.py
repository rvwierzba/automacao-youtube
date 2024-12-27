#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse

import googleapiclient.discovery
import googleapiclient.http
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def load_channel_config(channel_name: str):
    config_path = os.path.join(os.path.dirname(__file__), "channels_config.json")
    if not os.path.exists(config_path):
        print("ERRO: channels_config.json não encontrado!")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for c in data.get("channels", []):
        if c["name"] == channel_name:
            return c
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="YouTube API Key")
    parser.add_argument("--channel", required=True, help="Nome do canal (channels_config.json -> name)")
    parser.add_argument("--client-secret-file", required=True, help="Conteúdo JSON do client_secret")
    parser.add_argument("--token-file", required=True, help="Conteúdo JSON do token OAuth2")
    parser.add_argument("--video-file", default="video_final.mp4", help="Arquivo de vídeo")
    args = parser.parse_args()

    # 1) Carregar config do canal
    channel_config = load_channel_config(args.channel)
    if not channel_config:
        print(f"Canal '{args.channel}' não encontrado no channels_config.json")
        sys.exit(1)

    # 2) Salvar JSONs
    with open("temp_client_secret.json", "w", encoding="utf-8") as f:
        f.write(args.client_secret_file)
    with open("temp_token.json", "w", encoding="utf-8") as f:
        f.write(args.token_file)

    # 3) Credenciais
    creds = None
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    try:
        creds = Credentials.from_authorized_user_file("temp_token.json", scopes)
    except Exception as e:
        print("Erro ao carregar temp_token.json:", e)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Token inválido ou expirado e sem refresh_token.")
            sys.exit(1)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    # 4) Montar snippet do vídeo
    # Title com timestamp
    title_str = channel_config["title"] + " - " + time.strftime("%Y-%m-%d %H:%M:%S")
    desc_str = channel_config["description"]
    tags = channel_config["keywords"].split(",")

    body = {
        "snippet": {
            "title": title_str,
            "description": desc_str,
            "tags": tags,
            "categoryId": "28"  # ex: Science & Technology
        },
        "status": {
            "privacyStatus": "private"  # ou "public"
        }
    }

    print(f"Subindo vídeo: {args.video_file}")
    media_body = googleapiclient.http.MediaFileUpload(args.video_file, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media_body
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Progresso do upload: {int(status.progress() * 100)}%")

    if "id" in response:
        video_id = response["id"]
        print(f"Vídeo publicado com sucesso: https://youtu.be/{video_id}")
    else:
        print("Erro ao publicar vídeo:", response)
        sys.exit(1)

if __name__ == "__main__":
    main()
