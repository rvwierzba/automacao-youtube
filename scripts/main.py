from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging
import os
import argparse

def upload_to_youtube(service, video_file, title, description, category, keywords, privacy_status):
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': keywords.split(','),
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy_status
        }
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype='video/*')

    request = service.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logging.info(f"Upload Progress: {int(status.progress() * 100)}%")

    logging.info(f"Upload concluído! Video ID: {response['id']}")
    return response

def main():
    parser = argparse.ArgumentParser(description="Gerador e Upload de Vídeo")
    parser.add_argument('--gemini-api', required=True, help='Chave API do Gemini')
    parser.add_argument('--youtube-channel', required=True, help='ID do Canal do YouTube')
    parser.add_argument('--pixabay-api', required=True, help='Chave API do Pixabay')
    parser.add_argument('--quantidade', type=int, required=True, help='Quantidade de vídeos para gerar')

    args = parser.parse_args()

    # Configuração de logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Verificação das variáveis
    if not all([args.gemini_api, args.youtube_channel, args.pixabay_api]):
        logger.error("Uma ou mais chaves API estão faltando.")
        exit(1)

    logger.info("Iniciando a geração do vídeo...")
    # Lógica de geração do vídeo
    video_path = "video_final.mp4"
    try:
        # Simulação de criação do vídeo
        with open(video_path, 'w') as f:
            f.write("Conteúdo do vídeo.")
        logger.info(f"Vídeo gerado com sucesso: {video_path}")
    except Exception as e:
        logger.error(f"Erro ao gerar o vídeo: {e}")
        exit(1)

    # Verificação final
    if not os.path.isfile(video_path):
        logger.error(f"Vídeo '{video_path}' não encontrado.")
        exit(1)

    # Configuração da API do YouTube
    try:
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        SERVICE_ACCOUNT_FILE = 'client_secret.json'

        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('youtube', 'v3', credentials=credentials)

        # Informações do vídeo
        title = "Título do Vídeo"
        description = "Descrição do Vídeo"
        category = "22"  # Categoria 22 para People & Blogs
        keywords = "teste, youtube, automação"
        privacy_status = "private"  # "public", "unlisted", "private"

        # Upload do vídeo
        upload_to_youtube(service, video_path, title, description, category, keywords, privacy_status)
        logger.info("Vídeo postado com sucesso no YouTube.")

    except Exception as e:
        logger.error(f"Erro ao fazer upload para o YouTube: {e}")
        exit(1)

if __name__ == "__main__":
    main()
