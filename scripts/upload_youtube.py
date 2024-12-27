import os
import sys
import argparse
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

def upload_video(video_path, title, description, category_id, tags,
                 client_secret_file, token_file):
    """Realiza upload para o YouTube via google-api-python-client."""
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(
            token_file,
            ["https://www.googleapis.com/auth/youtube.upload"]
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secret_file,
                scopes=["https://www.googleapis.com/auth/youtube.upload"]
            )
            creds = flow.run_console()
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": "public"
        }
    }
    media = googleapiclient.http.MediaFileUpload(video_path, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress()*100)}%")

    if "id" in response:
        print("Upload realizado! Video ID:", response["id"])
    else:
        print("Falha no upload. Resposta:", response)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-file", required=True)
    parser.add_argument("--title", default="Meu Vídeo")
    parser.add_argument("--description", default="Vídeo gerado automaticamente")
    parser.add_argument("--category", default="22")
    parser.add_argument("--tags", nargs="*", default=["automation","curiosities"])
    parser.add_argument("--client-secret-file", required=True)
    parser.add_argument("--token-file", required=True)
    args = parser.parse_args()

    upload_video(
        video_path=args.video_file,
        title=args.title,
        description=args.description,
        category_id=args.category,
        tags=args.tags,
        client_secret_file=args.client_secret_file,
        token_file=args.token_file
    )

if __name__ == "__main__":
    main()
