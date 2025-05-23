import os
import argparse
import logging
import json
import sys
import time
import random
import numpy as np
import datetime 

# Para geração de áudio
from gtts import gTTS

# Para edição de vídeo
from moviepy.editor import (AudioFileClip, TextClip, CompositeVideoClip,
                            ColorClip, ImageClip, CompositeAudioClip,
                            concatenate_videoclips, concatenate_audioclips, AudioClip)
from moviepy.config import change_settings
import moviepy.config as MOPY_CONFIG

# Para o placeholder de imagem e manipulação
from PIL import Image as PILImage, ImageDraw as PILImageDraw, ImageFont as PILImageFont

# Para API do YouTube
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# Tenta importar a biblioteca do Vertex AI (para Imagen)
try:
    from google.cloud import aiplatform
    VERTEX_AI_SDK_AVAILABLE = True
    logging.info("Biblioteca google-cloud-aiplatform encontrada e importada.")
except ImportError:
    VERTEX_AI_SDK_AVAILABLE = False
    logging.warning("Biblioteca google-cloud-aiplatform não encontrada. Geração de imagem com Vertex AI Imagen estará desabilitada.")
    logging.warning("Para habilitar, adicione 'google-cloud-aiplatform' ao requirements.txt e instale.")


logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# --- Constantes e Configurações ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) 

CREDENTIALS_DIR = os.path.join(BASE_DIR, 'credentials')
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, 'client_secret.json')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'token.json')

GENERATED_VIDEOS_DIR = os.path.join(BASE_DIR, 'generated_videos')
GENERATED_IMAGES_DIR = os.path.join(BASE_DIR, 'generated_images') 
GENERATED_AUDIO_DIR = os.path.join(BASE_DIR, 'temp_audio') 
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
TOPIC_FILE_PATH = os.path.join(BASE_DIR, 'topics.txt') # Arquivo com lista de temas
HISTORY_FILE_PATH = os.path.join(BASE_DIR, 'topic_history.txt') # Arquivo para histórico de temas
HISTORY_LENGTH = 10 # Não repetir os últimos X temas (ajuste se sua lista de tópicos for pequena)

FPS_VIDEO = 24
MAX_WORDS_PER_LINE_TTS = 10 
MAX_CHARS_PER_LINE_IMAGE = 40

CHANNEL_CONFIGS = {
    "fizzquirk": {
        "video_description_template": "Descubra fatos incríveis sobre {topic_title}!\n\nNeste vídeo:\n- {fact_text_for_description}\n\n#FizzQuirk #Curiosidades #{topic_hashtag} #FatosIncriveis",
        "video_tags_list": ["fizzquirk", "curiosidades", "fatos", "aprender", "shorts"], 
        "music_options": [
            "animado.mp3", 
            "fundo_misterioso.mp3",
            "tema_calmo.mp3"
        ],
        "default_music_if_list_empty": None,
        "music_volume": 0.07,
        "gtts_language": "pt-br", 
        "text_font_path_for_image_placeholder": None, 
        "num_facts_per_video": 15, # Ajuste para duração: 15 fatos * ~9s/fato = ~2.25 min. Para 3-7 min, use 20-45.
        "duration_per_fact_slide_min": 7, 
        "pause_after_fact": 1.2, 
        "category_id": "27", 
        "youtube_privacy_status": "public", 
        "gcp_project_id": os.environ.get("GCP_PROJECT_ID"),
        "gcp_location": os.environ.get("GCP_LOCATION", "us-central1"),
        "imagen_model_name": "imagegeneration@006" 
    },
}

