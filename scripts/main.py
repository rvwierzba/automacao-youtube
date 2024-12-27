import os
import sys
import argparse
import gtts

# Em vez de "from moviepy import ...", importe partes específicas:
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip, TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


def criar_video(texto: str, saida: str = "video_final.mp4"):
    """Exemplo simples que gera TTS (em inglês), compõe com ImageClip e salva vídeo."""
    # 1) TTS
    tts = gtts.gTTS(text=texto, lang="en")
    tts.save("temp_audio.mp3")
    audio_clip = AudioFileClip("temp_audio.mp3")

    # 2) Cria background
    if not os.path.exists("bg.jpg"):
        # gera um BG colorido
        import numpy as np
        from PIL import Image

        w, h = 1280, 720
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        arr[:] = (50, 50, 200)  # BGR(ish)
        Image.fromarray(arr).save("bg.jpg")

    bg = ImageClip("bg.jpg").set_duration(audio_clip.duration)

    # 3) TextClip
    textclip = TextClip(
        txt=texto,
        fontsize=48,
        color='white',
        method='caption',
        size=bg.size
    ).set_duration(audio_clip.duration)

    final = CompositeVideoClip([
        bg,
        textclip.set_position("center")
    ], size=bg.size).set_audio(audio_clip)

    final.write_videofile(saida, fps=24, codec="libx264", audio_codec="aac")
    audio_clip.close()

    # Cleanup
    if os.path.exists("temp_audio.mp3"):
        os.remove("temp_audio.mp3")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", help="Exemplo de chave do Gemini")
    parser.add_argument("--youtube-channel", help="Exemplo do canal do YouTube")
    args = parser.parse_args()

    texto_exemplo = "Hello from MoviePy! No SubtitlesClip import, so no error now."
    criar_video(texto_exemplo, "video_final.mp4")
    print("Vídeo gerado com sucesso:", "video_final.mp4")


if __name__ == "__main__":
    main()
