import os
import logging
from moviepy.editor import ImageClip, TextClip, CompositeAudioClip
from gtts import gTTS

def criar_video(titulo, descricao, keywords, output_path='generated_videos'):
    """
    Cria um vídeo com base no título, descrição e palavras-chave fornecidas.
    """
    try:
        logging.info(f"Iniciando a criação do vídeo para o título: {titulo}")
        os.makedirs(output_path, exist_ok=True)

        # Cria o áudio usando gTTS
        audio_path = criar_audio(titulo, descricao, keywords)

        # Cria o clipe de imagem (substitua 'imagem.jpg' pelo caminho da sua imagem)
        imagem_clip = ImageClip("imagem.jpg").set_duration(10)

        # Cria o clipe de texto com o título
        texto_clip = TextClip(titulo, fontsize=70, color='white', size=(1280, 720), bg_color='black', method='caption', font='DejaVu-Sans-Bold').set_duration(10)

        # Combina o clipe de imagem e o clipe de texto
        video_clip = CompositeVideoClip([imagem_clip, texto_clip])

        # Adiciona o áudio ao clipe de vídeo
        audio_clip = AudioFileClip(audio_path)
        video_clip = video_clip.set_audio(audio_clip)

        # Salva o vídeo
        video_filename = f"video_{titulo}.mp4"
        video_full_path = os.path.join(output_path, video_filename)
        video_clip.write_videofile(video_full_path, codec='libx264')

        logging.info(f"Vídeo criado com sucesso: {video_full_path}")
        return video_full_path

    except Exception as e:
        logging.error(f"Erro na criação do vídeo: {e}")
        raise

def criar_audio(titulo, descricao, keywords):
    """
    Cria um arquivo de áudio com base no título, descrição e palavras-chave.
    """
    try:
        texto = f"{titulo}. {descricao}. {keywords}"
        tts = gTTS(text=texto, lang='en')
        audio_path = "audio.mp3"
        tts.save(audio_path)
        return audio_path
    except Exception as e:
        logging.error(f"Erro na criação do áudio: {e}")
        raise
