#!/usr/bin/env python3
import argparse
from gtts import gTTS
from moviepy.editor import AudioFileClip, ImageClip
from pathlib import Path

def criar_video(texto, saida_video):
    """
    Cria um vídeo simples a partir de:
      - Texto (para gerar áudio TTS com gTTS)
      - Imagem de fundo (bg.jpg) + áudio
    """

    # 1) Gera um arquivo de áudio temporário usando gTTS
    audio_temp = "temp_audio.mp3"
    tts = gTTS(texto, lang="en")
    tts.save(audio_temp)

    # 2) Carrega o áudio
    audio_clip = AudioFileClip(audio_temp)

    # 3) Cria um ImageClip com a duração igual à do áudio
    # Em vez de .set_duration(), use o parâmetro 'duration='
    bg = ImageClip("bg.jpg", duration=audio_clip.duration)

    # 4) Vincula o áudio ao clip de imagem
    bg = bg.set_audio(audio_clip)

    # 5) Exporta o vídeo final
    bg.write_videofile(saida_video, fps=24)

    # 6) Remove o arquivo temporário de áudio
    Path(audio_temp).unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True, help="Seu Gemini API Key")
    parser.add_argument("--youtube-channel", required=True, help="ID do canal no YouTube")
    args = parser.parse_args()

    # Exemplo de texto que poderia vir da sua API Gemini ou algo similar
    texto_exemplo = (
        f"Olá! Este é um teste simples. "
        f"Gemini key: {args.gemini_api}, canal: {args.youtube_channel}. "
        f"Obrigado por assistir!"
    )

    # Chama a função para criar o vídeo
    criar_video(texto_exemplo, "video_final.mp4")

if __name__ == "__main__":
    main()
