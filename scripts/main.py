#!/usr/bin/env python3
import argparse
import os
from gtts import gTTS
import moviepy as mp  # <-- Importa a nova moviepy
# Em algumas versões, pode ser import moviepy.video.VideoClip ou similar

def criar_video(texto, saida_video):
    """
    Cria um vídeo simples a partir de:
      - Texto (para gerar áudio TTS)
      - ImageClip + AudioClip
    """
    audio_temp = "temp_audio.mp3"
    tts = gTTS(texto, lang="en")
    tts.save(audio_temp)

    # Carrega o áudio.
    audio_clip = mp.AudioFileClip(audio_temp)

    # Cria um ImageClip com a duração do áudio.
    bg = mp.ImageClip("bg.jpg", duration=audio_clip.duration)

    # Vincula o áudio ao clip de imagem.
    bg = bg.set_audio(audio_clip)

    # Exporta o vídeo final
    bg.write_videofile(saida_video, fps=24)

    # Limpa temp
    if os.path.exists(audio_temp):
        os.remove(audio_temp)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True, help="Chave Gemini")
    parser.add_argument("--youtube-channel", required=True, help="Canal do YouTube")
    args = parser.parse_args()

    texto_exemplo = f"Olá, aqui é um exemplo com {args.gemini_api} no canal {args.youtube_channel}."
    criar_video(texto_exemplo, "video_final.mp4")

if __name__ == "__main__":
    main()
