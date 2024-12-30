import argparse
import os
import tempfile
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ColorClip, AudioFileClip, ImageClip, CompositeVideoClip
)

def gerar_texto_automatico():
    """
    Função simulada para gerar texto automaticamente.
    Substitua esta função pela integração real com a API Gemini.
    """
    return (
        "Hello and welcome to our channel! "
        "In today's episode, we explore some curious facts about planet Earth. "
        "Did you know that Mount Everest is not actually the closest point to outer space?"
    )

def criar_legenda(texto, imagem_saida="legenda.png"):
    """
    Cria uma imagem com o texto da legenda usando Pillow.
    """
    # Configurações da legenda
    largura, altura = 1200, 200  # Tamanho da imagem da legenda
    fundo_cor = (30, 30, 30)     # Cor de fundo (cinza escuro)
    texto_cor = (255, 255, 255)  # Cor do texto (branco)
    fonte_tamanho = 40            # Tamanho da fonte

    # Cria uma nova imagem RGB
    img = Image.new('RGB', (largura, altura), color=fundo_cor)
    d = ImageDraw.Draw(img)

    # Tenta carregar uma fonte TrueType, senão usa a fonte padrão
    try:
        fonte = ImageFont.truetype("arial.ttf", fonte_tamanho)
    except IOError:
        fonte = ImageFont.load_default()

    # Define o texto da legenda
    legenda_texto = "English Narration:\n" + texto

    # Calcula a posição do texto para centralização
    texto_posicao = (10, 10)  # Margem esquerda e superior

    # Adiciona o texto à imagem
    d.multiline_text(texto_posicao, legenda_texto, font=fonte, fill=texto_cor, align="center")

    # Salva a imagem da legenda
    img.save(imagem_saida)

def criar_video(texto, video_saida="video_final.mp4"):
    """
    1. Converte o texto em áudio usando gTTS (idioma inglês).
    2. Cria um fundo colorido com duração do áudio.
    3. Cria uma imagem de legenda com Pillow.
    4. Adiciona a legenda ao vídeo.
    5. Salva o arquivo final .mp4.
    """

    # 1. Converte texto em áudio (gTTS).
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
        audio_path = tmp_audio.name
    tts = gTTS(texto, lang='en')
    tts.save(audio_path)

    # Carrega o áudio no MoviePy.
    audio_clip = AudioFileClip(audio_path)

    # 2. Cria background colorido com a mesma duração do áudio.
    duracao = audio_clip.duration
    bg = ColorClip(size=(1280, 720), color=(30, 30, 30), duration=duracao)
    bg = bg.set_audio(audio_clip)

    # 3. Cria a legenda usando Pillow.
    legenda_path = "legenda.png"
    criar_legenda(texto, legenda_path)
    legenda_clip = ImageClip(legenda_path).set_duration(duracao).set_position(("center", "bottom"))

    # 4. Combina o fundo e a legenda.
    video_final = CompositeVideoClip([bg, legenda_clip])

    # 5. Exporta o vídeo final.
    video_final.write_videofile(video_saida, fps=30)

    # Remove arquivos temporários.
    os.remove(audio_path)
    os.remove(legenda_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-api", required=False, help="Chave/variável para Gemini, se usar.")
    parser.add_argument("--youtube-channel", required=False, help="ID ou info do canal.")
    args = parser.parse_args()

    # Gera o texto automaticamente (substitua pela chamada real à API Gemini).
    texto_exemplo = gerar_texto_automatico()

    # Gera o vídeo final.
    criar_video(texto_exemplo, video_saida="video_final.mp4")

if __name__ == "__main__":
    main()
