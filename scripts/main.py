import os
import json
import base64
import logging
import argparse

from video_creator import criar_video
from youtube_auth import load_credentials
from upload_youtube import upload_video

def load_json(file_path):
    """
    Carrega um arquivo JSON, tratando erros de arquivo e decodificação.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:  # Assume UTF-8. Ajuste se necessário.
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao decodificar JSON em {file_path}: {e}") from e


def main(channel_name):
    """
    Função principal para automatizar o processo de criação e upload de vídeos.
    """
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Iniciando automação para o canal: {channel_name}")

    try:
        # Carrega as configurações do canal diretamente (JSON puro)
        config = load_json('config/channels_config.json')
        canais = config['channels']
        canal_config = next((c for c in canais if c['name'] == channel_name), None)
        if not canal_config:
            raise ValueError(f"Canal {channel_name} não encontrado na configuração.")

        # Carrega as credenciais
        client_secret_path = os.path.join('credentials', canal_config['client_secret_file'])
        token_path = os.path.join('credentials', canal_config['token_file'])
        credentials = load_credentials(client_secret_path, token_path)

        # Cria o vídeo
        logging.info("Criando vídeo...")
        video_path = criar_video(canal_config['title'], canal_config['description'], canal_config['keywords'])
        logging.info(f"Vídeo criado: {video_path}")

        # Faz o upload do vídeo
        logging.info("Fazendo upload do vídeo...")
        upload_video(video_path, canal_config['title'], canal_config['description'], canal_config['keywords'].split(','), credentials)
        logging.info("Upload do vídeo concluído.")

    except Exception as e:
        logging.exception(f"Erro na automação: {e}")  # Use logging.exception para o traceback completo
        raise  # Re-levanta a exceção


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatiza a criação e upload de vídeos no YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser usado.')
    args = parser.parse_args()
    main(args.channel)
