# scripts/main.py

import os
import logging
from moviepy.editor import TextClip

def criar_video(texto, output_path='generated_videos'):
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Iniciando a criação do vídeo para o texto: {texto}")
        os.makedirs(output_path, exist_ok=True)

        # Criar um clipe de texto simples usando o Pillow
        clip = TextClip(
            texto,
            fontsize=70,
            color='white',
            size=(1280, 720),
            bg_color='black',
            method='caption',  # Utiliza o Pillow para renderizar o texto
            font='DejaVu-Sans-Bold'  # Fonte disponível no ambiente
        )
        clip = clip.set_duration(10)  # Duração de 10 segundos

        # Sanitizar o nome do arquivo para evitar espaços e caracteres especiais
        video_filename = f"video_{texto.replace(' ', '_')}.mp4"
        video_full_path = os.path.join(output_path, video_filename)
        clip.write_videofile(video_full_path, codec='libx264', audio=False)

        logging.info(f"Vídeo criado com sucesso: {video_full_path}")
        return video_full_path

    except Exception as e:
        logging.error(f"Erro na criação do vídeo: {e}")
        raise

if __name__ == "__main__":
    # Exemplo de uso
    textos = ["Olá, Mundo!", "Automação de Vídeos para YouTube"]
    for texto in textos:
        criar_video(texto)