def get_authenticated_service(client_secrets_path, token_path):
    logging.info(f"DEBUG_PRINT: [FUNC_AUTH] Tentando autenticar com token: {token_path} e client_secrets: {client_secrets_path}")
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info(f"Credenciais carregadas de {token_path}")
        except Exception as e:
            logging.warning(f"Não foi possível carregar token de {token_path}: {e}. Tentando fluxo de autorização.")
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logging.info("Token expirado, tentando refresh...")
                creds.refresh(Request())
                logging.info("Token atualizado com sucesso via refresh.")
            except Exception as e:
                logging.error(f"Falha ao atualizar token: {e}. Será necessário novo fluxo de autorização se não houver client_secrets.")
                creds = None 
        
        if not creds or not creds.valid: 
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: client_secret.json não encontrado em {client_secrets_path}")
                return None
            logging.info("Executando novo fluxo de autorização (pode ser interativo para ambiente local)...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
                if "GITHUB_ACTIONS" in os.environ: 
                     logging.error("ERRO: Novo fluxo de autorização interativo não é suportado em CI. Pré-autorize o token.json.")
                     return None
                creds = flow.run_local_server(port=0) 
            except Exception as e_flow:
                logging.error(f"Falha no fluxo de autorização: {e_flow}")
                return None
        
        if creds: 
            try:
                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                with open(token_path, 'w') as token_file:
                    token_file.write(creds.to_json())
                logging.info(f"Token salvo/atualizado em {token_path}")
            except Exception as e_save:
                logging.error(f"Erro ao salvar token em {token_path}: {e_save}")

    if not creds or not creds.valid:
        logging.error("Falha final ao obter credenciais válidas para YouTube.")
        return None
        
    logging.info("Serviço YouTube autenticado com sucesso.")
    return build('youtube', 'v3', credentials=creds)

def choose_topic(topic_file, history_file, history_len):
    if not os.path.exists(topic_file):
        logging.error(f"Arquivo de tópicos '{topic_file}' não encontrado!")
        return "Curiosidades Gerais" 
    
    with open(topic_file, 'r', encoding='utf-8') as f:
        all_topics = [line.strip() for line in f if line.strip()]
    
    if not all_topics:
        logging.error(f"Arquivo de tópicos '{topic_file}' está vazio!")
        return "Curiosidades Aleatórias" 

    recent_history = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as hf:
            recent_history = [line.strip() for line in hf]
            # Pega apenas os N últimos para evitar repetição recente
            recent_history = recent_history[-history_len:] 
            
    available_topics = [topic for topic in all_topics if topic not in recent_history]
    
    selected_topic = None
    if not available_topics: 
        logging.warning(f"Todos os {len(all_topics)} tópicos foram usados nos últimos {history_len} vídeos. Reciclando da lista completa.")
        if all_topics: # Garante que all_topics não está vazio
            selected_topic = random.choice(all_topics)
        else: # Caso extremo: all_topics está vazio (embora já verificado acima)
            selected_topic = "Fatos Diversos" 
    else:
        selected_topic = random.choice(available_topics)
        
    # Atualiza o histórico
    try:
        with open(history_file, 'a', encoding='utf-8') as hf:
            hf.write(f"{selected_topic}\n")
        # Opcional: Limpa o histórico antigo para não crescer indefinidamente demais
        with open(history_file, 'r', encoding='utf-8') as hf:
            lines = hf.readlines()
        # Mantém um histórico um pouco maior que o usado para verificação, para dar margem
        if len(lines) > max(history_len * 2, 20): # Ex: mantém no máximo 20 ou 2x o history_len
            with open(history_file, 'w', encoding='utf-8') as hf:
                hf.writelines(lines[-(max(history_len * 2, 20)):])
    except Exception as e:
        logging.error(f"Erro ao atualizar o arquivo de histórico '{history_file}': {e}")
        
    logging.info(f"Tópico escolhido: {selected_topic}")
    return selected_topic

def get_facts_for_video(topic, language, num_facts=1):
    logging.info(f"Obtendo {num_facts} fatos para o TEMA: '{topic}' (Idioma: {language})")
    
    # ----- INÍCIO DO PLACEHOLDER DE FATOS -----
    # Esta seção ainda é um placeholder. Para conteúdo real, você precisará:
    # 1. Criar um banco de dados de fatos categorizados por tema.
    # 2. OU Integrar com uma API de LLM (como Gemini) para gerar fatos baseados no 'topic'.
    #    Prompt exemplo para Gemini: "Gere {num_facts} fatos curtos, interessantes e verdadeiros sobre '{topic}' em {language}.
    #                                 Cada fato deve ser uma frase concisa e surpreendente. Formato: lista de strings."
    # ------------------------------------------
    
    # Exemplo de fatos placeholder genéricos, mas usando o tema na formulação
    generic_fact_templates_en = [
        f"Regarding the topic of {topic}, it's known that a group of flamingos is called a 'flamboyance'.",
        f"An interesting point when discussing {topic} is that honey is the only food that never spoils.",
        f"Speaking of {topic}, did you know the unicorn is the national animal of Scotland?",
        f"A curious fact related to {topic}: a shrimp's heart is in its head.",
        f"When considering {topic}, remember that slugs actually have four noses.",
        f"It's nearly impossible for most people to lick their own elbow, a fun thought related to {topic}!",
        f"A bolt of lightning, relevant to discussions about energy and {topic}, contains enough power to toast 100,000 bread slices.",
        f"The oldest living tree, a testament to endurance and {topic}, is over 4,800 years old.",
        f"Butterflies, in the context of senses and {topic}, taste with their feet.",
        f"An ostrich's eye is bigger than its brain, a quirky detail when exploring {topic}.",
        f"It's surprising that most lipstick contains fish scales, a fact that touches upon ingredients and {topic}.",
        f"Rats multiply so quickly; relevant to cycles and {topic}, in 18 months, two rats could have over a million descendants.",
        f"The 'Mona Lisa' has no eyebrows, an art mystery related to perceptions and {topic}.",
        f"Humans share 50% of their DNA with bananas, a genetic curiosity connected to life and {topic}.",
        f"A crocodile cannot stick its tongue out, a peculiar animal fact for {topic}."
    ]
    generic_fact_templates_pt_br = [
        f"Sobre o tema '{topic}', você sabia que um grupo de flamingos é chamado de 'bando'?",
        f"Um ponto interessante ao discutir '{topic}' é que o mel é o único alimento que nunca estraga.",
        f"Falando em '{topic}', o unicórnio é o animal nacional da Escócia.",
        f"Um fato curioso relacionado a '{topic}': o coração de um camarão fica na cabeça.",
        f"Ao considerar '{topic}', lembre-se que lesmas têm quatro narizes.",
        f"É quase impossível para a maioria das pessoas lamber o próprio cotovelo, um pensamento divertido relacionado a '{topic}'!",
        f"Um raio, relevante para discussões sobre energia e '{topic}', contém energia suficiente para torrar 100.000 fatias de pão.",
        f"A árvore viva mais antiga, um testamento à resistência e '{topic}', tem mais de 4.800 anos.",
        f"Borboletas, no contexto dos sentidos e '{topic}', sentem o sabor com os pés.",
        f"O olho de um avestruz é maior que seu cérebro, um detalhe peculiar ao explorar '{topic}'.",
        f"É surpreendente que a maioria dos batons contenha escamas de peixe, um fato que toca em ingredientes e '{topic}'.",
        f"Ratos se multiplicam rapidamente; relevante para ciclos e '{topic}', em 18 meses, dois ratos podem ter mais de um milhão de descendentes.",
        f"A 'Mona Lisa' não tem sobrancelhas, um mistério da arte relacionado a percepções e '{topic}'.",
        f"Humanos compartilham 50% de seu DNA com bananas, uma curiosidade genética conectada à vida e '{topic}'.",
        f"Um crocodilo não consegue colocar a língua para fora, um fato animal peculiar para '{topic}'."
    ]
    
    logging.warning(f"ALERTA: Usando lista de fatos placeholder levemente adaptada para o tema '{topic}'. Substitua por geração de fatos reais.")
    
    base_facts_list = generic_fact_templates_pt_br if language == "pt-br" else generic_fact_templates_en
    
    if not base_facts_list:
        logging.error(f"Nenhuma lista de fatos placeholder encontrada para o idioma '{language}'.")
        return []
    
    # Garante que tenhamos fatos suficientes, repetindo se necessário
    selected_facts = []
    if len(base_facts_list) >= num_facts:
        selected_facts = random.sample(base_facts_list, num_facts)
    else: 
        logging.warning(f"Fatos placeholder insuficientes ({len(base_facts_list)}) para {num_facts} fatos sobre '{topic}'. Fatos serão repetidos.")
        for i in range(num_facts):
            selected_facts.append(base_facts_list[i % len(base_facts_list)]) # Repete da lista base
        random.shuffle(selected_facts) # Embaralha mesmo se repetido

    return selected_facts


def generate_audio_from_text(text, lang, audio_file_path):
    # ... (código mantido) ...
    logging.info(f"Gerando áudio para: '{text[:50]}...' (Idioma: {lang})")
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
        if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
            logging.info(f"Áudio salvo em: {audio_file_path}")
            return audio_file_path
        logging.error(f"Falha ao salvar áudio ou arquivo vazio: {audio_file_path}")
    except Exception as e:
        logging.error(f"Erro em gTTS para '{lang}': {e}", exc_info=True)
    return None

def generate_dynamic_image_placeholder(fact_text, width, height, font_path_config, duration, fps_value):
    # ... (código mantido) ...
    logging.info(f"Gerando imagem PLACEHOLDER para: '{fact_text[:30]}...'")
    temp_img_path = None 
    try:
        r1, g1, b1 = random.randint(40, 120), random.randint(40, 120), random.randint(40, 120)
        r2, g2, b2 = min(255, r1 + random.randint(40,80)), min(255, g1 + random.randint(40,80)), min(255, b1 + random.randint(40,80))
        
        img = PILImage.new("RGB", (width, height))
        draw = PILImageDraw.Draw(img)
        for y_grad in range(height):
            r_curr = int(r1 + (r2 - r1) * y_grad / height); g_curr = int(g1 + (g2 - g1) * y_grad / height); b_curr = int(b1 + (b2 - b1) * y_grad / height)
            draw.line([(0, y_grad), (width, y_grad)], fill=(r_curr, g_curr, b_curr))

        padding = int(width * 0.08); max_text_width = width - 2 * padding
        font_to_use = None; current_font_size = int(height / 17) 
        try:
            if font_path_config and os.path.exists(font_path_config):
                font_to_use = PILImageFont.truetype(font_path_config, current_font_size)
                logging.info(f"Usando fonte customizada para placeholder: {font_path_config} com tamanho {current_font_size}")
            else:
                if font_path_config: logging.warning(f"Fonte '{font_path_config}' não encontrada.")
                try:
                    arial_path = os.path.join(ASSETS_DIR, "fonts", "arial.ttf") 
                    if os.path.exists(arial_path):
                        font_to_use = PILImageFont.truetype(arial_path, current_font_size)
                        logging.info(f"Usando fonte Arial de '{arial_path}' para placeholder.")
                    else: 
                        logging.warning(f"Arial não encontrada em '{arial_path}'. Usando fonte padrão Pillow.")
                        font_to_use = PILImageFont.load_default(size=current_font_size)
                except IOError: 
                    logging.warning(f"Erro ao carregar Arial. Usando fonte padrão Pillow.")
                    font_to_use = PILImageFont.load_default(size=current_font_size)
        except Exception as e_font: 
            logging.warning(f"Erro geral ao carregar fonte '{font_path_config}': {e_font}. Usando padrão Pillow.")
            current_font_size = max(15, int(height / 22)) 
            font_to_use = PILImageFont.load_default(size=current_font_size)


        lines = []; words = fact_text.split(); current_line = ""
        for word in words:
            try: 
                bbox_test = draw.textbbox((0,0), current_line + word + " ", font=font_to_use)
                text_w = bbox_test[2] - bbox_test[0]
            except AttributeError: text_w = draw.textlength(current_line + word + " ", font=font_to_use) 

            if text_w <= max_text_width: current_line += word + " "
            else: lines.append(current_line.strip()); current_line = word + " "
        lines.append(current_line.strip())
        
        line_heights = []
        for line in lines:
            try: bbox_line = draw.textbbox((0,0), line, font=font_to_use); line_h = bbox_line[3] - bbox_line[1]
            except AttributeError: ascent, descent = font_to_use.getmetrics(); line_h = ascent + descent
            line_heights.append(line_h)

        spacing = int(current_font_size * 0.2) 
        total_text_height = sum(line_heights) + (len(lines) - 1) * spacing
        
        y_text_start = (height - total_text_height) / 2
        text_color=(255, 255, 255); stroke_color=(0,0,0); stroke_width_val=max(1, int(current_font_size/20))
        
        current_y = y_text_start
        for i, line in enumerate(lines):
            try: bbox_line = draw.textbbox((0,0), line, font=font_to_use); line_w = bbox_line[2] - bbox_line[0]
            except AttributeError: line_w = draw.textlength(line, font=font_to_use)
            x_text = (width - line_w) / 2
            for dx_s in range(-stroke_width_val, stroke_width_val + 1):
                for dy_s in range(-stroke_width_val, stroke_width_val + 1):
                    if dx_s*dx_s + dy_s*dy_s <= stroke_width_val*stroke_width_val :
                         draw.text((x_text + dx_s, current_y + dy_s), line, font=font_to_use, fill=stroke_color, align="center")
            draw.text((x_text, current_y), line, font=font_to_use, fill=text_color, align="center")
            current_y += line_heights[i] + spacing

        temp_img_dir = GENERATED_IMAGES_DIR; os.makedirs(temp_img_dir, exist_ok=True)
        temp_img_path = os.path.join(temp_img_dir, f"placeholder_{random.randint(1000,9999)}_{int(time.time()*1000)}.png")
        img.save(temp_img_path)
        image_clip = ImageClip(temp_img_path).set_duration(duration).set_fps(fps_value) 
        return image_clip, temp_img_path
    except Exception as e:
        logging.error(f"Erro ao gerar imagem placeholder: {e}", exc_info=True)
        return ColorClip(size=(width, height), color=(random.randint(50,100),random.randint(50,100),random.randint(50,100)), duration=duration).set_fps(fps_value), None

def generate_image_with_vertex_ai_imagen(fact_text, duration, config, font_path_for_fallback, fps_value):
    # ... (código mantido) ...
    logging.info(f"Tentando gerar imagem com Vertex AI para: '{fact_text[:30]}...'")
    project_id = config.get("gcp_project_id")
    location = config.get("gcp_location")
    imagen_model_name = config.get("imagen_model_name", "imagegeneration@006") 

    if not VERTEX_AI_SDK_AVAILABLE:
        logging.warning("SDK Vertex AI (`google-cloud-aiplatform`) não disponível. Usando placeholder de imagem.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration, fps_value)

    if not all([project_id, location, imagen_model_name]):
        logging.error("ID do projeto GCP, localização ou nome do modelo Imagen não configurados. Usando placeholder.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration, fps_value)
    
    logging.info("*"*10 + " CHAMANDO VERTEX AI IMAGEN (ADAPTE ESTE CÓDIGO!) " + "*"*10)
    
    try:
        aiplatform.init(project=project_id, location=location)
        model = aiplatform.ImageGenerationModel.from_pretrained(imagen_model_name)
        prompt = (
            f"A visually stunning and captivating image (9:16 aspect ratio for YouTube Shorts) "
            f"that creatively illustrates the interesting fact: \"{fact_text}\". "
            f"Style: digital art, cinematic lighting, eye-catching, vibrant. Avoid text overlays on the image itself."
        )
        logging.info(f"Prompt para Imagen: {prompt}")
        response = model.generate_images(prompt=prompt, number_of_images=1)
        
        if response.images:
            image_obj = response.images[0]
            temp_img_dir = GENERATED_IMAGES_DIR; os.makedirs(temp_img_dir, exist_ok=True)
            gen_img_path = os.path.join(temp_img_dir, f"vertex_img_{int(time.time()*1000)}.png")
            
            if hasattr(image_obj, '_image_bytes') and image_obj._image_bytes:
                 with open(gen_img_path, "wb") as f: f.write(image_obj._image_bytes)
            elif hasattr(image_obj, 'save'): image_obj.save(location=gen_img_path)
            else:
                logging.error("Não foi possível salvar a imagem do Vertex AI."); return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration, fps_value)

            logging.info(f"Imagem gerada com Vertex AI e salva em: {gen_img_path}")
            img_clip = ImageClip(gen_img_path).set_duration(duration).set_fps(fps_value)
            final_img_clip = img_clip.resize(height=1920) 
            if final_img_clip.w > 1080: final_img_clip = final_img_clip.crop(x_center=final_img_clip.w/2, width=1080)
            elif final_img_clip.w < 1080: final_img_clip = final_img_clip.resize(width=1080)
            if final_img_clip.h > 1920: final_img_clip = final_img_clip.crop(y_center=final_img_clip.h/2, height=1920)
            return final_img_clip, gen_img_path 
        else:
            logging.error("Vertex AI Imagen API não retornou imagens."); return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration, fps_value)
    except Exception as e:
        logging.error(f"Erro ao gerar imagem com Vertex AI Imagen: {e}", exc_info=True); return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration, fps_value)

