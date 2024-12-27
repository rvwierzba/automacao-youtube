import os
import logging
from moviepy.editor import TextClip

def criar_video(texto, output_path='generated_videos'):
    try:
        # Configurar logging
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Iniciando a criação do vídeo para o texto: {texto}")

        os.makedirs(output_path, exist_ok=True)

        # Criar um clipe de texto usando o Pillow (sem duplicar o 'font')
        clip = TextClip(
            texto,
            fontsize=70,
            color='white',
            size=(1280, 720),
            bg_color='black',
            method='caption'  # Permite quebras de linha automáticas
            # NÃO inclua font='...' aqui, pois o 'caption' pode gerar conflito se duplicarmos 'font'
        ).set_duration(5)  # Exemplo: 5 segundos

        # Nome de arquivo sanitizado
        video_filename = f"video_{texto.replace(' ', '_')}.mp4"
        video_full_path = os.path.join(output_path, video_filename)

        # Criar o vídeo
        clip.write_videofile(video_full_path, codec='libx264', audio=False)
        logging.info(f"Vídeo criado com sucesso em: {video_full_path}")
        return video_full_path

    except Exception as e:
        logging.error(f"Erro na criação do vídeo: {e}")
        raise

if __name__ == "__main__":
    # Exemplo de uso local
    criar_video("Olá, Mundo!")
