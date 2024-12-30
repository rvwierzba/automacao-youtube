import argparse
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

def upload_video(video_file, client_secret_file, token_file, title, description, category, tags):
    # Carrega as credenciais
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes=["https://www.googleapis.com/auth/youtube.upload"])
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Token renovado com sucesso.")
        else:
            raise Exception("Credenciais inválidas ou expiradas.")
    
    youtube = build('youtube', 'v3', credentials=creds)
    
    request_body = {
        'snippet': {
            'categoryId': category,
            'title': title,
            'description': description,
            'tags': [tag.strip() for tag in tags.split(",")]  # Separar por vírgula e remover espaços
        },
        'status': {
            'privacyStatus': 'public',
        }
    }
    
    media = MediaFileUpload(video_file, mimetype='video/mp4', resumable=True)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress() * 100)}%")
    print(f"Upload Complete! Video ID: {response.get('id')}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-file", required=True, help="Caminho para o arquivo de vídeo.")
    parser.add_argument("--client-secret-file", required=True, help="Caminho para o arquivo de segredos do cliente.")
    parser.add_argument("--token-file", required=True, help="Caminho para o arquivo de token.")
    parser.add_argument("--title", required=True, help="Título do vídeo.")
    parser.add_argument("--description", required=True, help="Descrição do vídeo.")
    parser.add_argument("--category", required=True, help="Categoria do vídeo.")
    parser.add_argument("--tags", required=True, help="Tags do vídeo, separadas por vírgula.")
    args = parser.parse_args()
    
    upload_video(
        video_file=args.video_file,
        client_secret_file=args.client_secret_file,
        token_file=args.token_file,
        title=args.title,
        description=args.description,
        category=args.category,
        tags=args.tags
    )

if __name__ == "__main__":
    main()
