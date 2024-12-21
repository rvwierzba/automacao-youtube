# scripts/video_creator.py

import os
from dotenv import load_dotenv
from moviepy.editor import TextClip, CompositeVideoClip, ColorClip
import logging

load_dotenv()

gemini_api_key = os.getenv('GEMINI_API_KEY')

def criar_video(texto, duration=10, tamanho=(1920, 1080), color=(0, 0, 0), output_path='generated_videos'):
    try:
        logging.info(f"Iniciando criação do vídeo com o texto: {texto}")
        
        # Exemplo de utilização da GEMINI_API_KEY
        # Utilize a gemini_api_key para gerar conteúdo ou integrar com o Gemini API conforme sua lógica
        
        # Criar um clipe de texto principal
        txt_clip = TextClip(texto, fontsize=70, color='white')
        txt_clip = txt_clip.set_pos('center').set_duration(duration)
        
        # Criar uma legenda
        legenda_texto = "Legend: This is an example subtitle in English."
        legenda_clip = TextClip(legenda_texto, fontsize=40, color='yellow')
        legenda_clip = legenda_clip.set_pos(('center', 'bottom')).set_duration(duration).set_opacity(0.6)
        
        # Criar um clipe de fundo
        fundo = ColorClip(size=tamanho, color=color).set_duration(duration)
        
        # Combinar os clipes
        video = CompositeVideoClip([fundo, txt_clip, legenda_clip])
        
        # Garantir que o diretório de saída exista
        os.makedirs(output_path, exist_ok=True)
        
        # Definir o caminho completo do vídeo
        video_filename = f"automacao_videos_{texto.replace(' ', '_')}.mp4"
        video_path = os.path.join(output_path, video_filename)
        
        # Renderizar o vídeo
        video.write_videofile(video_path, codec='libx264', audio=False)
        
        logging.info(f"Vídeo criado em: {video_path}")
        return video_path
    except Exception as e:
        logging.error(f"Erro na criação do vídeo: {e}")
        raise