def create_video_from_content(facts, narration_audio_files, channel_config, channel_title="Video"):
    logging.info(f"--- Criando vídeo para '{channel_title}' com {len(facts)} fatos ---")
    W, H = 1080, 1920; FPS_VIDEO = 24
    default_slide_duration = channel_config.get("duration_per_fact_slide_min", 6)
    pause_after_fact = channel_config.get("pause_after_fact", 1.0)
    font_for_placeholder = channel_config.get("text_font_path_for_image_placeholder")
    if font_for_placeholder and not os.path.isabs(font_for_placeholder):
        font_for_placeholder = os.path.join(ASSETS_DIR, "fonts", os.path.basename(font_for_placeholder))

    video_slide_clips = []
    audio_slide_segments = [] 
    temp_image_paths_to_clean = []
    
    for i, fact_text in enumerate(facts):
        narration_file = narration_audio_files[i]
        if not (narration_file and os.path.exists(narration_file) and os.path.getsize(narration_file) > 0):
            logging.warning(f"Narração inválida para '{fact_text[:30]}...'. Pulando."); continue
        
        narration_clip_instance = AudioFileClip(narration_file)
        slide_duration = max(narration_clip_instance.duration + pause_after_fact, default_slide_duration)
        
        image_clip_result, temp_img_path = generate_image_with_vertex_ai_imagen(
            fact_text, slide_duration, channel_config,
            font_for_placeholder, FPS_VIDEO
        )
        if temp_img_path: temp_image_paths_to_clean.append(temp_img_path)
        if image_clip_result is None: 
            logging.error(f"Imagem nula para '{fact_text[:30]}...'. Pulando."); continue

        image_clip_result = image_clip_result.set_duration(slide_duration).set_fps(FPS_VIDEO)
        video_slide_clips.append(image_clip_result) 

        narration_part_for_slide = narration_clip_instance.subclip(0, min(narration_clip_instance.duration, slide_duration))
        current_segment_audio = None
        if narration_part_for_slide.duration < slide_duration:
            silence_needed = slide_duration - narration_part_for_slide.duration
            n_channels = getattr(narration_part_for_slide, 'nchannels', 2)
            audio_fps_val = getattr(narration_part_for_slide, 'fps', 44100)
            make_frame_silent = lambda t: np.zeros(n_channels)
            padding = AudioClip(make_frame_silent, duration=silence_needed, fps=audio_fps_val)
            current_segment_audio = concatenate_audioclips([narration_part_for_slide, padding])
        else:
            current_segment_audio = narration_part_for_slide
        
        audio_slide_segments.append(current_segment_audio)
        
    if not video_slide_clips: logging.error("Nenhum slide de vídeo foi gerado."); return None

    final_visual_part = concatenate_videoclips(video_slide_clips, method="compose").set_fps(FPS_VIDEO)
    final_narration_audio = concatenate_audioclips(audio_slide_segments)
    
    total_video_duration_actual = final_visual_part.duration

    if final_narration_audio.duration > total_video_duration_actual:
        final_narration_audio = final_narration_audio.subclip(0, total_video_duration_actual)
    elif final_narration_audio.duration < total_video_duration_actual:
        silence_needed = total_video_duration_actual - final_narration_audio.duration
        if silence_needed > 0.01: 
            n_channels = getattr(final_narration_audio, 'nchannels', 2)
            audio_fps_val = getattr(final_narration_audio, 'fps', 44100)
            make_frame_silent = lambda t: np.zeros(n_channels)
            padding = AudioClip(make_frame_silent, duration=silence_needed, fps=audio_fps_val)
            final_narration_audio = concatenate_audioclips([final_narration_audio, padding])

    final_video_with_narration = final_visual_part.set_audio(final_narration_audio)
    
    selected_music_path = channel_config.get("selected_music_path")
    music_volume = channel_config.get("music_volume", 0.08)
    final_product_video = final_video_with_narration

    if selected_music_path and os.path.exists(selected_music_path):
        try:
            music_clip = AudioFileClip(selected_music_path).volumex(music_volume)
            if music_clip.duration < total_video_duration_actual:
                music_final = music_clip.loop(duration=total_video_duration_actual)
            else:
                music_final = music_clip.subclip(0, total_video_duration_actual)
            
            current_audio = final_product_video.audio 
            if current_audio:
                final_audio_track = CompositeAudioClip([current_audio, music_final])
                final_product_video = final_product_video.set_audio(final_audio_track)
            else: 
                final_product_video = final_product_video.set_audio(music_final)
            logging.info(f"Música '{os.path.basename(selected_music_path)}' adicionada.")
        except Exception as e_music:
            logging.warning(f"Erro ao adicionar música '{selected_music_path}': {e_music}.")
    
    os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
    video_fname = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}.mp4"
    video_output_path = os.path.join(GENERATED_VIDEOS_DIR, video_fname)
    
    logging.info(f"Escrevendo vídeo final: {video_output_path} (Duração: {final_product_video.duration:.2f}s)")
    final_product_video.write_videofile(video_output_path, codec='libx264', audio_codec='aac', 
                                     fps=FPS_VIDEO, preset='ultrafast', threads=(os.cpu_count() or 2), logger='bar')
    logging.info("Vídeo final escrito.")

    for img_path in temp_image_paths_to_clean:
        if os.path.exists(img_path):
            try: os.remove(img_path); logging.info(f"Imagem temp removida: {img_path}")
            except Exception as e: logging.warning(f"Falha ao remover img temp {img_path}: {e}")
            
    return video_output_path

