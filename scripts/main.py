import os
import json
import base64
import logging
import argparse

from video_creator import criar_video  # Importe suas funções.  VOCÊ PRECISA FORNECER ESTE ARQUIVO.
from youtube_auth import load_credentials  # Importe suas funções. USE A VERSÃO CORRETA (abaixo).
from upload_youtube import upload_video  # Importe suas funções. VOCÊ PRECISA FORNECER ESTE ARQUIVO.

def load_json(file_path):
    """
    Carrega um arquivo JSON, tratando erros de arquivo e decodificação.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:  # Assume UTF-8.  Ajuste se necessário.
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao decodificar JSON em {file_path}: {e}") from e


def main(channel_name):
    """
    Função principal para automatizar o processo de criação e upload de vídeos.
    """
    logging.basicConfig(level=logging.INFO)  # INFO para logs normais, DEBUG para logs detalhados
    logging.info(f"Iniciando automação para o canal: {channel_name}")

    try:
        # --- Caminho absoluto usando GITHUB_WORKSPACE ---
        base_dir = os.environ['GITHUB_WORKSPACE']  # Variável de ambiente do GitHub Actions
        config_path = os.path.join(base_dir, 'config', 'channels_config.json')
        logging.info(f"Config file path: {config_path}")  # Log do caminho completo

        # --- Verificações de existência e permissão (redundantes, mas importantes para debug) ---
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
        if not os.access(config_path, os.R_OK):
            raise PermissionError(f"Sem permissão de leitura para: {config_path}")
        # --- Fim das verificações extras ---


        config = load_json(config_path)
        canais = config['channels']
        canal_config = next((c for c in canais if c['name'] == channel_name), None)
        if not canal_config:
            raise ValueError(f"Canal {channel_name} não encontrado na configuração.")


        # --- Caminhos absolutos, SEM duplicar 'credentials' ---
        client_secret_path = os.path.join(base_dir, 'credentials', canal_config['client_secret_file'])
        token_path = os.path.join(base_dir, 'credentials', canal_config['token_file'])
        logging.debug(f"Client secret path: {client_secret_path}")  # Log do caminho
        logging.debug(f"Token path: {token_path}")  # Log do caminho

        credentials = load_credentials(client_secret_path, token_path)

        # --- Criação do vídeo (substitua pela sua lógica) ---
        logging.info("Criando vídeo...")
        # IMPORTANTE: Se criar_video retornar um caminho RELATIVO, você *precisa* do os.path.join
        video_path = criar_video(canal_config['title'], canal_config['description'], canal_config['keywords'])
        video_path = os.path.join(base_dir, video_path)  # GARANTIA de caminho absoluto
        logging.info(f"Vídeo criado: {video_path}")

        # --- Upload do vídeo ---
        logging.info("Fazendo upload do vídeo...")
        upload_video(video_path, canal_config['title'], canal_config['description'], canal_config['keywords'].split(','), credentials)
        logging.info("Upload do vídeo concluído.")

    except Exception as e:
        logging.exception(f"Erro na automação: {e}")  # Log completo do erro
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatiza a criação e upload de vídeos no YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser usado.')
    args = parser.parse_args()
    main(args.channel)
