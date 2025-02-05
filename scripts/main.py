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
    with open(file_path, 'r') as file:
        base64_content = file.read()
        print(f"Conteúdo base64 lido de {file_path}: {base64_content[:50]}...")  # Imprime os primeiros 50 caracteres

    base64_content = base64_content.encode('ascii', 'ignore')  # Ignora erros de codificação ASCII
    print(f"Conteúdo base64 após encode('ascii'): {base64_content[:50]}...")

    for encoding in ['utf-8', 'latin-1', 'windows-1252']:  # Tenta UTF-8, Latin-1 e Windows-1252
        print(f"Tentando decodificar com {encoding}...")
        try:
            json_content = base64.b64decode(base64_content).decode(encoding)
            print(f"Decodificação com {encoding} bem-sucedida.")
            return json.loads(json_content)
        except UnicodeDecodeError as e:
            print(f"Tentativa de decodificação com {encoding} falhou: {e}")
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON após decodificação base64 com {encoding}: {e}")
            pass  # Tenta a próxima codificação

    raise ValueError(f"Não foi possível decodificar o arquivo {file_path} com nenhuma das codificações tentadas.")

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