def generate_video_title(facts, topic_title, channel_name="default"):
    if not facts:
        timestamp = datetime.date.today().strftime('%Y-%m-%d')
        # Usa o nome do canal se o tópico for muito genérico ou não existir
        title_base = topic_title if topic_title and topic_title.lower() not in ["curiosidades gerais", "curiosidades aleatórias"] else channel_name.capitalize()
        return f"{title_base} - Curiosidades do Dia {timestamp}"

    # Tenta usar o tópico no título de forma mais proeminente
    if topic_title and topic_title.lower() not in ["curiosidades gerais", "curiosidades aleatórias", "fatos diversos"]:
        title_base = topic_title
    else: # Se o tópico for genérico, usa parte do primeiro fato
        first_fact_preview = " ".join(facts[0].split()[:5]) # Menos palavras do fato
        if len(facts[0].split()) > 5: first_fact_preview += "..."
        title_base = f"{topic_title}: {first_fact_preview}"
    
    # Remove pontuação final comum para títulos
    if title_base.endswith(('.', ',', ';', ':')):
        title_base = title_base[:-1]
    
    # Adiciona um toque do canal ou um slogan
    generated_title = f"{title_base.strip()} | Curiosidades FizzQuirk!" 
        
    max_title_length = 95 
    if len(generated_title) > max_title_length:
        cut_title = generated_title[:max_title_length-3]
        last_space = cut_title.rfind(' ')
        generated_title = cut_title[:last_space] + "..." if last_space != -1 else cut_title + "..."
            
    logging.info(f"Título gerado: '{generated_title}'")
    return generated_title

