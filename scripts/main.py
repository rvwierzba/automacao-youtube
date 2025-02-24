import os
import json
import base64
import logging
import argparse

from video_creator import criar_video  # Importe suas funções
from youtube_auth import load_credentials  # Importe suas funções
from upload_youtube import upload_video  # Importe suas funções

def load_json(file_path):
    """
    Carrega um arquivo JSON, tratando erros e removendo BOM se existir.
    """
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as file: # Use utf-8-sig
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao decodificar JSON em {file_path}: {e}") from e


def main(channel_name):
    """
    Função principal.
    """
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Iniciando automação para o canal: {channel_name}")

    try:
        # Caminhos absolutos, usando a variável de ambiente do GitHub Actions
        base_dir = os.environ['GITHUB_WORKSPACE']
        config_path = os.path.join(base_dir, 'config', 'channels_config.json')
        logging.debug(f"Config file path: {config_path}") # Log do caminho

        config = load_json(config_path)
        canais = config['channels']
        canal_config = next((c for c in canais if c['name'] == channel_name), None)
        if not canal_config:
            raise ValueError(f"Canal {channel_name} não encontrado na configuração.")

        # Monta os caminhos para os arquivos de credenciais
        client_secret_path = os.path.join(base_dir, canal_config['client_secret_file'])
        token_path = os.path.join(base_dir,  canal_config['token_file'])
        logging.debug(f"Client secret path: {client_secret_path}") # Log do caminho
        logging.debug(f"Token path: {token_path}") # Log do caminho

        credentials = load_credentials(client_secret_path, token_path)

        logging.info("Criando vídeo...")
        video_path = criar_video(canal_config['title'], canal_config['description'], canal_config['keywords'])
        video_path = os.path.join(base_dir, video_path)  # IMPORTANTE: Caminho absoluto
        logging.info(f"Vídeo criado: {video_path}")

        logging.info("Fazendo upload do vídeo...")
        upload_video(video_path, canal_config['title'], canal_config['description'], canal_config['keywords'].split(','), credentials)
        logging.info("Upload do vídeo concluído.")


    except Exception as e:
        logging.exception(f"Erro na automação: {e}") # Log completo, incluindo traceback
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatiza a criação e upload de vídeos no YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser usado.')
    args = parser.parse_args()
    main(args.channel)
