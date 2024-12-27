#!/usr/bin/env python3

import os
import sys
import json
import requests
from moviepy.editor import TextClip, CompositeVideoClip

def chamar_gemini_api(gemini_api_key: str, tema: str = "Random Curiosities"):
    """
    Exemplo fictício: chama a API do Gemini para gerar um texto.
    Substitua pela chamada real da sua API.
    """
    # Exemplo: GET ou POST, dependendo da API
    url = "https://api.gemini.com/v1/generate"  # fictício
    headers = {
        "Authorization": f"Bearer {gemini_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": f"Me dê um roteiro em inglês sobre curiosidades do tema: {tema}"
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data.get("text", "No content returned from Gemini")

def criar_video(texto: str, output_file: str = "video_final.mp4"):
    """
    Exemplo super simples com moviepy.
    Substitua a lógica de criar slides/clipes do jeito que preferir.
    """
    # Exemplo: faz um TextClip e salva
    clip = TextClip(texto, fontsize=70, color='white', size=(1280, 720), method='caption')
    clip = clip.set_duration(10)  # 10s
    # Salva
    clip.write_videofile(output_file, fps=24)

def main():
    # Pega args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=True, help="Gemini API Key")
    parser.add_argument("--youtube-channel", required=False, help="Channel ID", default="fizzquirk")
    args = parser.parse_args()

    gemini_api_key = args.gemini_api
    # 1) Gera texto
    texto_roteiro = chamar_gemini_api(gemini_api_key, tema="facts about the world")

    # 2) Cria vídeo com esse texto
    criar_video(texto_roteiro, "video_final.mp4")

    print("Vídeo gerado: video_final.mp4")

if __name__ == "__main__":
    main()