def generate_video_description(facts, config, channel_name_arg, topic_title):
    template = config.get("video_description_template", "Descubra fatos incríveis sobre {topic_title}!\n\nNeste vídeo:\n{fact_text_for_description}\n\n#Curiosidades #{topic_hashtag}")
    
    facts_summary = "\n- ".join(facts) # Lista todos os fatos, um por linha
    if not facts:
        facts_summary = "Muitas curiosidades interessantes exploradas neste vídeo!"

    # Cria uma hashtag a partir do tópico, removendo espaços e caracteres especiais, e minúsculas
    topic_hashtag_clean = "".join(c for c in topic_title if c.isalnum()).lower()
    if not topic_hashtag_clean: topic_hashtag_clean = channel_name_arg # Fallback para nome do canal
    
    description = template.format(
        fact_text_for_description=facts_summary, 
        topic_title=topic_title,
        topic_hashtag=topic_hashtag_clean
    )
    
    # Adicionar tags base do canal se não estiverem já no template por placeholders
    base_tags_from_config = config.get("video_tags_list", [])
    for tag in base_tags_from_config:
        if f"#{tag.lower().replace(' ', '')}" not in description.lower(): # Evita duplicar e normaliza
            description += f" #{tag.lower().replace(' ', '')}"
            
    logging.info(f"Descrição gerada (primeiros 250 chars): '{description[:250]}...'")
    return description

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status="public"):
    logging.info(f"--- Upload INICIADO para: '{title}', Status: '{privacy_status}' ---")
    print(f"PRINT: Iniciando upload para o vídeo: {title}") 
    sys.stdout.flush() 
    response_final_upload = None 
    try:
        if not video_path or not os.path.exists(video_path):
            logging.error(f"ERRO Upload: Arquivo de vídeo NÃO encontrado em {video_path}")
            print(f"PRINT ERROR: Arquivo de vídeo NÃO encontrado em {video_path}")
            sys.stderr.flush()
            return None
        
        logging.info(f"Caminho do vídeo para upload: {video_path}")
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        logging.info("MediaFileUpload objeto criado.")
        print("PRINT: MediaFileUpload objeto criado.")
        sys.stdout.flush()

        request_body = {
            'snippet': {'title': title, 'description': description, 'tags': tags, 'categoryId': category_id},
            'status': {'privacyStatus': privacy_status}
        }
        logging.info(f"Corpo da requisição para YouTube: {json.dumps(request_body, indent=2, ensure_ascii=False)}") # Log mais detalhado
        print(f"PRINT: Corpo da requisição para YouTube: {json.dumps(request_body, indent=2, ensure_ascii=False)}")
        sys.stdout.flush()

        request = youtube_service.videos().insert(part=','.join(request_body.keys()), body=request_body, media_body=media)
        logging.info("Objeto de requisição de upload do YouTube criado.")
        print("PRINT: Objeto de requisição de upload do YouTube criado.")
        sys.stdout.flush()
        
        done = False
        upload_progress_counter = 0
        max_retries_no_progress = 10 # Número de vezes que tentaremos next_chunk sem progresso aparente
        
        while not done:
            upload_progress_counter += 1
            logging.info(f"Tentativa de next_chunk #{upload_progress_counter}")
            print(f"PRINT: Tentativa de next_chunk #{upload_progress_counter}")
            sys.stdout.flush()
            status, chunk_response = None, None # Resetar antes de cada chamada
            try:
                status, chunk_response = request.next_chunk() 
            except Exception as e_chunk:
                logging.error(f"ERRO em request.next_chunk(): {e_chunk}", exc_info=True)
                print(f"PRINT ERROR em next_chunk(): {e_chunk}")
                sys.stderr.flush()
                # Considerar um número limitado de retentativas para erros de chunk aqui
                if upload_progress_counter > max_retries_no_progress: # Exemplo, se falhar X vezes seguidas
                    logging.error("Muitas falhas em next_chunk. Abortando upload.")
                    return None
                time.sleep(5 * upload_progress_counter) # Backoff exponencial simples
                continue # Tenta o próximo chunk
            
            logging.info(f"next_chunk retornou: status={status}, chunk_response é None? {chunk_response is None}")
            print(f"PRINT: next_chunk retornou: status={status}, chunk_response é None? {chunk_response is None}")
            sys.stdout.flush()

            if status: 
                logging.info(f"Upload: {int(status.progress() * 100)}%")
                print(f"PRINT: Upload: {int(status.progress() * 100)}%")
                sys.stdout.flush()
            if chunk_response is not None: 
                logging.info(f"chunk_response recebido (não None), upload provavelmente concluído. Resposta: {chunk_response}")
                print(f"PRINT: chunk_response recebido (não None). Resposta: {chunk_response}")
                sys.stdout.flush()
                done = True
                response_final_upload = chunk_response
            # Verifica se o upload está travado (sem status e sem resposta por muitas tentativas)
            elif status is None and upload_progress_counter > max_retries_no_progress : 
                logging.error(f"Muitas tentativas de next_chunk ({upload_progress_counter}) sem progresso ou resposta final. Abortando upload.")
                print(f"PRINT ERROR: Muitas tentativas de next_chunk ({upload_progress_counter}) sem progresso ou resposta final.")
                sys.stderr.flush()
                done = True # Força a saída do loop
                response_final_upload = None # Garante que seja None
        
        logging.info(f"Loop de upload concluído. response_final_upload é None? {response_final_upload is None}")
        print(f"PRINT: Loop de upload concluído. response_final_upload é None? {response_final_upload is None}")
        sys.stdout.flush()

        if response_final_upload: 
            video_id = response_final_upload.get('id')
            if video_id:
                logging.info(f"Upload completo! Vídeo ID: {video_id}")
                correct_youtube_link = f"http://www.youtube.com/watch?v={video_id}"
                logging.info(f"Link do vídeo: {correct_youtube_link}")
                print(f"PRINT SUCCESS: Upload completo! Vídeo ID: {video_id}")
                print(f"PRINT SUCCESS: Link do vídeo: {correct_youtube_link}")
                sys.stdout.flush()
                return video_id
            else:
                logging.error(f"Upload pode ter falhado ou API não retornou ID de vídeo. Resposta final: {response_final_upload}")
                print(f"PRINT ERROR: Upload pode ter falhado ou API não retornou ID de vídeo. Resposta final: {response_final_upload}")
                sys.stderr.flush()
                return None
        else: 
            logging.error("Upload não retornou uma resposta final válida (response_final_upload é None).")
            print("PRINT ERROR: Upload não retornou uma resposta final válida (response_final_upload é None).")
            sys.stderr.flush()
            return None
    except Exception as e:
        logging.error(f"ERRO CRÍTICO durante upload para o YouTube: {e}", exc_info=True)
        print(f"PRINT CRITICAL ERROR: Erro durante upload: {e}")
        sys.stderr.flush()
        return None

