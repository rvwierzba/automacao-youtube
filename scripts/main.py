import argparse
import logging
import os
import sys
import requests
from moviepy.editor import ImageClip, concatenate_videoclips
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def fetch_images(api_key, per_page=2, safesearch=True, query=None):
    """
    Busca imagens na API do Pixabay.
    """
    url = "https://pixabay.com/api/"
    params = {
        "key": api_key,
        "per_page": per_page,
        "safesearch": safesearch
    }
    if query:
        params["q"] = query
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if 'hits' in data:
            return data['hits']
        else:
            logging.error("Resposta inesperada da API do Pixabay: %s", data)
            return []
    except requests.exceptions.HTTPError as e:
        logging.error(f"Falha ao buscar imagens: {response.status_code}")
        logging.error(f"Detalhes do erro: {response.text}")
        raise
    except Exception as e:
        logging.error(f"Erro desconhecido: {str(e)}")
        raise

def generate_content(gemini_api_key, image_description):
    """
    Gera conteúdo usando a Gemini API com base na descrição da imagem.
    """
    url = "https://api.gemini.com/generate"  # Substitua pela URL real da Gemini API
    headers = {
        "Authorization": f"Bearer {gemini_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": f"Crie uma descrição detalhada para o vídeo baseado na imagem: {image_description}",
        "max_tokens": 150
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get('text', 'Descrição não disponível.')
    except requests.exceptions.HTTPError as e:
        logging.error(f"Falha ao gerar conteúdo com Gemini API: {response.status_code}")
        logging.error(f"Detalhes do erro: {response.text}")
        raise
    except Exception as e:
        logging.error(f"Erro desconhecido na geração de conteúdo: {str(e)}")
        raise

def create_video(images, duration_per_image=5):
    """
    Cria um vídeo a partir de uma lista de URLs de imagens.
    """
    clips = []
    for img in images:
        img_url = img.get('largeImageURL')
        if not img_url:
            logging.warning("Imagem sem URL encontrada, pulando.")
            continue
        try:
            response = requests.get(img_url, stream=True)
            response.raise_for_status()
            img_path = f"temp_image_{images.index(img)}.jpg"
            with open(img_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            clip = ImageClip(img_path).set_duration(duration_per_image)
            clips.append(clip)
        except Exception as e:
            logging.error(f"Erro ao baixar ou processar a imagem {img_url}: {str(e)}")
            continue

    if not clips:
        logging.error("Nenhum vídeo foi criado devido à falta de imagens válidas.")
        sys.exit(1)

    video = concatenate_videoclips(clips, method="compose")
    video_path = "output_video.mp4"
    video.write_videofile(video_path, fps=24)
    
    # Limpar imagens temporárias
    for img in images:
        img_path = f"temp_image_{images.index(img)}.jpg"
        if os.path.exists(img_path):
            os.remove(img_path)
    
    return video_path

def upload_to_youtube(video_path, title, description, channel_id, credentials_path):
    """
    Faz o upload do vídeo para o YouTube usando a API do YouTube.
    """
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=scopes
    )
    youtube = build('youtube', 'v3', credentials=credentials)

    request_body = {
        'snippet': {
            'categoryId': '22',  # Categoria para "People & Blogs", ajuste conforme necessário
            'title': title,
            'description': description
        },
        'status': {
            'privacyStatus': 'public'  # Pode ser 'private', 'unlisted'
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/*')

    try:
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
        logging.info(f"Upload concluído! ID do vídeo: {response.get('id')}")
    except Exception as e:
        logging.error(f"Falha ao fazer upload do vídeo: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Automação YouTube")
    parser.add_argument('--gemini-api', required=True, help='Chave da API Gemini')
    parser.add_argument('--youtube-channel', required=True, help='ID do canal do YouTube')
    parser.add_argument('--pixabay-api', required=True, help='Chave da API Pixabay')
    parser.add_argument('--quantidade', type=int, default=2, help='Quantidade de vídeos por execução')
    parser.add_argument('--query', type=str, default='nature', help='Termo de busca para as imagens')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Iniciando automação com as seguintes configurações:")
    logging.info(f"Gemini API Key: {args.gemini_api}")
    logging.info(f"YouTube Channel ID: {args.youtube_channel}")
    logging.info(f"Pixabay API Key: {args.pixabay_api}")
    logging.info(f"Quantidade de vídeos: {args.quantidade}")
    logging.info(f"Termo de busca: {args.query}")

    try:
        # 1. Buscar imagens no Pixabay
        imagens = fetch_images(api_key=args.pixabay_api, per_page=args.quantidade, safesearch=True, query=args.query)
        logging.info(f"Encontradas {len(imagens)} imagens.")

        if not imagens:
            logging.error("Nenhuma imagem foi encontrada. Abortando a execução.")
            sys.exit(1)

        # 2. Gerar conteúdo com Gemini API
        descricoes = []
        for img in imagens:
            descricao = generate_content(gemini_api_key=args.gemini_api, image_description=img.get('tags', ''))
            descricoes.append(descricao)
            logging.info(f"Descrição gerada: {descricao}")

        # 3. Criar vídeo a partir das imagens
        video_path = create_video(imagens, duration_per_image=5)
        logging.info(f"Vídeo criado: {video_path}")

        # 4. Preparar título e descrição para o vídeo
        titulo = "Automação de Vídeo com Pixabay e Gemini API"
        descricao = "Este vídeo foi gerado automaticamente usando as APIs do Pixabay e Gemini."

        # 5. Upload para o YouTube
        upload_to_youtube(
            video_path=video_path,
            title=titulo,
            description=descricao,
            channel_id=args.youtube_channel,
            credentials_path='credentials/service_account.json'
        )

        logging.info("Automação concluída com sucesso.")

    except Exception as e:
        logging.error(f"Erro durante a execução: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
