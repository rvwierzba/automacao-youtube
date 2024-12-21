# scripts/upload_youtube.py

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging

def upload_video_to_youtube(youtube, video_path, title, description, category_id="22", privacy_status="public"):
    try:
        logging.info(f"Iniciando upload para o YouTube: {title}")
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["automacao", "video", "youtube"],
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status
                }
            },
            media_body=MediaFileUpload(video_path, resumable=True)
        )
        response = request.execute()
        logging.info(f"Vídeo enviado para o YouTube com sucesso! ID: {response['id']}")
    except Exception as e:
        logging.error(f"Erro no upload para o YouTube: {e}")
        raise