def main(channel_name_arg):
    logging.info(f"--- Iniciando para canal: {channel_name_arg} ---")
    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Configuração para o canal '{channel_name_arg}' não encontrada."); sys.exit(1)

    os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "music"), exist_ok=True)

    chosen_topic = choose_topic(TOPIC_FILE_PATH, HISTORY_FILE_PATH, HISTORY_LENGTH)
    logging.info(f"Tema selecionado para o vídeo: {chosen_topic}")
    if not chosen_topic or "Gerais" in chosen_topic or "Aleatórias" in chosen_topic: # Se o fallback foi usado
        logging.warning(f"Usando tema de fallback '{chosen_topic}'. Certifique-se que 'topics.txt' existe e tem conteúdo.")

    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices: 
        music_file_name = random.choice(music_choices)
        potential_music_path = os.path.join(ASSETS_DIR, "music", music_file_name) 
        if os.path.exists(potential_music_path):
            selected_music_path = potential_music_path
            logging.info(f"Música selecionada: {selected_music_path}")
        else:
            logging.warning(f"Arquivo de música '{music_file_name}' não encontrado em '{os.path.join(ASSETS_DIR, 'music')}'. Prosseguindo sem música.")
            selected_music_path = None 
    config["selected_music_path"] = selected_music_path 

    client_secrets_path = CLIENT_SECRET_FILE
    token_path = TOKEN_FILE
    
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: logging.error("Falha YouTube auth."); sys.exit(1)

    num_facts = config.get("num_facts_per_video", 15) # Aumentado para vídeos mais longos
    facts_list = get_facts_for_video(chosen_topic, config["gtts_language"], num_facts)
    if not facts_list: logging.error(f"Nenhum fato obtido para o tema '{chosen_topic}'. Encerrando."); sys.exit(1)

    narration_audio_files = []
    actual_facts_with_audio = [] 

    for i, fact in enumerate(facts_list):
        audio_fname = f"{channel_name_arg}_fact_{i+1}_{int(time.time()*1000)}_{random.randint(0,1000)}.mp3"
        audio_file_path = os.path.join(GENERATED_AUDIO_DIR, audio_fname)
        path = generate_audio_from_text(fact, config["gtts_language"], audio_file_path)
        if path: 
            narration_audio_files.append(path)
            actual_facts_with_audio.append(fact)
        else: 
            logging.warning(f"Falha áudio para fato: '{fact[:30]}...'.")
    
    if not narration_audio_files or len(narration_audio_files) != len(actual_facts_with_audio) or not actual_facts_with_audio :
         logging.error(f"Geração de áudio inconsistente ou falhou. Fatos válidos: {len(actual_facts_with_audio)}, Áudios: {len(narration_audio_files)}. Abortando.")
         for audio_f in narration_audio_files: 
             if os.path.exists(audio_f): os.remove(audio_f)
         sys.exit(1)

    video_output_path = create_video_from_content(
        facts=actual_facts_with_audio, 
        narration_audio_files=narration_audio_files, 
        channel_config=config, 
        channel_title=channel_name_arg
    )
    
    for audio_f in narration_audio_files:
        if os.path.exists(audio_f):
            try: 
                os.remove(audio_f)
                logging.info(f"Áudio temp removido: {audio_f}")
            except Exception as e: 
                logging.warning(f"Falha ao remover áudio temp {audio_f}: {e}")

    if not video_output_path: 
        logging.error("Falha criar vídeo.")
        sys.exit(1)

    video_title = generate_video_title(actual_facts_with_audio, chosen_topic, channel_name=channel_name_arg)
    video_description = generate_video_description(actual_facts_with_audio, config, channel_name_arg, chosen_topic) 
    
    # Prepara a lista de tags final
    final_tags = list(config.get("video_tags_list", [])) 
    topic_hashtag_clean = "".join(c for c in chosen_topic if c.isalnum()).lower()
    if topic_hashtag_clean and topic_hashtag_clean not in final_tags:
        final_tags.append(topic_hashtag_clean)
    # Adiciona tags baseadas nos primeiros fatos, se desejar (exemplo)
    # for fact in actual_facts_with_audio[:2]: # Pega palavras dos 2 primeiros fatos
    #     words = fact.lower().split()
    #     for word in words:
    #         if len(word) > 4 and word.isalnum() and word not in final_tags and word not in ['sobre', 'fatos', 'curiosidades', topic_hashtag_clean]:
    #             final_tags.append(word)
    #             if len(final_tags) > 15: break # Limita o número de tags
    #     if len(final_tags) > 15: break
    
    logging.info(f"==> Preparando para fazer upload do vídeo: '{video_title}' para o arquivo: {video_output_path}")
    print(f"PRINT: Iniciando chamada para upload_video com título: {video_title}")
    sys.stdout.flush()

    video_id_uploaded = upload_video(
        youtube_service, 
        video_output_path, 
        video_title,
        video_description, 
        final_tags,       
        config.get("category_id"),               
        config.get("youtube_privacy_status", "public")
    )
    logging.info(f"==> Resultado do upload_video (video_id_uploaded): {video_id_uploaded}")
    print(f"PRINT: Resultado do upload_video (video_id_uploaded): {video_id_uploaded}")
    sys.stdout.flush()

    if video_id_uploaded:
        logging.info(f"--- SUCESSO! Canal '{channel_name_arg}'. VÍDEO PÚBLICO ID: {video_id_uploaded} ---")
        print(f"PRINT SUCCESS: --- SUCESSO! Canal '{channel_name_arg}'. VÍDEO PÚBLICO ID: {video_id_uploaded} ---")
        if os.path.exists(video_output_path): 
            logging.info(f"Vídeo local {video_output_path} mantido para inspeção.")
    else:
        logging.error(f"--- FALHA no upload para o canal '{channel_name_arg}'. Script terminando com erro. ---")
        print(f"PRINT ERROR: --- FALHA no upload para o canal '{channel_name_arg}'. ---")
        sys.stderr.flush()
        sys.exit(1)
    
    logging.info(f"--- Fim do processo para o canal '{channel_name_arg}' ---")
    print(f"PRINT: --- Fim do processo para o canal '{channel_name_arg}' ---")
    sys.stdout.flush()
    time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatiza a criação e upload de vídeos de curiosidades para o YouTube.")
    parser.add_argument("--channel", required=True, help="Nome do canal (chave em CHANNEL_CONFIGS).")
    args = None
    try:
        args = parser.parse_args()
        main(args.channel)
    except SystemExit as e:
        if e.code is None or e.code == 0: 
             logging.info(f"Script para '{args.channel if args else 'N/A'}' concluído (código de saída {e.code}).")
             print(f"PRINT: Script para '{args.channel if args else 'N/A'}' concluído (código de saída {e.code}).")
        else: 
             logging.error(f"Script para '{args.channel if args else 'N/A'}' encerrado com erro (código {e.code}).")
             print(f"PRINT ERROR: Script para '{args.channel if args else 'N/A'}' encerrado com erro (código {e.code}).")
             if e.code != 0: raise 
    except Exception as e_main_block:
        logging.error(f"ERRO INESPERADO NO BLOCO PRINCIPAL para '{args.channel if args else 'N/A'}': {e_main_block}", exc_info=True)
        print(f"PRINT CRITICAL ERROR: ERRO INESPERADO NO BLOCO PRINCIPAL para '{args.channel if args else 'N/A'}': {e_main_block}")
        sys.exit(2)
    finally:
        print("PRINT: Bloco finally do __main__ alcançado.")
        sys.stdout.flush()
        sys.stderr.flush()
