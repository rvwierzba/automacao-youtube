import argparse
import logging
import os
import requests

def fetch_images(api_key, per_page=2, safesearch=True):
    """
    Busca imagens na API do Pixabay.
    """
    url = "https://pixabay.com/api/"
    params = {
        "key": api_key,
        "per_page": per_page,
        "safesearch": safesearch
    }
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

def main():
    parser = argparse.ArgumentParser(description="Automação YouTube")
    parser.add_argument('--gemini-api', required=True, help='Chave da API Gemini')
    parser.add_argument('--youtube-channel', required=True, help='ID do canal do YouTube')
    parser.add_argument('--pixabay-api', required=True, help='Chave da API Pixabay')
    parser.add_argument('--quantidade', type=int, default=2, help='Quantidade de vídeos por execução')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    logging.info("Iniciando automação com as seguintes configurações:")
    logging.info(f"Gemini API Key: {args.gemini_api}")
    logging.info(f"YouTube Channel ID: {args.youtube_channel}")
    logging.info(f"Pixabay API Key: {args.pixabay_api}")
    logging.info(f"Quantidade de vídeos: {args.quantidade}")

    try:
        imagens = fetch_images(api_key=args.pixabay_api, per_page=args.quantidade, safesearch=True)
        logging.info(f"Encontradas {len(imagens)} imagens.")
        # Aqui você pode adicionar a lógica para processar as imagens e criar vídeos no YouTube
        # Por exemplo, fazer upload de vídeos usando a API do YouTube
    except Exception as e:
        logging.error(f"Erro durante a execução: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
