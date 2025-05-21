import argparse
import os
import random
import datetime
import time # Adicionado para o timestamp no nome do arquivo de vídeo
from dotenv import load_dotenv
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy.editor import (ImageClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, ColorClip)
from moviepy.config import change_settings
from PIL import Image, ImageDraw, ImageFont
import nltk
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    nltk.download('punkt')
from gtts import gTTS

# --- Configurações Globais e Carregamento de Variáveis de Ambiente ---
load_dotenv()
change_settings({"IMAGEMAGICK_BINARY": os.getenv("IMAGEMAGICK_BINARY", "imagemagick")})

# Tente importar a biblioteca Vertex AI e defina um sinalizador
VERTEX_AI_AVAILABLE = False
try:
    from google.cloud import aiplatform
    from google.cloud.aiplatform_v1beta1.types import PredictRequest
    from google.cloud.aiplatform_v1beta1.services.prediction_service import PredictionServiceClient
    from google.protobuf import json_format
    from google.protobuf.struct_pb2 import Value
    VERTEX_AI_AVAILABLE = True
    print("INFO: Biblioteca google-cloud-aiplatform encontrada. Geração de imagem com Vertex AI Imagen HABILITADA.")
except ImportError:
    print("WARNING:root:Biblioteca google-cloud-aiplatform não encontrada. Geração de imagem com Vertex AI Imagen estará desabilitada.")
    print("WARNING:root:Para habilitar, adicione 'google-cloud-aiplatform' ao requirements.txt e instale.")


# --- Constantes e Configurações ---
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_DIR = os.path.join(CURRENT_DIR, '..', 'credentials') # Ajustado para subir um nível e depois entrar em credentials
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, 'client_secret.json')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'token.json')

GENERATED_VIDEOS_DIR = os.path.join(CURRENT_DIR, '..', 'generated_videos')
GENERATED_IMAGES_DIR = os.path.join(CURRENT_DIR, '..', 'generated_images')
GENERATED_AUDIO_DIR = os.path.join(CURRENT_DIR, '..', 'generated_audio')
ASSETS_DIR = os.path.join(CURRENT_DIR, '..', 'assets') # Para fontes, etc.

FPS_VIDEO = 24 # Frames por segundo para o vídeo
IMAGE_DURATION_SECONDS = 5 # Duração de cada imagem no vídeo
MAX_WORDS_PER_LINE_TTS = 10 # Máximo de palavras por linha para o texto na imagem (afeta o TTS)
MAX_CHARS_PER_LINE_IMAGE = 40 # Máximo de caracteres por linha para o texto na imagem (afeta a quebra de linha visual)

# Configuração específica do canal (pode ser movida para um arquivo de configuração depois)
CHANNEL_CONFIGS = {
    "default": {
        "facts_language": "en", # Idioma para os fatos placeholder
        "image_generation_prompt_prefix": "Create a vibrant and engaging background image for a fun fact video. The image should be abstract and colorful, suitable for a general audience. Aspect ratio 16:9. Style: ",
        "image_styles": ["digital art", "cartoonish", "flat design", "geometric patterns", "abstract gradient"],
        "text_font_path_for_image_placeholder": None, # Caminho para a fonte se não usar Vertex AI ou se falhar
        "text_font_size_for_image_placeholder": 60,
        "text_color_for_image_placeholder": (255, 255, 255), # Branco
        "text_bg_color_for_image_placeholder": (0,0,0,150), # Fundo preto semi-transparente para o texto
        "text_position_for_image_placeholder": ('center', 'center'),
        "youtube_video_category_id": "24", # Entertainment
        "youtube_privacy_status": "public", # ou "private" ou "unlisted"
        "youtube_tags": ["fun facts", "shorts", "trivia", "entertainment"],
        "youtube_description_template": "Discover interesting fun facts in this short video! #funfacts #shorts #[CHANNEL_NAME]\n\nFact: {fact_text}\n\nDisclaimer: This video was auto-generated."
    },
    "fizzquirk": {
        "facts_language": "en",
        "image_generation_prompt_prefix": "Create a whimsical and quirky background image for a fun fact video for the 'FizzQuirk' channel. The image should be playful and eye-catching, with a touch of humor. Aspect ratio 16:9. Style: ",
        "image_styles": ["quirky illustration", "pop art", "surreal art", "bright and bold"],
        "text_font_path_for_image_placeholder": None, # Especificar se tiver uma fonte customizada
        "text_font_size_for_image_placeholder": 65,
        "text_color_for_image_placeholder": (255, 255, 0), # Amarelo
        "text_bg_color_for_image_placeholder": (0,0,0,180),
        "text_position_for_image_placeholder": ('center', 'bottom'),
        "youtube_video_category_id": "24",
        "youtube_privacy_status": "public",
        "youtube_tags": ["fizzquirk", "quirky facts", "fun shorts", "weird trivia"],
        "youtube_description_template": "Get your daily dose of quirkiness with FizzQuirk! #fizzquirk #funfacts #[CHANNEL_NAME]\n\nFact: {fact_text}\n\nDisclaimer: This video was auto-generated for FizzQuirk."
    }
    # Adicione outras configurações de canal aqui
}

