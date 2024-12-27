# main.py
import sys
from moviepy.editor import TextClip, CompositeVideoClip


def criar_video(texto: str, saida="video_final.mp4"):
    """
    Cria um vídeo simples de 5 segundos,
    exibindo o 'texto' ao centro.
    Utiliza 'method="caption"' para
    não depender do ImageMagick/convert.
    """
    try:
        # Força a renderização via PIL/Pillow (method='caption'),
        # evitando a chamada de 'convert' do ImageMagick.
        clip_texto = TextClip(
            txt=texto,
            fontsize=70,
            color='white',
            # Você pode alterar o bg_color, tamanho etc. livremente.
            size=(1280, 720),
            bg_color='black',
            method='caption'  # <-- IMPORTANTE!
        ).set_duration(5)

        # Se quiser centralizar ou animar, você pode setar .set_position("center")
        # clip_texto = clip_texto.set_position("center")

        # Criamos um clip final
        final_clip = CompositeVideoClip([clip_texto])

        # Renderiza o vídeo em MP4
        final_clip.write_videofile(saida, fps=24, codec="libx264", audio=False)
        print(f"Vídeo '{saida}' criado com sucesso!")
    except Exception as e:
        print(f"Erro na criação do vídeo: {e}")
        raise


def main():
    # Exemplo: se você quiser pegar o texto via argv:
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
    else:
        texto = "Olá, Mundo!"

    criar_video(texto, "video_final.mp4")


if __name__ == "__main__":
    main()
