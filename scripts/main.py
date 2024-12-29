# scripts/main.py

import sys
import argparse
from moviepy.editor import AudioFileClip, ColorClip

def criar_video(texto, nome_output):
    # Carrega áudio (mude "audio.mp3" se você tiver outro nome de arquivo de áudio)
    audio_clip = AudioFileClip("audio.mp3")

    # Cria um fundo colorido (preto) no tamanho e duração do áudio
    # Se quiser outra cor, troque (0, 0, 0) por (R, G, B) como (255, 255, 255) para branco etc.
    fundo = ColorClip(size=(1280, 720), color=(0, 0, 0)).set_duration(audio_clip.duration)

    # Atribui o áudio ao fundo
    final_clip = fundo.set_audio(audio_clip)

    # Salva em MP4
    final_clip.write_videofile(nome_output, fps=30)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True, help="Chave da API Gemini")
    parser.add_argument("--youtube-channel", required=True, help="Canal do YouTube")
    args = parser.parse_args()

    # Exemplo de texto, só para simular
    texto_exemplo = "Texto gerado pela API Gemini..."

    criar_video(texto_exemplo, "video_final.mp4")

if __name__ == "__main__":
    main()
