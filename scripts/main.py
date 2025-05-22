import os
import argparse
import logging
import json
import sys
import time
import random
import numpy as np

from gtts import gTTS
from moviepy.editor import (AudioFileClip, TextClip, CompositeVideoClip,
                            ColorClip, ImageClip, CompositeAudioClip,
                            concatenate_videoclips, concatenate_audioclips, AudioClip)
from moviepy.config import change_settings
import moviepy.config as MOPY_CONFIG

from PIL import Image as PILImage, ImageDraw as PILImageDraw, ImageFont as PILImageFont

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

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
ASSETS_DIR = os.path.join(BASE_DIR, 'assets') # Definido globalmente

FPS_VIDEO = 24
IMAGE_DURATION_SECONDS = 5
MAX_WORDS_PER_LINE_TTS = 10 
MAX_CHARS_PER_LINE_IMAGE = 40

CHANNEL_CONFIGS = {
    "fizzquirk": {
        "video_title_template": "FizzQuirk Fact Shorts! #{short_id}",
        "video_description_template": "Astounding fact of the day by FizzQuirk!\n\nFact:\n{fact_text_for_description}\n\n#FizzQuirk #Shorts #AmazingFacts #Trivia #FunFacts",
        "video_tags_list": ["fizzquirk", "facts", "trivia", "shorts", "fun facts", "learning", "amazing facts"],
        "music_options": [
            "animado.mp3", 
            "fundo_misterioso.mp3",
            "tema_calmo.mp3"
        ],
        "default_music_if_list_empty": None,
        "music_volume": 0.07,
        "gtts_language": "en",
        "text_font_path_for_image_placeholder": None, 
        "num_facts_to_use": 3,
        "duration_per_fact_slide_min": 6,
        "pause_after_fact": 1.0,
        "category_id": "27",
        "gcp_project_id": os.environ.get("GCP_PROJECT_ID"),
        "gcp_location": os.environ.get("GCP_LOCATION", "us-central1"),
        "imagen_model_name": "imagegeneration@006"
    },
}

def get_authenticated_service(client_secrets_path, token_path):
    # ... (código da função mantido) ...
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
                logging.error(f"ERRO CRÍTICO: client_secrets.json não encontrado em {client_secrets_path}")
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

def get_facts_for_video(keywords, language, num_facts=1):
    # ... (função mantida) ...
    logging.info(f"Obtendo {num_facts} fatos para idioma '{language}' com keywords: {keywords}")
    facts_db = {
        "en": [
            "A group of flamingos is called a 'flamboyance'.", "Honey is the only food that never spoils.",
            "The unicorn is the national animal of Scotland.", "A shrimp's heart is in its head.",
            "Slugs have four noses.", "It is impossible for most people to lick their own elbow.",
            "A bolt of lightning contains enough energy to toast 100,000 slices of bread.",
            "The oldest known living tree is over 4,800 years old."
        ],
        "pt-br": [ 
            "Um grupo de flamingos é chamado de 'bando' ou, poeticamente, 'flamboiada'.", 
            "O mel é o único alimento que realmente nunca estraga.",
            "O unicórnio é o animal nacional da Escócia.", 
            "O coração de um camarão fica na cabeça.",
            "Lesmas têm quatro narizes, ou melhor, tentáculos que funcionam como narizes."
        ]
    }
    logging.warning(f"ALERTA: Usando lista de fatos placeholder para '{language}'. Adapte 'get_facts_for_video' para conteúdo real.")
    available_facts = facts_db.get(language, facts_db.get("en", [])) 

    if not available_facts:
        logging.error(f"Nenhuma lista de fatos encontrada para o idioma '{language}' ou fallback 'en'.")
        return []
    if len(available_facts) < num_facts:
        logging.warning(f"Fatos insuficientes ({len(available_facts)}) para '{language}'. Solicitados: {num_facts}. Usando todos disponíveis.")
        return available_facts
    return random.sample(available_facts, num_facts)

def generate_audio_from_text(text, lang, audio_file_path):
    # ... (função mantida) ...
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
    # ... (função mantida) ...
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
                if font_path_config: logging.warning(f"Fonte '{font_path_config}' não encontrada. Usando padrão Pillow.")
                else: logging.info("Nenhum caminho de fonte especificado. Usando padrão Pillow.")
                font_to_use = PILImageFont.load_default(size=current_font_size) 
        except Exception as e_font: 
            logging.warning(f"Erro ao carregar fonte '{font_path_config}': {e_font}. Usando padrão Pillow.")
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
    # ... (função mantida, com placeholder para Vertex AI Imagen) ...
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

    video_slide_clips = []
    audio_slide_segments = [] # CORRIGIDO: Lista inicializada aqui
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
        
        audio_slide_segments.append(current_segment_audio) # Agora é `append` simples para concatenar depois
        
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