# --- Funções de Autenticação do YouTube ---
def get_youtube_credentials():
    """Obtém ou atualiza as credenciais do usuário para a API do YouTube."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"ERRO ao carregar token.json: {e}")
            creds = None # Garante que creds seja None se o token for inválido

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("INFO: Credenciais expiradas. Tentando atualizar...")
                creds.refresh(Request())
                print("INFO: Credenciais atualizadas com sucesso.")
            except Exception as e:
                print(f"ERRO CRÍTICO: Falha ao atualizar credenciais: {e}")
                print("INFO: Será necessário reautenticar.")
                creds = None # Força a reautenticação
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"ERRO CRÍTICO: Arquivo client_secret.json não encontrado em {CLIENT_SECRET_FILE}")
                print("INFO: Faça o download do seu client_secret.json do Google Cloud Console e coloque-o no diretório 'credentials'.")
                return None
            try:
                print("INFO: Iniciando novo fluxo de autenticação.")
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                print("INFO: Autenticação bem-sucedida.")
            except Exception as e:
                print(f"ERRO CRÍTICO: Falha durante o fluxo de autenticação: {e}")
                return None

        if creds:
            try:
                os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                print(f"INFO: Token salvo em {TOKEN_FILE}")
            except Exception as e:
                print(f"ERRO: Não foi possível salvar o token em {TOKEN_FILE}: {e}")
    return creds

# --- Funções de Geração de Conteúdo ---

def get_facts_for_video(num_facts=3, channel_name="default"):
    """
    Busca ou gera uma lista de fatos para o vídeo.
    ATENÇÃO: Esta é uma função placeholder. Adapte para buscar de uma API, arquivo, etc.
    """
    config = CHANNEL_CONFIGS.get(channel_name, CHANNEL_CONFIGS["default"])
    lang = config["facts_language"]
    print(f"WARNING:root:ALERTA: Usando lista de fatos placeholder para '{lang}'. Adapte 'get_facts_for_video' para conteúdo real.")

    if lang == "pt-br":
        placeholder_facts = [
            "O mel nunca estraga.",
            "Polvos têm três corações.",
            "A Torre Eiffel pode ser 15 cm mais alta durante o verão.",
            "O som de um trovão não pode ser ouvido no vácuo do espaço.",
            "Morcegos são os únicos mamíferos capazes de voar."
        ]
    else: # Default to English
        placeholder_facts = [
            "Honey never spoils.",
            "Octopuses have three hearts.",
            "The Eiffel Tower can be 15 cm taller during the summer.",
            "The sound of a thunder cannot be heard in the vacuum of space.",
            "Bats are the only mammals capable of flight."
        ]
    return random.sample(placeholder_facts, min(num_facts, len(placeholder_facts)))


def generate_image_with_vertex_ai(prompt_text, image_path, project_id, location="us-central1", model_id="imagegeneration@006"):
    """
    Gera uma imagem usando Vertex AI Imagen e salva no caminho especificado.
    Retorna o caminho da imagem gerada ou None em caso de falha.
    """
    if not VERTEX_AI_AVAILABLE:
        print("WARNING:root:SDK Vertex AI (`google-cloud-aiplatform`) não disponível. Não é possível gerar imagem com Vertex AI.")
        return None

    print(f"INFO: Solicitando imagem ao Vertex AI com o prompt: '{prompt_text}'")
    try:
        aiplatform.init(project=project_id, location=location)
        parameters = {
            "prompt": prompt_text,
            "sampleCount": 1,
            "aspectRatio": "16:9", #  "1:1", "9:16", "4:3", "3:4"
            # "negativePrompt": "text, watermark, poorly drawn", # Exemplo
            # "seed": 12345 # Para reprodutibilidade, se necessário
        }
        endpoint = f"projects/{project_id}/locations/{location}/publishers/google/models/{model_id}"

        # Precisamos construir o request manualmente para usar a API REST via client library genérica
        # quando não estamos em um ambiente que suporta gRPC totalmente (como alguns runners de CI)
        # ou para ter mais controle sobre o timeout.

        # Se você tiver problemas de timeout, pode precisar ajustar o cliente da API.
        # Para simplificar, estamos usando aiplatform.Endpoint que lida com isso.
        # No entanto, a documentação mais recente pode sugerir o uso direto de PredictionServiceClient.

        # Tentativa com a forma mais simples e recomendada primeiro:
        model = aiplatform.Endpoint(endpoint_name=endpoint) # Usando o nome do modelo diretamente como endpoint
        response = model.predict(instances=[parameters])

        # A API pode retornar a imagem como bytes codificados em base64
        if response.predictions and len(response.predictions) > 0:
            prediction = response.predictions[0]
            if isinstance(prediction, dict) and "bytesBase64Encoded" in prediction:
                image_bytes = prediction["bytesBase64Encoded"]
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                with open(image_path, "wb") as f:
                    import base64
                    f.write(base64.b64decode(image_bytes))
                print(f"INFO: Imagem gerada e salva em {image_path}")
                return image_path
            else:
                print(f"ERRO: Resposta do Vertex AI não continha 'bytesBase64Encoded' esperado: {prediction}")
                return None
        else:
            print(f"ERRO: Nenhuma predição retornada pelo Vertex AI: {response}")
            return None

    except Exception as e:
        print(f"ERRO CRÍTICO ao gerar imagem com Vertex AI: {e}")
        return None

def create_placeholder_image_with_text(text, image_path, width=1920, height=1080, channel_name="default"):
    """Cria uma imagem de placeholder com gradiente e o texto centralizado."""
    config = CHANNEL_CONFIGS.get(channel_name, CHANNEL_CONFIGS["default"])
    print(f"WARNING:root:SDK Vertex AI (`google-cloud-aiplatform`) não disponível ou falhou. Usando placeholder de imagem para: {text}")

    img = Image.new('RGB', (width, height), color = (73, 109, 137)) # Cor base
    draw = ImageDraw.Draw(img)

    # Gradiente simples (opcional, pode ser customizado)
    for i in range(height):
        r = int(73 + (100 - 73) * (i / height))
        g = int(109 + (150 - 109) * (i / height))
        b = int(137 + (200 - 137) * (i / height))
        draw.line([(0, i), (width, i)], fill=(r, g, b))

    try:
        if config["text_font_path_for_image_placeholder"] and os.path.exists(config["text_font_path_for_image_placeholder"]):
            font = ImageFont.truetype(config["text_font_path_for_image_placeholder"], config["text_font_size_for_image_placeholder"])
            print(f"INFO: Usando fonte customizada para placeholder: {config['text_font_path_for_image_placeholder']}")
        else:
            if config["text_font_path_for_image_placeholder"]: # Se o caminho foi dado mas não encontrado
                 print(f"WARNING:root:Fonte '{config['text_font_path_for_image_placeholder']}' não encontrada. Usando padrão.")
            font = ImageFont.truetype(os.path.join(ASSETS_DIR, "fonts", "arial.ttf"), config["text_font_size_for_image_placeholder"]) # Fonte padrão se nenhuma especificada ou encontrada
            print(f"INFO: Usando fonte padrão Arial para placeholder.")
    except IOError:
        print(f"WARNING:root:Fonte não pôde ser carregada. Usando fonte default do Pillow.")
        font = ImageFont.load_default()


    # Quebra de linha inteligente para o texto
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        if len(current_line + " " + word) <= MAX_CHARS_PER_LINE_IMAGE:
            current_line += " " + word if current_line else word
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    wrapped_text = "\n".join(lines)

    # Calcula o tamanho do texto e a posição
    try:
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font) # Requer Pillow >= 8.0.0
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError: # Fallback para versões mais antigas do Pillow ou se textbbox não estiver disponível
        text_width, text_height = draw.textsize(wrapped_text, font=font)


    pos_x_config, pos_y_config = config["text_position_for_image_placeholder"]

    if pos_x_config == 'center':
        x = (width - text_width) / 2
    elif isinstance(pos_x_config, int):
        x = pos_x_config
    else: # default left
        x = 50

    if pos_y_config == 'center':
        y = (height - text_height) / 2
    elif pos_y_config == 'bottom':
        y = height - text_height - 50 # 50px de margem inferior
    elif pos_y_config == 'top':
        y = 50 # 50px de margem superior
    elif isinstance(pos_y_config, int):
        y = pos_y_config
    else: # default center
        y = (height - text_height) / 2

    # Adiciona um retângulo de fundo para o texto para melhor legibilidade
    rect_x0 = x - 20  # Padding
    rect_y0 = y - 20
    rect_x1 = x + text_width + 20
    rect_y1 = y + text_height + 20
    draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=config["text_bg_color_for_image_placeholder"])

    draw.text((x, y), wrapped_text, font=font, fill=config["text_color_for_image_placeholder"], align="center")

    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    img.save(image_path)
    print(f"INFO: Imagem placeholder salva em {image_path}")
    return image_path


def generate_audio_from_text(text, audio_path, lang="en"):
    """Gera áudio a partir do texto usando gTTS e salva."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        tts.save(audio_path)
        print(f"INFO: Áudio gerado para '{text[:30]}...' e salvo em {audio_path}")
        return audio_path
    except Exception as e:
        print(f"ERRO ao gerar áudio para '{text[:30]}...': {e}")
        return None

