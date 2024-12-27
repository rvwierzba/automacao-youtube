#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
import requests

from gtts import gTTS
from moviepy.editor import (AudioFileClip, VideoFileClip, ImageClip,
                            CompositeVideoClip, SubtitlesClip,
                            TextClip, concatenate_videoclips)
from moviepy.video.tools.subtitles import SubtitlesClip

import nltk  # Para separar frases, se desejar. Precisará 'pip install nltk'
# nltk.download('punkt') se não tiver baixado

def chamar_gemini_api(gemini_api_key: str, tema: str = "Incredible Curiosities"):
    """
    Exemplo fictício de chamada à API do Gemini.
    Ajuste para a rota real e forma real de parse.
    """
    url = "https://api.gemini.com/v1/generate"  # ROTA FICTÍCIA
    headers = {
        "Authorization": f"Bearer {gemini_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": f"Generate an English script about: {tema}"}
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    # Supondo que a API retorne "text" com o script
    return data.get("text", "No text returned from Gemini API")

def gerar_legendas_srt(frases_com_tempo, srt_filename="subtitles.srt"):
    """
    Recebe uma lista de tuplas (start, end, frase)
    Gera o arquivo .srt
    """
    with open(srt_filename, "w", encoding="utf-8") as f:
        for i, (start, end, frase) in enumerate(frases_com_tempo, start=1):
            f.write(f"{i}\n")
            # Formato SRT: HH:MM:SS,mmm
            # Convertemos start/end (em segundos) para esse formato
            start_s = time.strftime('%H:%M:%S', time.gmtime(start))
            start_ms = int((start - int(start)) * 1000)
            end_s = time.strftime('%H:%M:%S', time.gmtime(end))
            end_ms = int((end - int(end)) * 1000)

            f.write(f"{start_s},{start_ms:03d} --> {end_s},{end_ms:03d}\n")
            f.write(frase.strip() + "\n\n")

def criar_video_com_subtitulacao(texto:str, audio_path:str, srt_path:str, output_path="video_final.mp4"):
    """
    Cria um vídeo 1280x720 com o áudio e legendas (queimadas).
    """
    # 1) Carregar o áudio e extrair duracao
    audio = AudioFileClip(audio_path)
    dur = audio.duration

    # 2) Vamos gerar um clip de fundo (bg) fixo, ex: cor ou imagem
    # Exemplo: um "fundo colorido" ou uma imagem. Aqui, cor (um clip de cor).
    W, H = 1280, 720
    # A partir do MoviePy 2.0, não existe mais ColorClip oficial, mas simulamos:
    bg_clip = ImageClip(color=(30, 30, 30), size=(W, H), ismask=False, duration=dur)
    bg_clip = bg_clip.set_duration(dur)

    # 3) Carregar subtitles do .srt
    generator = lambda txt: TextClip(txt, fontsize=50, color='white', size=(W-100,None), method='caption')
    subs = SubtitlesClip(srt_path, generator)

    # 4) Compor
    final_clip = CompositeVideoClip([bg_clip, subs.set_pos('center')])
    final_clip = final_clip.set_duration(dur).set_audio(audio)

    # 5) Render
    final_clip.write_videofile(output_path, fps=24)
    final_clip.close()
    audio.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True, help="Chave da API fictícia do Gemini")
    parser.add_argument("--youtube-channel", default="fizzquirk", help="Nome do canal (não é usado neste script)")
    args = parser.parse_args()

    # 1) Obter texto
    tema = "Incredible Curiosities"  # ou algo fixo. Poderia ser random
    texto_gerado = chamar_gemini_api(args.gemini_api, tema=tema)
    texto_gerado = texto_gerado.strip()
    if not texto_gerado:
        texto_gerado = "Here are some interesting curiosities..."

    print("Texto gerado do Gemini:")
    print(texto_gerado)

    # 2) Converter para áudio (TTS)
    tts = gTTS(text=texto_gerado, lang="en")
    audio_file = "audio_temp.mp3"
    tts.save(audio_file)
    print(f"Áudio TTS salvo: {audio_file}")

    # 3) Gerar legendas SRT
    # - Dividimos o texto em frases
    sentences = nltk.sent_tokenize(texto_gerado, language="english")
    # Carregamos a duração do audio via moviepy
    audio_clip = AudioFileClip(audio_file)
    total_dur = audio_clip.duration

    # Dividir tempo total pelo número de frases => aproximar
    # (exemplo simples, cada frase terá a mesma fatia)
    n = len(sentences)
    if n == 0:
        sentences = [texto_gerado]  # fallback
        n = 1
    slice_dur = total_dur / n

    # Montar (start, end, frase) para cada frase
    frases_com_tempo = []
    current_start = 0.0
    for s in sentences:
        current_end = current_start + slice_dur
        frases_com_tempo.append((current_start, current_end, s))
        current_start = current_end

    srt_file = "subtitles.srt"
    gerar_legendas_srt(frases_com_tempo, srt_file)
    print(f"Legendas geradas: {srt_file}")

    # 4) Criar vídeo final com legendas e áudio
    criar_video_com_subtitulacao(
        texto=texto_gerado,
        audio_path=audio_file,
        srt_path=srt_file,
        output_path="video_final.mp4"
    )

    print(">>> Vídeo final gerado: video_final.mp4")

if __name__ == "__main__":
    main()
