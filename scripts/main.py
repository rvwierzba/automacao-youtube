import argparse
import os
import tempfile
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
)

def buscar_imagem_pixabay(query, api_key, largura=1280, altura=720):
    """
    Busca uma imagem no Pixabay relacionada à query.
    Retorna o caminho para a imagem baixada localmente.
    """
    url = 'https://pixabay.com/api/'
    params = {
        'key': api_key,
        'q': query,
        'image_type': 'photo',
        'orientation': 'horizontal',
        'safesearch': 'true',
        'per_page': 3
    }
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Erro ao buscar imagem para '{query}': {response.status_code}")
        return None
    
    try:
        data = response.json()
    except ValueError:
        print(f"Resposta inválida para a busca de imagem para '{query}'.")
        return None

    if data['hits']:
        # Seleciona a primeira imagem
        image_url = data['hits'][0]['largeImageURL']
        image_response = requests.get(image_url)
        
        if image_response.status_code != 200:
            print(f"Erro ao baixar a imagem de '{image_url}': {image_response.status_code}")
            return None
        
        image_path = os.path.join(tempfile.gettempdir(), os.path.basename(image_url))
        with open(image_path, 'wb') as f:
            f.write(image_response.content)
        return image_path
    else:
        print(f"Nenhuma imagem encontrada para '{query}'.")
        return None

def gerar_narracao(texto, idioma='en'):
    """
    Gera uma narração a partir do texto usando gTTS.
    Retorna o caminho para o arquivo de áudio gerado.
    """
    tts = gTTS(texto, lang=idioma)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
        audio_path = tmp_audio.name
    tts.save(audio_path)
    return audio_path

def criar_legenda(texto, imagem_saida="legenda.png"):
    """
    Cria uma imagem com o texto da legenda usando Pillow.
    """
    # Configurações da legenda
    largura, altura = 1280, 100  # Tamanho da imagem da legenda
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
    legenda_texto = texto

    # Adiciona o texto à imagem, centralizado
    text_width, text_height = d.textsize(legenda_texto, font=fonte)
    position = ((largura - text_width) / 2, (altura - text_height) / 2)
    d.text(position, legenda_texto, font=fonte, fill=texto_cor, align="center")

    # Salva a imagem da legenda
    img.save(imagem_saida)

def criar_video(curiosidades, pixabay_api_key, video_saida="video_final.mp4"):
    """
    Cria um vídeo a partir de uma lista de curiosidades.
    Cada curiosidade terá uma imagem e uma narração correspondente.
    """
    clips = []
    audios = []
    
    for index, curiosidade in enumerate(curiosidades, start=1):
        titulo = curiosidade['titulo']
        descricao = curiosidade['descricao']
        print(f"Processando curiosidade {index}: {titulo}")
        
        # Buscar imagem relacionada
        imagem = buscar_imagem_pixabay(titulo, pixabay_api_key)
        if not imagem:
            print(f"Sem imagem para: {titulo}")
            continue
        
        # Gerar narração
        narracao = gerar_narracao(descricao)
        audios.append(AudioFileClip(narracao))
        
        # Criar legenda
        criar_legenda(titulo, imagem_saida="legenda.png")
        legenda_clip = ImageClip("legenda.png").set_duration(AudioFileClip(narracao).duration).set_position(("center", "bottom"))
        
        # Criar clipe de imagem
        imagem_clip = ImageClip(imagem).set_duration(AudioFileClip(narracao).duration)
        
        # Combinar imagem e legenda
        video_clip = CompositeVideoClip([imagem_clip, legenda_clip])
        video_clip = video_clip.set_audio(AudioFileClip(narracao))
        
        clips.append(video_clip)
    
    if not clips:
        print("Nenhum clipe foi criado. Verifique as curiosidades e as imagens.")
        return
    
    # Concatenar todos os clipes
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Exportar o vídeo final
    final_video.write_videofile(video_saida, fps=24)
    
    # Limpar arquivos temporários
    for audio in audios:
        os.remove(audio.filename)
    os.remove("legenda.png")

def main():
    parser = argparse.ArgumentParser(description="Gerar vídeo de curiosidades com imagens e narração.")
    parser.add_argument("--gemini-api", required=False, help="Chave/variável para Gemini, se usar.")
    parser.add_argument("--youtube-channel", required=False, help="ID ou info do canal.")
    parser.add_argument("--pixabay-api", required=True, help="Chave de API do Pixabay para buscar imagens.")
    args = parser.parse_args()
    
    # Definir a lista de curiosidades
    curiosidades = [
        {
            "titulo": "Fato 1: Montanha mais alta",
            "descricao": "Did you know that Mount Everest is not actually the closest point to outer space?"
        },
        {
            "titulo": "Fato 2: Profundidade do Oceano",
            "descricao": "The Mariana Trench is the deepest part of the world's oceans, reaching depths of over 36,000 feet."
        },
        {
            "titulo": "Fato 3: Velocidade da Luz",
            "descricao": "Light travels at an incredible speed of approximately 299,792 kilometers per second."
        },
        {
            "titulo": "Fato 4: Diamante mais Duro",
            "descricao": "Diamonds are the hardest natural material on Earth, rated 10 on the Mohs scale."
        },
        {
            "titulo": "Fato 5: Células do Corpo",
            "descricao": "The human body is composed of approximately 37.2 trillion cells."
        },
        # Adicione mais curiosidades conforme necessário
    ]
    
    # Criar o vídeo
    criar_video(curiosidades, args.pixabay_api)

if __name__ == "__main__":
    main()
