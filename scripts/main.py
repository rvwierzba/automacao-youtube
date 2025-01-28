import os
import json
import base64
import logging
import argparse

from video_creator import criar_video
from youtube_auth import load_credentials
from upload_youtube import upload_video

def load_json_from_base64(file_path):
    """
    Carrega um arquivo JSON a partir de um arquivo base64.
    """
    with open(file_path, 'r') as file:
        base64_content = file.read()
    json_content = base64.b64decode(base64_content).decode('utf-8')
    return json.loads(json_content)

def main(channel_name):
    """
    Função principal para automatizar o processo de criação e upload de vídeos.
    """
    try:
        # Carrega as configurações do canal
        with open('config/channels_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        canais = config['channels']
        canal_config = next((c for c in canais if c['name'] == channel_name), None)
        if not canal_config:
            raise ValueError(f"Canal {channel_name} não encontrado na configuração.")

        # Carrega as credenciais
        client_secret_path = os.path.join('credentials', canal_config['client_secret_file'])
        token_path = os.path.join('credentials', canal_config['token_file'])
        credentials = load_credentials(client_secret_path, token_path)

        # Cria o vídeo
        video_path = criar_video(canal_config['title'], canal_config['description'], canal_config['keywords'])

        # Faz o upload do vídeo
        upload_video(video_path, canal_config['title'], canal_config['description'], canal_config['keywords'].split(','), credentials)

    except Exception as e:
        logging.error(f"Erro na automação: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatiza a criação e upload de vídeos no YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser usado.')
    args = parser.parse_args()
    main(args.channel)
