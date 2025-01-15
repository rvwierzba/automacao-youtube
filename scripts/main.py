import argparse
import logging
import os
import sys
import requests
import json
import subprocess
from pathlib import Path
from moviepy.editor import ImageClip, concatenate_videoclips
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Scopes necessários para a API do YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def parse_arguments():
    parser = argparse.ArgumentParser(description="Automação para criação e upload de vídeos no YouTube.")
    parser.add_argument('--gemini-api', required=True, help='Chave da API do Gemini.')
    parser.add_argument('--youtube-channel', required=True, help='ID do canal do YouTube.')
    parser.add_argument('--pixabay-api', required=True, help='Chave da API do Pixabay.')
    parser.add_argument('--quantidade', type=int, default=3, help='Quantidade de vídeos a serem criados.')
    parser.add_argument('--search-term', type=str, default='nature', help='Termo de busca para as imagens.')
    parser.add_argument('--client-secrets', type=str, default='credentials/client_secret.json', help='Caminho para o arquivo client_secret.json da API do YouTube.')
    return parser.parse_args()

def buscar_imagens_pixabay(api_key, search_term, quantidade):
    logging.info("Buscando imagens no Pixabay...")
    url = 'https://pixabay.com/api/'
    params = {
        'key': api_key,
        'q': search_term,
        'image_type': 'photo',
        'per_page': quantidade
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        dados = response.json()
        imagens = dados.get('hits', [])
        if not imagens:
            logging.error("Nenhuma imagem encontrada para o termo de busca fornecido.")
            sys.exit(1)
        logging.info(f"Recebido {len(imagens)} resultados da API do Pixabay.")
        return imagens
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar imagens no Pixabay: {e}")
        sys.exit(1)

def baixar_imagem(url, caminho):
    try:
        logging.info(f"Baixando imagem: {url}")
        resposta = requests.get(url, stream=True)
        resposta.raise_for_status()
        with open(caminho, 'wb') as f:
            for chunk in resposta.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Imagem salva em: {caminho}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao baixar imagem {url}: {e}")
        sys.exit(1)

def criar_video(imagens, output_path, duracao_por_imagem=2):
    try:
        logging.info("Criando vídeo com as imagens obtidas...")
        clips = []
        for img_path in imagens:
            clip = ImageClip(str(img_path)).set_duration(duracao_por_imagem)
            clips.append(clip)
        video = concatenate_videoclips(clips, method="compose")
        video.write_videofile(str(output_path), fps=24)
        logging.info(f"Vídeo criado com sucesso em: {output_path}")
    except Exception as e:
        logging.error(f"Erro ao criar vídeo: {e}")
        sys.exit(1)

def autenticar_youtube(client_secrets_file):
    logging.info("Autenticando na API do YouTube...")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        creds = flow.run_console()
        youtube = build('youtube', 'v3', credentials=creds)
        logging.info("Autenticação realizada com sucesso.")
        return youtube
    except FileNotFoundError:
        logging.error(f"Arquivo client_secrets.json não encontrado em: {client_secrets_file}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Erro na autenticação com a API do YouTube: {e}")
        sys.exit(1)

def upload_video_youtube(youtube, file_path, title, description, category_id=22, tags=None):
    logging.info("Iniciando upload do vídeo para o YouTube...")
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public'  # Pode ser 'public', 'private' ou 'unlisted'
        }
    }
    try:
        media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True, mimetype='video/*')
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logging.info(f"Progresso do upload: {int(status.progress() * 100)}%")
        logging.info(f"Vídeo enviado com sucesso! ID do vídeo: {response.get('id')}")
    except HttpError as e:
        logging.error(f"Erro ao enviar vídeo: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Erro inesperado durante o upload: {e}")
        sys.exit(1)

def main():
    args = parse_arguments()

    # Exibir configurações iniciais
    logging.info("Iniciando automação com as seguintes configurações:")
    logging.info(f"Gemini API Key: {'***'}")
    logging.info(f"YouTube Channel ID: {'***'}")
    logging.info(f"Pixabay API Key: {'***'}")
    logging.info(f"Quantidade de vídeos: {args.quantidade}")
    logging.info(f"Termo de busca: {args.search_term}")

    # Diretório temporário para baixar imagens
    temp_dir = Path("temp_images")
    temp_dir.mkdir(exist_ok=True)

    # Buscar imagens no Pixabay
    imagens = buscar_imagens_pixabay(args.pixabay_api, args.search_term, args.quantidade)

    # Baixar imagens
    caminhos_imagens = []
    for idx, img in enumerate(imagens, start=1):
        img_url = img.get('largeImageURL')
        if not img_url:
            logging.warning(f"Imagem {idx} não possui URL válida. Pulando...")
            continue
        img_path = temp_dir / f"imagem_{idx}.jpg"
        baixar_imagem(img_url, img_path)
        caminhos_imagens.append(img_path)

    if not caminhos_imagens:
        logging.error("Nenhuma imagem válida foi baixada. Encerrando o script.")
        sys.exit(1)

    # Criar vídeo
    video_path = Path("output_video.mp4")
    criar_video(caminhos_imagens, video_path)

    # Autenticar na API do YouTube
    youtube = autenticar_youtube(args.client_secrets)

    # Upload do vídeo para o YouTube
    titulo_video = "Automação de Vídeo com Python"
    descricao_video = "Este vídeo foi gerado automaticamente utilizando scripts Python."
    upload_video_youtube(youtube, video_path, titulo_video, descricao_video, tags=["automação", "python", "youtube"])

    logging.info("Automação concluída com sucesso.")

if __name__ == "__main__":
    main()
