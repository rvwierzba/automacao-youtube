#!/usr/bin/env python3
import argparse
from moviepy.editor import AudioFileClip, ImageClip

def criar_video(texto, saida):
    # Exemplo: gera arquivo de áudio a partir do texto
    from gtts import gTTS
    from pathlib import Path

    temp_audio = "temp_audio.mp3"
    tts = gTTS(texto, lang="en")
    tts.save(temp_audio)

    # Carrega o áudio
    audio_clip = AudioFileClip(temp_audio)

    # ANTES (incompatível com MoviePy master):
    #   bg = ImageClip("bg.jpg").set_duration(audio_clip.duration)

    # AGORA (duas possibilidades):

    # (opção 1) já passa a duration no construtor
    bg = ImageClip("bg.jpg", duration=audio_clip.duration)
    # (opção 2) ou em duas etapas:
    #   bg = ImageClip("bg.jpg")
    #   bg.duration = audio_clip.duration

    # Se quiser adicionar áudio no background
    bg = bg.set_audio(audio_clip)

    # Renderiza o vídeo
    bg.write_videofile(saida, fps=24)

    # Remove arquivo temporário
    Path(temp_audio).unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True)
    parser.add_argument("--youtube-channel", required=True)
    args = parser.parse_args()

    # Exemplo de texto fixo, só pra fins de teste
    texto_exemplo = f"Teste... Gemini: {args.gemini_api}, canal: {args.youtube_channel}"
    criar_video(texto_exemplo, "video_final.mp4")

if __name__ == "__main__":
    main()
