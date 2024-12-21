# scripts/main.py

import os
import logging
import json
from upload_youtube import upload_video_to_youtube
from youtube_auth import load_credentials
from video_creator import criar_video
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    filename='logs/main.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def carregar_configuracao(caminho_config='config/channels_config.json'):
    try:
        with open(caminho_config, 'r') as f:
            config = json.load(f)
        return config['channels']
    except Exception as e:
        logging.error(f"Erro ao carregar o arquivo de configuração: {e}")
        raise

def main():
    # Carregar configurações dos canais
    canais = carregar_configuracao()
    
    for canal in canais:
        try:
            nome_canal = canal['name']
            client_secret_file = os.path.join('credentials', canal['client_secret_file'])
            token_file = os.path.join('credentials', canal['token_file'])
            titulo = canal['title']
            descricao = canal['description']
            
            logging.info(f"Processando o canal: {nome_canal}")
            
            # Carregar ou autenticar no YouTube
            youtube = load_credentials(client_secret_file, token_file)
            
            # Criar o vídeo
            video_path = criar_video(texto=nome_canal, output_path='generated_videos')
            
            # Fazer upload para o YouTube
            upload_video_to_youtube(youtube, video_path, titulo, descricao)
        
        except Exception as e:
            logging.error(f"Erro ao processar o canal {nome_canal}: {e}")

if __name__ == "__main__":
    main()
