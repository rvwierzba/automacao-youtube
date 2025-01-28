import json
import base64
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy.editor import VideoFileClip, AudioFileClip
import google.auth  # Importação necessária
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

logger = logging.getLogger(__name__)

#... (restante do código)...

def upload_video_to_youtube(video_file, title, description, tags, subtitles_file, client_secret_path, token_path):
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    
    # Carregar as credenciais do client_secret
    client_secret = load_json_from_base64(client_secret_path)  # Se ainda for usar base64
    
    # Fluxo de autenticação (similar a scripts/youtube_auth.py)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes)
            creds = flow.run_console()
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    youtube = build('youtube', 'v3', credentials=creds)

    #... (resto do código para upload)...

def main(client_secret_path, token_path, video_title, audio_file):
    #... outras funções...

    # Fazer upload para o YouTube
    upload_video_to_youtube(
        output_video_file, 
        video_title, 
        "Descrição do vídeo", 
        ["tag1", "tag2"], 
        subtitles_file,
        client_secret_path,  # Passar o caminho do client_secret
        token_path  # Passar o caminho do token
    )

#... (resto do código)...
