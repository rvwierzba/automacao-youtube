# scripts/main.py
import sys
from moviepy.editor import VideoClip, TextClip, CompositeVideoClip

def criar_video(texto: str, saida="video_final.mp4", duracao=5):
    """
    Cria um vídeo simples com 'texto' na tela.
    Usa 'method="caption"' para não depender do 'convert' (ImageMagick).
    """
    try:
        # Gera um TextClip usando apenas Pillow, sem chamar o 'convert'
        clip_texto = TextClip(
            txt=texto,
            fontsize=70,
            color='white',
            size=(1280, 720),   # Tamanho do quadro
            bg_color='black',  # Cor de fundo
            method='caption'   # <--- FUNDAMENTAL: evita o ImageMagick
        ).set_duration(duracao)

        # Caso queira centralizar, pode usar .set_position("center")
        # clip_texto = clip_texto.set_position("center")

        video_final = CompositeVideoClip([clip_texto], size=(1280, 720))
        # Renderiza (codec libx264 e sem áudio, por ex.)
        video_final.write_videofile(saida, fps=24, codec='libx264', audio=False)
        print(f"Vídeo '{saida}' criado com sucesso!")
    except Exception as e:
        print(f"Erro na criação do vídeo: {e}")
        raise

def main():
    # Exemplo: se quiser texto via argv
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
    else:
        texto = "Olá, Mundo!"

    criar_video(texto)

if __name__ == "__main__":
    main()
