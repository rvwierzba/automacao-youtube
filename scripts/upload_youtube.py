# scripts/upload_youtube.py

import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def upload_video_to_youtube(youtube, video_path, title, description, category_id=22, keywords=""):
    try:
        logging.info(f"Iniciando upload do vídeo: {video_path}")

        request_body = {
            'snippet': {
                'categoryId': category_id,
                'title': title,
                'description': description,
                'tags': [tag.strip() for tag in keywords.split(",")] if keywords else []
            },
            'status': {
                'privacyStatus': 'public',  # Pode ser 'public', 'private' ou 'unlisted'
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logging.info(f"Progresso do upload: {int(status.progress() * 100)}%")

        logging.info(f"Vídeo enviado com sucesso. ID do Vídeo: {response['id']}")

    except Exception as e:
        logging.error(f"Erro ao enviar o vídeo para o YouTube: {e}")
        raise
