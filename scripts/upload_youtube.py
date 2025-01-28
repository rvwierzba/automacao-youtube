import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def upload_video(video_path, title, description, tags, credentials):
    """
    Faz o upload do vídeo para o YouTube.
    """
    try:
        youtube = build('youtube', 'v3', credentials=credentials)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "categoryId": 22,  # Categoria: People & Blogs
                    "description": description,
                    "title": title,
                    "tags": tags
                },
                "status": {
                    "privacyStatus": "public"
                }
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploading... {int(status.progress() * 100)}%")

        logging.info(f"Upload Complete! Video ID: {response['id']}")
    except Exception as e:
        logging.error(f"Erro ao fazer upload do vídeo: {e}")
        raise