def create_video_from_facts(facts, channel_name="default"):
    """Cria um vídeo a partir de uma lista de fatos (texto, imagem, áudio)."""
    config = CHANNEL_CONFIGS.get(channel_name, CHANNEL_CONFIGS["default"])
    clips = []
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") # Necessário para Vertex AI

    for i, fact_text in enumerate(facts):
        unique_id = f"{channel_name}_{int(time.time())}_{i}" # Adiciona timestamp e índice para unicidade
        image_filename = f"image_{unique_id}.png"
        audio_filename = f"audio_{unique_id}.mp3"

        image_path_generated = os.path.join(GENERATED_IMAGES_DIR, image_filename)
        audio_path_generated = os.path.join(GENERATED_AUDIO_DIR, audio_filename)

        # 1. Gerar Imagem
        generated_image_file = None
        if VERTEX_AI_AVAILABLE and project_id:
            style_keyword = random.choice(config["image_styles"])
            image_prompt = f"{config['image_generation_prompt_prefix']} Fact: \"{fact_text}\". {style_keyword}."
            generated_image_file = generate_image_with_vertex_ai(image_prompt, image_path_generated, project_id)

        if not generated_image_file: # Fallback para placeholder
            generated_image_file = create_placeholder_image_with_text(fact_text, image_path_generated, channel_name=channel_name)

        if not generated_image_file or not os.path.exists(generated_image_file):
            print(f"ERRO CRÍTICO: Não foi possível gerar ou encontrar a imagem para o fato: {fact_text}")
            continue # Pula para o próximo fato

        # 2. Gerar Áudio
        audio_file = generate_audio_from_text(fact_text, audio_path_generated, lang=config["facts_language"])
        if not audio_file or not os.path.exists(audio_file):
            print(f"ERRO CRÍTICO: Não foi possível gerar ou encontrar o áudio para o fato: {fact_text}")
            # Considerar criar um clipe silencioso ou pular
            # Por enquanto, vamos pular este fato se o áudio falhar
            if os.path.exists(generated_image_file): # Limpa a imagem gerada se o áudio falhar
                try:
                    os.remove(generated_image_file)
                except OSError as e:
                    print(f"AVISO: Não foi possível remover a imagem órfã {generated_image_file}: {e}")
            continue


        # 3. Criar Clipe de Vídeo
        try:
            img_clip = ImageClip(generated_image_file).set_duration(IMAGE_DURATION_SECONDS).set_fps(FPS_VIDEO)
            audio_clip_moviepy = AudioFileClip(audio_file)

            # Ajusta a duração do clipe de imagem para a duração do áudio, se o áudio for mais longo
            # Ou mantém IMAGE_DURATION_SECONDS se o áudio for mais curto, o áudio vai parar.
            # Para Shorts, idealmente o áudio e imagem têm durações próximas.
            actual_duration = max(IMAGE_DURATION_SECONDS, audio_clip_moviepy.duration)
            actual_duration = min(actual_duration, 15) # Limita a 15s para shorts, pode ajustar

            img_clip = img_clip.set_duration(actual_duration)
            audio_clip_moviepy = audio_clip_moviepy.set_duration(min(audio_clip_moviepy.duration, actual_duration))


            video_clip = img_clip.set_audio(audio_clip_moviepy)
            clips.append(video_clip)
            print(f"INFO: Clipe criado para: {fact_text[:30]}... com duração: {actual_duration:.2f}s")

        except Exception as e:
            print(f"ERRO ao criar clipe para '{fact_text[:30]}...': {e}")
            # Limpeza de arquivos gerados para este fato em caso de erro na criação do clipe
            if os.path.exists(generated_image_file):
                try: os.remove(generated_image_file)
                except OSError: pass
            if os.path.exists(audio_file):
                try: os.remove(audio_file)
                except OSError: pass


    if not clips:
        print("ERRO: Nenhum clipe foi gerado. Saindo.")
        return None

    final_video = concatenate_videoclips(clips, method="compose")
    video_timestamp = int(time.time()) # Timestamp para nome de arquivo único
    video_filename = f"{channel_name}_{video_timestamp}.mp4"
    output_video_path = os.path.join(GENERATED_VIDEOS_DIR, video_filename)

    os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
    try:
        print(f"INFO: Montando vídeo final em {output_video_path}...")
        final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=FPS_VIDEO)
        print(f"INFO: Vídeo final gerado: {output_video_path}")
        return output_video_path
    except Exception as e:
        print(f"ERRO CRÍTICO ao escrever o arquivo de vídeo final: {e}")
        return None
    finally:
        # Limpeza dos clipes individuais de áudio e imagem após a criação do vídeo final
        for clip_obj in clips: # MoviePy clips, não os caminhos dos arquivos
            # A limpeza dos arquivos originais de imagem e áudio pode ser feita aqui
            # ou idealmente, guardar os caminhos e limpá-los.
            # Por agora, os arquivos permanecem em generated_images e generated_audio
            # para depuração, mas podem ser removidos se necessário.
            if hasattr(clip_obj, 'img_path_original') and os.path.exists(clip_obj.img_path_original):
                try: os.remove(clip_obj.img_path_original)
                except OSError: pass
            if hasattr(clip_obj, 'audio_path_original') and os.path.exists(clip_obj.audio_path_original):
                try: os.remove(clip_obj.audio_path_original)
                except OSError: pass
        print("INFO: Limpeza (potencial) de arquivos de clipe individuais concluída.")


