#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Exemplo de script Python que cria um vídeo usando MoviePy sem depender do ImageMagick
para renderizar o texto. Em vez disso, usa o method='caption' (renderização via Pillow).
"""

import logging
import sys

from moviepy.editor import TextClip, CompositeVideoClip


def criar_video(texto: str, saida="video_final.mp4"):
    """
    Cria um vídeo de 5 segundos com um texto centralizado,
    usando Pillow no lugar do ImageMagick.
    """
    try:
        # method='caption' força o uso do PIL/Pillow, evitando o ImageMagick
        clip_texto = TextClip(
            txt=texto,
            fontsize=70,
            color='white',
            size=(1280, 720),   # resolução do quadro
            bg_color='black',
            method='caption',   # ESSENCIAL para não chamar 'convert'
        ).set_duration(5)

        final_clip = CompositeVideoClip([clip_texto])
        final_clip.write_videofile(
            saida,
            fps=24,
            codec="libx264",  # Ajuste se quiser outro codec
            audio=False
        )
        logging.info(f"Vídeo '{saida}' criado com sucesso!")
    except Exception as e:
        logging.error(f"Erro na criação do vídeo: {e}", exc_info=True)
        sys.exit(1)


def main():
    """
    Exemplo simples: cria um vídeo com a frase 'Olá, Mundo!'.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    texto_exemplo = "Olá, Mundo!"
    logging.info(f"Iniciando a criação do vídeo para o texto: {texto_exemplo}")
    criar_video(texto_exemplo)


if __name__ == "__main__":
    main()
