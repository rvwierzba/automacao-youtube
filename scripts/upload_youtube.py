import os
import sys
import argparse
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

def upload_video(video_path, title, description, category_id, tags,
                 client_secret_file, token_file):
    """
    Realiza upload do video para o YouTube usando google-api-python-client.
    """
    # Carrega credenciais do token
    creds = None
    if os.path.exists(token_file):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_file, ["https://www.googleapis.com/auth/youtube.upload"])

    # Se não existe token ou é inválido, cria fluxo
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secret_file,
                scopes=["https://www.googleapis.com/auth/youtube.upload"]
            )
            creds = flow.run_console()
        # Salva credenciais
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    # Monta metadata
    request_body = {
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

    media = googleapiclient.http.MediaFileUpload(video_path, chunksize=-1, resumable=True)
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

    if "id" in response:
        print(f"Video uploaded. Video ID = {response['id']}")
    else:
        print("Upload error:", response)
        raise RuntimeError(f"Upload failed: {response}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-file", required=True)
    parser.add_argument("--title", default="Meu Vídeo")
    parser.add_argument("--description", default="Vídeo curioso!")
    parser.add_argument("--category", default="22")  # 22=People & Blogs
    parser.add_argument("--tags", nargs="*", default=["curiosities","facts"])
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