# --- Funções do YouTube ---
def generate_video_title(facts, channel_name="default"):
    """Gera um título para o vídeo."""
    if not facts:
        return f"{channel_name.capitalize()} Short Video - {datetime.date.today().strftime('%Y-%m-%d')}"

    # Usa o primeiro fato para gerar um título mais descritivo
    first_fact = facts[0]
    # Simplifica o fato para um título, pegando as primeiras palavras ou uma parte chave
    title_keywords = " ".join(first_fact.split()[:5]) # Pega as primeiras 5 palavras
    if len(first_fact.split()) > 5:
        title_keywords += "..."

    # Remove caracteres que podem não ser ideais para títulos (ex: ponto final)
    title_keywords = title_keywords.replace('.', '')

    # Título com foco no conteúdo
    generated_title = f"Curiosidade Incrível: {title_keywords.strip()}"

    # Limita o tamanho do título (YouTube tem limite, geralmente ~100 caracteres)
    max_title_length = 90 # Deixa uma margem
    if len(generated_title) > max_title_length:
        generated_title = generated_title[:max_title_length-3] + "..."

    print(f"INFO: Título gerado para o vídeo: '{generated_title}'")
    return generated_title


def generate_video_description(facts, channel_name="default"):
    """Gera uma descrição para o vídeo."""
    config = CHANNEL_CONFIGS.get(channel_name, CHANNEL_CONFIGS["default"])
    # Usa o primeiro fato para a descrição se a lista de fatos não estiver vazia
    first_fact_text = facts[0] if facts else "Fatos interessantes!"
    # Substitui placeholders no template
    description = config["youtube_description_template"].replace("{fact_text}", first_fact_text)
    description = description.replace("#[CHANNEL_NAME]", f"#{channel_name.replace(' ', '')}") # Garante que o nome do canal seja uma hashtag válida
    return description

