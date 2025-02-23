import os
import json
import base64
import logging
import argparse

from video_creator import criar_video  # Importe suas funções
from youtube_auth import load_credentials  # Importe suas funções
from upload_youtube import upload_video  # Importe suas funções

def load_json_from_base64(file_path):
    """
    Carrega um arquivo JSON a partir de um arquivo base64, tentando diferentes codificações.
    Inclui logs detalhados para depuração.
    """
    try:
        with open(file_path, 'r') as file:
            base64_content = file.read().strip()  # Remove espaços em branco e novas linhas
            print(f"Conteúdo base64 lido de {file_path}: {base64_content[:50]}...")  # Imprime os primeiros 50 caracteres

        # Decodifica o conteúdo base64
        json_content = base64.b64decode(base64_content).decode('utf-8')
        print(f"Conteúdo JSON decodificado: {json_content[:50]}...")  # Imprime os primeiros 50 caracteres do JSON

        # Converte o conteúdo decodificado para JSON
        return json.loads(json_content)
    except Exception as e:
        print(f"Erro ao decodificar o arquivo {file_path}: {e}")
        raise ValueError(f"Não foi possível decodificar o arquivo {file_path} com a codificação UTF-8.")

def main(channel_name):
    """
    Função principal para automatizar o processo de criação e upload de vídeos.
    """
    logging.basicConfig(level=logging.INFO)  # Configura o logging para nível INFO (você pode ajustar para DEBUG se precisar de mais detalhes)
    logging.info(f"Iniciando automação para o canal: {channel_name}")

    try:
        # Carrega as configurações do canal usando load_json_from_base64
        config = load_json_from_base64('config/channels_config.json')
        canais = config['channels']
        canal_config = next((c for c in canais if c['name'] == channel_name), None)
        if not canal_config:
            raise ValueError(f"Canal {channel_name} não encontrado na configuração.")

        # Carrega as credenciais
        client_secret_path = os.path.join('credentials', canal_config['client_secret_file'])
        token_path = os.path.join('credentials', canal_config['token_file'])

        # Chama a função load_credentials com o caminho correto do arquivo
        credentials = load_credentials(client_secret_path, token_path)

        # Cria o vídeo (substitua com sua lógica real)
        logging.info("Criando vídeo...")
        video_path = criar_video(canal_config['title'], canal_config['description'], canal_config['keywords'])
        logging.info(f"Vídeo criado: {video_path}")

        # Faz o upload do vídeo
        logging.info("Fazendo upload do vídeo...")
        upload_video(video_path, canal_config['title'], canal_config['description'], canal_config['keywords'].split(','), credentials)
        logging.info("Upload do vídeo concluído.")

    except Exception as e:
        logging.error(f"Erro na automação: {e}")
        raise  # Re-levanta a exceção para que o GitHub Actions registre o erro

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automatiza a criação e upload de vídeos no YouTube.')
    parser.add_argument('--channel', type=str, required=True, help='Nome do canal a ser usado.')
    args = parser.parse_args()
    main(args.channel)
