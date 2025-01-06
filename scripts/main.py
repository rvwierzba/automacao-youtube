# scripts/main.py

import argparse
import os
import tempfile
import subprocess
import google.generativeai as genai  # Importação correta
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
)
import requests  # Importado para buscar imagens no Pixabay


def gerar_curiosidades_gemini(api_key, quantidade=5):
    """
    Gera uma lista de curiosidades usando a API do Gemini.
    """
    try:
        genai.configure(api_key=api_key)
        print("Métodos disponíveis em google.generativeai após configuração:", dir(genai))  # Adiciona log
        prompt = f"Liste {quantidade} curiosidades interessantes e pouco conhecidas em português."
        response = genai.generate_text(
            model="text-bison-001",  # Utilize o modelo correto disponível para sua conta
            prompt=prompt,
            max_tokens=150,
            temperature=0.7,
        )
        curiosidades = response.text.strip().split('\n')
        # Limpar e formatar as curiosidades
        curiosidades = [c.strip('- ').strip() for c in curiosidades if c.strip()]
        return curiosidades
    except AttributeError as e:
        print(f"Erro ao gerar curiosidades com a API do Gemini: {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado ao gerar curiosidades com a API do Gemini: {e}")
        return []


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


def gerar_narracao(texto, idioma='pt'):
    """
    Gera uma narração a partir do texto usando gTTS.
    Retorna o caminho para o arquivo de áudio gerado.
    """
    try:
        tts = gTTS(texto, lang=idioma)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            audio_path = tmp_audio.name
        tts.save(audio_path)
        return audio_path
    except Exception as e:
        print(f"Erro ao gerar narração: {e}")
        return None


def criar_legenda(texto, imagem_saida="legenda.png"):
    """
    Cria uma imagem com o texto da legenda usando Pillow.
    """
    try:
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
    except Exception as e:
        print(f"Erro ao criar legenda: {e}")


def carregar_historico(caminho="used_curiosidades.txt"):
    """
    Carrega o histórico de curiosidades já utilizadas.
    """
    try:
        if not os.path.exists(caminho):
            return set()
        with open(caminho, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except Exception as e:
        print(f"Erro ao carregar histórico: {e}")
        return set()


def salvar_historico(curiosidades, caminho="used_curiosidades.txt"):
    """
    Salva as curiosidades utilizadas no histórico e faz commit no repositório.
    """
    try:
        with open(caminho, 'a', encoding='utf-8') as f:
            for curiosidade in curiosidades:
                f.write(f"{curiosidade}\n")
        
        # Adiciona, faz commit e push do arquivo de histórico
        subprocess.run(["git", "add", caminho], check=True)
        subprocess.run(["git", "commit", "-m", f"Atualiza histórico de curiosidades: {', '.join(curiosidades)}"], check=True)
        subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print(f"Erro ao salvar histórico: {e}")


def gerar_curiosidades_unicas(api_key, quantidade=5, caminho_historico="used_curiosidades.txt"):
    """
    Gera uma lista de curiosidades únicas usando a API do Gemini.
    """
    try:
        historico = carregar_historico(caminho_historico)
        curiosidades = []
        tentativas = 0
        max_tentativas = 10  # Para evitar loops infinitos

        while len(curiosidades) < quantidade and tentativas < max_tentativas:
            novas_curiosidades = gerar_curiosidades_gemini(api_key, quantidade=1)
            if not novas_curiosidades:
                break
            curiosidade = novas_curiosidades[0]
            if curiosidade not in historico and curiosidade not in curiosidades:
                curiosidades.append(curiosidade)
            tentativas += 1

        if curiosidades:
            salvar_historico(curiosidades, caminho_historico)
        
        return curiosidades
    except Exception as e:
        print(f"Erro ao gerar curiosidades únicas: {e}")
        return []


def criar_video(curiosidades, pixabay_api_key, video_saida="video_final.mp4"):
    """
    Cria um vídeo a partir de uma lista de curiosidades.
    Cada curiosidade terá uma imagem e uma narração correspondente.
    """
    try:
        print(f"Iniciando a criação do vídeo: {video_saida}")
        clips = []
        audios = []
        
        for index, curiosidade in enumerate(curiosidades, start=1):
            titulo = f"Curiosidade {index}"
            descricao = curiosidade
            print(f"Processando: {titulo}")
            
            # Buscar imagem relacionada
            imagem = buscar_imagem_pixabay(titulo, pixabay_api_key)
            if not imagem:
                # Tentar buscar uma imagem genérica se não encontrar
                imagem = buscar_imagem_pixabay("natureza", pixabay_api_key)
                if not imagem:
                    print(f"Sem imagem para: {titulo} e também não foi possível buscar uma imagem genérica.")
                    continue
            
            # Gerar narração
            narracao = gerar_narracao(descricao)
            if not narracao:
                print(f"Falha ao gerar narração para: {titulo}")
                continue
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
            return False  # Indica falha na criação do vídeo
        
        # Concatenar todos os clipes
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Exportar o vídeo final
        final_video.write_videofile(video_saida, fps=24)
        print(f"Vídeo '{video_saida}' exportado com sucesso.")
        
        # Verificar se o vídeo foi criado
        if not os.path.exists(video_saida):
            print(f"Erro: O arquivo de vídeo '{video_saida}' não foi criado.")
            return False
        else:
            print(f"Verificação: O arquivo '{video_saida}' foi encontrado.")
        
        # Limpar arquivos temporários
        for audio in audios:
            os.remove(audio.filename)
        os.remove("legenda.png")
        
        return True  # Indica sucesso na criação do vídeo
    except Exception as e:
        print(f"Erro ao criar vídeo: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Gerar vídeo de curiosidades com imagens e narração.")
    parser.add_argument("--gemini-api", required=True, help="Chave de API do Gemini para gerar curiosidades.")
    parser.add_argument("--youtube-channel", required=False, help="ID ou informação do canal.")
    parser.add_argument("--pixabay-api", required=True, help="Chave de API do Pixabay para buscar imagens.")
    parser.add_argument("--quantidade", type=int, default=5, help="Número de curiosidades a gerar.")
    parser.add_argument("--historico", type=str, default="used_curiosidades.txt", help="Caminho para o arquivo de histórico.")
    args = parser.parse_args()
    
    print(f"API Gemini Key: {args.gemini_api}")
    print(f"YouTube Channel ID: {args.youtube_channel}")
    print(f"Pixabay API Key: {args.pixabay_api}")
    print(f"Quantidade: {args.quantidade}")
    
    try:
        # Gerar curiosidades únicas dinamicamente
        print("Iniciando o processo de geração de curiosidades...")
        curiosidades = gerar_curiosidades_unicas(args.gemini_api, quantidade=args.quantidade, caminho_historico=args.historico)
        
        if not curiosidades:
            print("Nenhuma curiosidade única foi gerada.")
            exit(1)  # Saída com erro
        
        for i, curiosidade in enumerate(curiosidades, start=1):
            print(f"Curiosidade {i}: {curiosidade}")
        
        # Criar o vídeo
        sucesso = criar_video(curiosidades, args.pixabay_api)
        
        if not sucesso:
            print("Falha na criação do vídeo.")
            exit(1)  # Saída com erro
        
        print("Processo concluído com sucesso!")
        exit(0)  # Saída com sucesso
    except Exception as e:
        print(f"Erro no processo principal: {e}")
        exit(1)


if __name__ == "__main__":
    main()