def upload_video_to_youtube(video_path, title, description, category_id, tags, privacy_status="public"):
    """Faz upload de um vídeo para o YouTube."""
    creds = get_youtube_credentials()
    if not creds:
        print("ERRO CRÍTICO: Falha ao obter credenciais do YouTube. Upload cancelado.")
        return None

    try:
        youtube = build('youtube', 'v3', credentials=creds)
        print(f"INFO: Fazendo upload do vídeo '{video_path}' para o YouTube com o título '{title}'...")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status
            }
        }

        media_file = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        # A variável 'response' aqui estava causando o NameError se a request falhasse antes da atribuição
        upload_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media_file
        )

        response = None
        while response is None:
            try:
                status, response = upload_request.next_chunk()
                if status:
                    print(f"INFO: Upload {int(status.progress() * 100)}% completo.")
            except Exception as e:
                print(f"ERRO durante o upload do chunk: {e}")
                # Adicionar uma pausa e tentar novamente pode ser útil aqui, ou um limite de tentativas
                time.sleep(5) # Pausa de 5s antes de tentar o próximo chunk novamente (ou falhar)

        if response and 'id' in response:
            video_id = response['id']
            print(f"INFO: Upload completo! Vídeo ID: {video_id}")
            print(f"INFO: Link do vídeo: https://www.youtube.com/watch?v={video_id}")
            return video_id
        else:
            print(f"ERRO CRÍTICO: O upload falhou ou não retornou um ID de vídeo. Resposta: {response}")
            return None

    except Exception as e:
        print(f"ERRO CRÍTICO durante o processo de upload do YouTube: {e}")
        return None