def generate_video_title(facts, channel_name="default"):
    if not facts: return f"{channel_name.capitalize()} Video - {datetime.date.today().strftime('%Y-%m-%d')}"
    first_fact = facts[0]
    words_for_title = first_fact.split()[:7] 
    title_base = " ".join(words_for_title)
    if title_base.endswith(('.', ',', ';', ':')): title_base = title_base[:-1]
    
    generated_title = f"Fato Incrível: {title_base.strip()}"
    if len(first_fact.split()) > 7: generated_title += "..."
        
    max_title_length = 95 
    if len(generated_title) > max_title_length:
        cut_title = generated_title[:max_title_length-3]
        last_space = cut_title.rfind(' ')
        generated_title = cut_title[:last_space] + "..." if last_space != -1 else cut_title + "..."
            
    logging.info(f"Título gerado: '{generated_title}'")
    return generated_title

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status="public"):
    logging.info(f"--- Upload: '{title}', Status: '{privacy_status}' ---")
    response_final_upload = None # CORRIGIDO: Inicializa response_final_upload
    try:
        if not video_path or not os.path.exists(video_path):
            logging.error(f"ERRO Upload: Arquivo de vídeo NÃO encontrado em {video_path}")
            return None
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        request_body = {
            'snippet': {'title': title, 'description': description, 'tags': tags, 'categoryId': category_id},
            'status': {'privacyStatus': privacy_status}
        }
        request = youtube_service.videos().insert(part=','.join(request_body.keys()), body=request_body, media_body=media)
        
        done = False
        while not done:
            status, chunk_response = request.next_chunk() 
            if status: 
                logging.info(f"Upload: {int(status.progress() * 100)}%")
            if chunk_response is not None: 
                done = True
                response_final_upload = chunk_response 
        
        if response_final_upload: 
            video_id = response_final_upload.get('id')
            if video_id:
                logging.info(f"Upload completo! Vídeo ID: {video_id}")
                logging.info(f"Link (pode levar alguns minutos para ficar ativo): https://www.youtube.com/watch?v={video_id}") # Link correto
                return video_id
            else:
                logging.error(f"Upload pode ter falhado ou API não retornou ID. Resposta: {response_final_upload}")
                return None
        else: 
            logging.error("Upload não retornou uma resposta final válida após o loop.")
            return None
    except Exception as e:
        logging.error(f"ERRO CRÍTICO durante upload para o YouTube: {e}", exc_info=True)
        return None

def main(channel_name_arg):
    logging.info(f"--- Iniciando para canal: {channel_name_arg} ---")
    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Configuração para o canal '{channel_name_arg}' não encontrada em CHANNEL_CONFIGS."); sys.exit(1)

    os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(ASSETS_DIR, "music"), exist_ok=True)

    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices: 
        music_file_name = random.choice(music_choices)
        potential_music_path = os.path.join(ASSETS_DIR, "music", music_file_name)
        if os.path.exists(potential_music_path):
            selected_music_path = potential_music_path
            logging.info(f"Música selecionada: {selected_music_path}")
        else:
            logging.warning(f"Arquivo de música '{music_file_name}' não encontrado em '{os.path.join(ASSETS_DIR, 'music')}'. Prosseguindo sem música de fundo.")
            selected_music_path = None 
    config["selected_music_path"] = selected_music_path 

    client_secrets_path = CLIENT_SECRET_FILE
    token_path = TOKEN_FILE
    
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: logging.error("Falha YouTube auth."); sys.exit(1)

    facts_list = get_facts_for_video(config.get("fact_keywords", []), config["gtts_language"], config["num_facts_to_use"])
    if not facts_list: logging.error("Sem fatos."); sys.exit(1)

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
            try: os.remove(audio_f); logging.info(f"Áudio temp removido: {audio_f}")
            except Exception as e: logging.warning(f"Falha ao remover áudio temp {audio_f}: {e}")

    if not video_output_path: logging.error("Falha criar vídeo."); sys.exit(1)

    video_title = generate_video_title(actual_facts_with_audio, channel_name=channel_name_arg)
    video_description = generate_video_description(actual_facts_with_audio, channel_name=channel_name_arg) # Corrigido para usar a função correta
    
    video_id_uploaded = upload_video(youtube_service, video_output_path, video_title,
                                     video_description, config["youtube_tags"],
                                     config["youtube_video_category_id"], config["youtube_privacy_status"])
    if video_id_uploaded:
        logging.info(f"--- SUCESSO! Canal '{channel_name_arg}'. VÍDEO PÚBLICO ID: {video_id_uploaded} ---")
        if os.path.exists(video_output_path): 
            logging.info(f"Vídeo local {video_output_path} mantido para inspeção.")
    else:
        logging.error(f"--- FALHA no upload para o canal '{channel_name_arg}'. ---"); sys.exit(1)
    
    logging.info(f"--- Fim do processo para o canal '{channel_name_arg}' ---")

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
        else: 
             logging.error(f"Script para '{args.channel if args else 'N/A'}' encerrado com erro (código {e.code}).")
             raise 
    except Exception as e_main_block:
        logging.error(f"ERRO INESPERADO NO BLOCO PRINCIPAL para '{args.channel if args else 'N/A'}': {e_main_block}", exc_info=True)
        sys.exit(2)
