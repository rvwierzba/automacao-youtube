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

def load_json_from_base64(file_path):
    with open(file_path, 'r') as file:
        base64_content = file.read()
    json_content = base64.b64decode(base64_content).decode('utf-8')
    return json.loads(json_content)

def validate_client_secret(client_secret):
    # Verifica apenas os campos que você realmente tem
    required_fields = ['client_email', 'client_id']
    if 'installed' in client_secret:
        for field in required_fields:
            if field not in client_secret['installed']:
                logger.error(f"Erro: Campo '{field}' está ausente no client_secret.")
                raise ValueError(f"Campo '{field}' está ausente no client_secret.")
    else:
        logger.error("Erro: Estrutura de client_secret inválida.")
        raise ValueError("Estrutura de client_secret inválida.")

def create_video_with_audio(video_title, audio_file, output_file):
    clip = VideoFileClip("path/to/your/image.mp4")  # Substitua pelo caminho correto da sua imagem/vídeo
    audio = AudioFileClip(audio_file)
    final_clip = clip.set_audio(audio)
    final_clip.write_videofile(output_file, codec='libx264')

def create_subtitles(video_title, subtitles_file):
    with open(subtitles_file, 'w') as f:
        f.write("1\n00:00:00,000 --> 00:00:05,000\nExemplo de legenda em inglês\n\n")  # Exemplo

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

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '22'  # Categoria padrão (People & Blogs)
        },
        'status': {
            'privacyStatus': 'public'  # ou 'private' ou 'unlisted'
        }
    }

    media = MediaFileUpload(video_file, mimetype='video/mp4')
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = request.execute()

    # Adiciona legendas (implementação a ser feita)
    # caption_body = {
    #     'snippet': {
    #         'videoId': response['id'],
    #         'language': 'en',
    #         'name': 'Legendas em Inglês',
    #         'isDraft': False
    #     }
    # }
    # youtube.captions().insert(part='snippet', body=caption_body, media_body=subtitles_file).execute()

def main(client_secret_path, token_path, video_title, audio_file):
    client_secret = load_json_from_base64(client_secret_path)
    token = load_json_from_base64(token_path)

    # Validar client_secret
    validate_client_secret(client_secret)

    # Criar vídeo com áudio
    output_video_file = "output_video.mp4"
    create_video_with_audio(video_title, audio_file, output_video_file)

    # Criar legendas
    subtitles_file = "subtitles.srt"
    create_subtitles(video_title, subtitles_file)

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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Processar credenciais do YouTube e fazer upload de vídeo.')
    parser.add_argument('--client_secret_path', required=True, help='Caminho para o client_secret em base64')
    parser.add_argument('--token_path', required=True, help='Caminho para o token em base64')
    parser.add_argument('--video_title', required=True, help='Título do vídeo')
    parser.add_argument('--audio_file', required=True, help='Caminho para o arquivo de áudio')
    args = parser.parse_args()
    main(args.client_secret_path, args.token_path, args.video_title, args.audio_file)
