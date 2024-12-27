#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import moviepy.editor as mp
from moviepy.video.VideoClip import TextClip


def criar_video(texto: str, output: str = "video_final.mp4"):
    """
    Cria um vídeo de 5 segundos com um texto centralizado na tela,
    usando 'method="caption"' para evitar invocar o ImageMagick 'convert'.
    """
    # Tamanho e cores:
    largura, altura = 1280, 720
    cor_fundo = "black"
    cor_texto = "white"

    # Cria o clip de texto usando método 'caption':
    # Observação: não coloque 'font=' ou algo que exija fallback (ex: fontes exóticas).
    clip_texto = TextClip(
        txt=texto,
        fontsize=70,
        color=cor_texto,
        size=(largura, altura),
        bg_color=cor_fundo,
        method="caption",       # <--- FORÇANDO o Pillow e não o 'convert'
        align="center"
    ).set_duration(5)

    # Se quiser, podemos animar. Aqui deixamos fixo por 5s.
    # Monta o vídeo final (pode ser só o clip_texto).
    video_final = mp.CompositeVideoClip([clip_texto])

    # Renderiza em MP4 (h.264):
    video_final.write_videofile(
        output,
        fps=30,
        codec="libx264",
        threads=0,  # usa todos os cores
        audio=False
    )


def main():
    """
    Função principal do script.
    """
    # Pode pegar texto de sys.argv, ou fixo:
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
    else:
        texto = "Olá, Mundo!"

    print(f"INFO: Iniciando a criação do vídeo para o texto: {texto}")
    try:
        criar_video(texto)
        print("Vídeo criado com sucesso!")
    except Exception as e:
        print(f"Erro na criação do vídeo: {e}")


if __name__ == "__main__":
    main()