# --- Função Principal ---
def main():
    parser = argparse.ArgumentParser(description="Automatiza a criação e upload de vídeos de curiosidades para o YouTube.")
    parser.add_argument("--channel", type=str, default="default", help="Nome do canal para usar configurações específicas (ex: fizzquirk).")
    parser.add_argument("--num_facts", type=int, default=1, help="Número de fatos para incluir no vídeo (máx 3-5 recomendado para Shorts).")
    args = parser.parse_args()

    print(f"--- Iniciando Geração de Vídeo para o Canal: {args.channel} ---")

    # Criação dos diretórios necessários
    os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "fonts"), exist_ok=True) # Garante que assets/fonts exista


    facts = get_facts_for_video(num_facts=args.num_facts, channel_name=args.channel)
    if not facts:
        print("ERRO: Nenhum fato foi obtido. Encerrando.")
        return

    video_file_path = create_video_from_facts(facts, channel_name=args.channel)

    if video_file_path and os.path.exists(video_file_path):
        print(f"INFO: Vídeo gerado com sucesso: {video_file_path}")
        channel_config = CHANNEL_CONFIGS.get(args.channel, CHANNEL_CONFIGS["default"])

        video_title = generate_video_title(facts, channel_name=args.channel)
        video_description = generate_video_description(facts, channel_name=args.channel)

        upload_video_to_youtube(
            video_file_path,
            video_title,
            video_description,
            channel_config["youtube_video_category_id"],
            channel_config["youtube_tags"],
            channel_config["youtube_privacy_status"]
        )
        # Considere remover o vídeo local após o upload se não precisar mais dele
        # try:
        #     os.remove(video_file_path)
        #     print(f"INFO: Vídeo local {video_file_path} removido após upload.")
        # except OSError as e:
        #     print(f"AVISO: Não foi possível remover o vídeo local {video_file_path}: {e}")
    else:
        print("ERRO CRÍTICO: Falha ao gerar o arquivo de vídeo. Upload cancelado.")

    print(f"--- Processo para o Canal: {args.channel} Concluído ---")

if __name__ == "__main__":
    main()
