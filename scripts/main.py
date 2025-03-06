import os
import argparse
import logging
import json
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

logging.basicConfig(level=logging.INFO)

# Escopos necessários para acessar a API do YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service(credentials_path):
    creds = None
    # O arquivo token.pickle armazena os tokens de acesso e de atualização do usuário,
    # e é criado automaticamente quando o fluxo de autorização é concluído pela primeira vez.
    token_path = os.path.splitext(credentials_path)[0] + '_token.pickle'
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    # Se não houver credenciais (disponíveis) válidas, deixe o usuário fazer login.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Salve as credenciais para a próxima execução
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def main(channel):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    credential_file = 'canal1_client_secret.json.base64'

    credential_path = os.path.join(credentials_dir, credential_file)

    try:
        with open(credential_path, 'r') as f:
            credencial_base64 = f.read()
            credencial_json = base64.b64decode(credencial_base64).decode('utf-8')
            credencial = json.loads(credencial_json)

        client_secrets_path = os.path.splitext(credential_path)[0] + '.json'
        with open(client_secrets_path, 'w') as f:
            json.dump(credencial, f, indent=4)
        logging.info(f"Arquivo de credenciais JSON criado em: {client_secrets_path}")

        youtube = get_authenticated_service(client_secrets_path)
        logging.info("Serviço do YouTube autenticado.")

        # Obtém informações do canal
        request_channel = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        response_channel = request_channel.execute()
        logging.info(f"Informações do canal: {response_channel}")

        # Obtém uploads do canal
        uploads_playlist_id = response_channel['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        request_uploads = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id
        )
        response_uploads = request_uploads.execute()
        logging.info(f"Uploads do canal: {response_uploads}")

        # Exemplo de como iterar pelos vídeos enviados
        if 'items' in response_uploads:
            for item in response_uploads['items']:
                video_id = item['contentDetails']['videoId']
                video_title = item['snippet']['title']
                logging.info(f"Vídeo ID: {video_id}, Título: {video_title}")

        # Exemplo de como listar playlists
        request_playlists = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True
        )
        response_playlists = request_playlists.execute()
        logging.info(f'Playlists do canal: {response_playlists}')
        # Adicione aqui o restante da sua lógica para usar a API do YouTube
        # Exemplo, adicionar um vídeo a uma playlist:
        # playlist_id_alvo = "SUA_PLAYLIST_ID"
        # request_add_video = youtube.playlistItems().insert(part='snippet', body={"snippet": {"playlistId": playlist_id_alvo, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
        # response_add_video = request_add_video.execute()
        # logging.info(f'Vídeo adicionado a playlist: {response_add_video}')
        # e muito mais...

    except FileNotFoundError:
        logging.error(f"Arquivo de credenciais não encontrado em: {credential_path}")
        return
    except json.JSONDecodeError:
        logging.error("Erro ao decodificar arquivo JSON de credenciais.")
        return
    except Exception as e:
        logging.error(f"Erro durante o processamento das credenciais: {e}")
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    args = parser.parse_args()
    main(args.channel)
