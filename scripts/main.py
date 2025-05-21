import os
import argparse
import logging
import json
import sys
import time
import random
import numpy as np # Para o clipe de silêncio

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
    logging.info("Biblioteca google-cloud-aiplatform encontrada.")
except ImportError:
    VERTEX_AI_SDK_AVAILABLE = False
    logging.warning("Biblioteca google-cloud-aiplatform não encontrada. Geração de imagem com Vertex AI Imagen estará desabilitada.")
    logging.warning("Instale com: pip install google-cloud-aiplatform")


logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# --- CONFIGURAÇÕES GLOBAIS DOS CANAIS ---
CHANNEL_CONFIGS = {
    "fizzquirk": { 
        "video_title_template": "FizzQuirk Fact Shorts! #{short_id}",
        "video_description_template": "Astounding fact of the day by FizzQuirk!\n\nFact:\n{fact_text_for_description}\n\n#FizzQuirk #Shorts #AmazingFacts #Trivia #FunFacts",
        "video_tags_list": ["fizzquirk", "facts", "trivia", "shorts", "fun facts", "learning", "amazing facts"],
        "music_options": [ # Seus arquivos de música
            "assets/music/animado.mp3",
            "assets/music/fundo_misterioso.mp3",
            "assets/music/tema_calmo.mp3"
        ],
        "default_music_if_list_empty": None, # Pode ser um caminho para uma música padrão se a lista estiver vazia
        "music_volume": 0.07, 
        "gtts_language": "en", 
        "text_font_path_for_image_placeholder": "assets/fonts/DejaVuSans-Bold.ttf", # Para o placeholder
        "num_facts_to_use": 3, # Quantos fatos por vídeo
        "duration_per_fact_slide_min": 6, # Duração mínima de cada "slide" (imagem + narração) em segundos
        "pause_after_fact": 1.0, # Segundos de pausa/silêncio adicionados após a narração de cada fato
        "category_id": "27",  # Education (Educação)
        # --- Configurações para Vertex AI Imagen (PREENCHA COM SEUS DADOS) ---
        "gcp_project_id": os.environ.get("GCP_PROJECT_ID"), # Defina como variável de ambiente ou string direta
        "gcp_location": os.environ.get("GCP_LOCATION", "us-central1"), # Ex: "us-central1"
        "imagen_model_name": "imagegeneration@006" # Verifique o nome do modelo mais recente/disponível para você
    },
    # Adicione outras configurações de canais aqui
    # "curiosidades_br": { ... } 
}

def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado para YouTube API ---")
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info(f"Credenciais carregadas de {token_path}")
        except Exception as e:
            logging.warning(f"Não foi possível carregar token de {token_path}: {e}")
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
                logging.error(f"ERRO CRÍTICO: client_secrets.json não encontrado em {client_secrets_path} e token inválido/ausente.")
                return None
            logging.info("Executando novo fluxo de autorização (interativo - para ambiente local)...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
                creds = flow.run_local_server(port=0) 
            except Exception as e_flow:
                logging.error(f"Falha no fluxo de autorização interativo: {e_flow}")
                return None
        
        if creds: 
            try:
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
    logging.info(f"Obtendo {num_facts} fatos para idioma '{language}' com keywords: {keywords}")
    # === ATENÇÃO: Esta função PRECISA ser adaptada para retornar fatos no 'language' especificado ===
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
        logging.error(f"Nenhuma lista de fatos encontrada para '{language}' ou fallback 'en'.")
        return []
    if len(available_facts) < num_facts:
        logging.warning(f"Fatos insuficientes ({len(available_facts)}) para '{language}'. Solicitados: {num_facts}. Usando todos disponíveis.")
        return available_facts
    return random.sample(available_facts, num_facts)

def generate_audio_from_text(text, lang, output_filename):
    logging.info(f"Gerando áudio para: '{text[:50]}...' (Idioma: {lang})")
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        output_dir = "temp_audio"; os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, output_filename)
        tts.save(audio_path)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logging.info(f"Áudio salvo em: {audio_path}")
            return audio_path
        logging.error(f"Falha ao salvar áudio ou arquivo vazio: {audio_path}")
        return None
    except Exception as e:
        logging.error(f"Erro em gTTS para '{lang}': {e}", exc_info=True)
        return None

def generate_dynamic_image_placeholder(fact_text, width, height, font_path_config, duration):
    logging.info(f"Gerando imagem PLACEHOLDER para: '{fact_text[:30]}...'")
    try:
        r1, g1, b1 = random.randint(40, 120), random.randint(40, 120), random.randint(40, 120)
        r2, g2, b2 = min(255, r1 + random.randint(40,80)), min(255, g1 + random.randint(40,80)), min(255, b1 + random.randint(40,80))
        
        img = PILImage.new("RGB", (width, height))
        draw = PILImageDraw.Draw(img)
        for y_grad in range(height):
            r_curr = int(r1 + (r2 - r1) * y_grad / height)
            g_curr = int(g1 + (g2 - g1) * y_grad / height)
            b_curr = int(b1 + (b2 - b1) * y_grad / height)
            draw.line([(0, y_grad), (width, y_grad)], fill=(r_curr, g_curr, b_curr))

        padding = int(width * 0.08); max_text_width = width - 2 * padding
        font_to_use = None; font_size = int(height / 17)
        try:
            if font_path_config and os.path.exists(font_path_config):
                font_to_use = PILImageFont.truetype(font_path_config, font_size)
            else:
                if font_path_config: logging.warning(f"Fonte '{font_path_config}' não encontrada.")
                font_to_use = PILImageFont.load_default(size=font_size) 
        except Exception as e_font:
            logging.warning(f"Erro ao carregar fonte '{font_path_config}': {e_font}. Usando fonte padrão.")
            font_to_use = PILImageFont.load_default(size=max(15, int(height / 22))) # Garante um tamanho mínimo

        lines = []; words = fact_text.split(); current_line = ""
        for word in words:
            bbox_test = draw.textbbox((0,0), current_line + word + " ", font=font_to_use)
            if bbox_test[2] - bbox_test[0] <= max_text_width: current_line += word + " "
            else: lines.append(current_line.strip()); current_line = word + " "
        lines.append(current_line.strip())
        
        line_heights = [draw.textbbox((0,0), line, font=font_to_use)[3] - draw.textbbox((0,0), line, font=font_to_use)[1] for line in lines]
        spacing = int(font_size * 0.2) 
        total_text_height = sum(line_heights) + (len(lines) - 1) * spacing
        
        y_text_start = (height - total_text_height) / 2
        text_color=(255, 255, 255); stroke_color=(0,0,0); stroke_width_val=max(1, int(font_size/20))
        
        current_y = y_text_start
        for i, line in enumerate(lines):
            bbox_line = draw.textbbox((0,0), line, font=font_to_use); line_w = bbox_line[2] - bbox_line[0]
            x_text = (width - line_w) / 2
            for dx_s in range(-stroke_width_val, stroke_width_val + 1):
                for dy_s in range(-stroke_width_val, stroke_width_val + 1):
                    if dx_s*dx_s + dy_s*dy_s <= stroke_width_val*stroke_width_val:
                         draw.text((x_text + dx_s, current_y + dy_s), line, font=font_to_use, fill=stroke_color, align="center")
            draw.text((x_text, current_y), line, font=font_to_use, fill=text_color, align="center")
            current_y += line_heights[i] + spacing

        temp_img_dir = "temp_images"; os.makedirs(temp_img_dir, exist_ok=True)
        temp_img_path = os.path.join(temp_img_dir, f"placeholder_{random.randint(1000,9999)}.png")
        img.save(temp_img_path)
        image_clip = ImageClip(temp_img_path, duration=duration).set_fps(FPS)
        logging.info(f"Imagem placeholder salva temporariamente em {temp_img_path}")
        return image_clip, temp_img_path # Retorna o caminho para limpeza posterior
    except Exception as e:
        logging.error(f"Erro ao gerar imagem placeholder: {e}", exc_info=True)
        return ColorClip(size=(width, height), color=(random.randint(50,100), random.randint(50,100), random.randint(50,100)), duration=duration).set_fps(FPS), None

def generate_image_with_vertex_ai_imagen(fact_text, duration, config, font_path_for_fallback):
    logging.info(f"Tentando gerar imagem com Vertex AI para: '{fact_text[:30]}...'")
    project_id = config.get("gcp_project_id")
    location = config.get("gcp_location")
    model_name = config.get("imagen_model_name")

    if not VERTEX_AI_SDK_AVAILABLE:
        logging.warning("SDK Vertex AI não disponível. Usando placeholder de imagem.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

    if not all([project_id, location, model_name]):
        logging.error("ID do projeto GCP, localização ou nome do modelo Imagen não configurados. Usando placeholder.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)
    
    logging.info("*"*30 + " CHAMANDO VERTEX AI IMAGEN " + "*"*30)
    logging.info(f"Projeto: {project_id}, Local: {location}, Modelo: {model_name}")
    
    try:
        aiplatform.init(project=project_id, location=location)
        model = aiplatform.ImageGenerationModel.from_pretrained(model_name)
        
        prompt = (
            f"A visually captivating, high-resolution image (9:16 aspect ratio for YouTube Shorts) "
            f"that creatively illustrates the interesting fact: '{fact_text}'. "
            f"Style: digital art, cinematic, engaging, clear focus, suitable for a general audience. Avoid text."
        )
        logging.info(f"Prompt para Imagen: {prompt}")
        
        # Parâmetros de geração de imagem (podem variar conforme o modelo)
        images = model.generate_images(
            prompt=prompt,
            number_of_images=1, # Gerar uma imagem por fato
            # Adicionar mais parâmetros conforme necessário, ex:
            # aspect_ratio="9:16", # Se suportado pelo modelo
            # seed=random.randint(0, 1000000) 
        )
        
        if images and images[0]: # A API retorna uma lista de objetos de imagem
            image_obj = images[0]
            temp_img_dir = "temp_images_vertex"; os.makedirs(temp_img_dir, exist_ok=True)
            # O SDK do Vertex AI salva o arquivo diretamente e não retorna bytes facilmente às vezes.
            # Criamos um nome de arquivo temporário para ele salvar.
            temp_generated_image_path = os.path.join(temp_img_dir, f"vertex_img_{random.randint(10000,99999)}.png")
            
            # O objeto image_obj pode ter um método _save ou _write_to_file, ou precisar acessar ._image_bytes
            # Verifique a documentação da versão da SDK que você está usando.
            # Exemplo assumindo que _save existe ou um método similar para obter os bytes
            if hasattr(image_obj, '_image_bytes'):
                 with open(temp_generated_image_path, "wb") as f:
                    f.write(image_obj._image_bytes) # Acesso direto aos bytes
                 logging.info(f"Imagem gerada com Vertex AI Imagen e salva em: {temp_generated_image_path}")
            elif hasattr(image_obj, 'save'):
                image_obj.save(location=temp_generated_image_path) # Se o objeto tiver um método save
                logging.info(f"Imagem gerada com Vertex AI Imagen (via .save()) e salva em: {temp_generated_image_path}")
            else:
                logging.error("Não foi possível salvar a imagem do Vertex AI. O objeto de imagem retornado não tem _image_bytes ou método save().")
                return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

            img_clip = ImageClip(temp_generated_image_path).set_duration(duration).set_fps(FPS)
            # Garante que a imagem tenha a proporção correta (9:16)
            img_clip = img_clip.resize(height=1920) # Ou width=1080 e crop, dependendo da saída da API
            return img_clip, temp_generated_image_path # Retorna o clipe e o caminho para limpeza
        else:
            logging.error("Vertex AI Imagen API não retornou imagens.")
            return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

    except Exception as e:
        logging.error(f"Erro ao gerar imagem com Vertex AI Imagen: {e}", exc_info=True)
        logging.error("Certifique-se que sua conta de serviço (GOOGLE_APPLICATION_CREDENTIALS) tem o papel 'Vertex AI User'.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)


def create_video_from_content(facts, narration_audio_files, channel_config, channel_title="Video"):
    logging.info(f"--- Criando vídeo para '{channel_title}' com {len(facts)} fatos ---")
    W, H = 1080, 1920; FPS = 24
    default_slide_duration = channel_config.get("duration_per_fact_slide_min", 6)
    pause_after_fact = channel_config.get("pause_after_fact", 1.0) # Aumentar pausa
    font_for_placeholder = channel_config.get("text_font_path_for_image_placeholder", "assets/fonts/DejaVuSans-Bold.ttf")

    video_slide_clips = []
    audio_slide_segments = []
    temp_image_paths_to_clean = [] # Lista para rastrear imagens temporárias
    
    current_timeline_pos = 0.0

    for i, fact_text in enumerate(facts):
        narration_file = narration_audio_files[i]
        if not (narration_file and os.path.exists(narration_file) and os.path.getsize(narration_file) > 0):
            logging.error(f"Arquivo de narração inválido para fato '{fact_text[:30]}...': {narration_file}. Pulando."); continue
        
        narration_clip_instance = AudioFileClip(narration_file)
        slide_duration = max(narration_clip_instance.duration + pause_after_fact, default_slide_duration)
        
        image_clip_result, temp_img_path = generate_image_with_vertex_ai_imagen( # Função atualizada
            fact_text=fact_text, 
            duration=slide_duration, 
            config=channel_config, # Passa todo o config
            font_path_for_fallback=font_for_placeholder
        )
        if temp_img_path: temp_image_paths_to_clean.append(temp_img_path)

        image_clip_result = image_clip_result.set_duration(slide_duration).set_fps(FPS).set_start(current_timeline_pos)
        video_slide_clips.append(image_clip_result)

        # Áudio do slide
        narration_part = narration_clip_instance.subclip(0, min(narration_clip_instance.duration, slide_duration))
        if narration_part.duration < slide_duration:
            silence_needed = slide_duration - narration_part.duration
            n_channels = getattr(narration_part, 'nchannels', 2)
            audio_fps = getattr(narration_part, 'fps', 44100)
            make_frame_silent = lambda t: np.zeros(n_channels)
            padding = AudioClip(make_frame_silent, duration=silence_needed, fps=audio_fps)
            slide_audio_segment = concatenate_audioclips([narration_part, padding])
        else:
            slide_audio_segment = narration_part
        
        audio_slide_segments.append(slide_audio_segment.set_start(current_timeline_pos))
        current_timeline_pos += slide_duration

    if not video_slide_clips: logging.error("Nenhum slide de vídeo gerado."); return None

    final_visual_part = CompositeVideoClip(video_slide_clips, size=(W,H)).set_duration(current_timeline_pos).set_fps(FPS)
    final_narration_audio = CompositeAudioClip(audio_slide_segments).set_duration(current_timeline_pos) # Use CompositeAudioClip para segmentos com .set_start()
    
    final_video_with_narration = final_visual_part.set_audio(final_narration_audio)
    
    selected_music_path = channel_config.get("selected_music_path")
    music_volume = channel_config.get("music_volume", 0.08)
    final_product_video = final_video_with_narration

    if selected_music_path and os.path.exists(selected_music_path):
        try:
            music_clip = AudioFileClip(selected_music_path).volumex(music_volume)
            if music_clip.duration < current_timeline_pos:
                music_final = music_clip.loop(duration=current_timeline_pos)
            else:
                music_final = music_clip.subclip(0, current_timeline_pos)
            
            # Garante que áudio de narração não é None
            current_main_audio = final_video_with_narration.audio
            if current_main_audio is None:
                logging.warning("Narração está None. Usando apenas música.")
                final_product_video = final_video_with_narration.set_audio(music_final)
            else:
                final_audio_track = CompositeAudioClip([current_main_audio, music_final])
                final_product_video = final_video_with_narration.set_audio(final_audio_track)
            logging.info(f"Música '{selected_music_path}' adicionada.")
        except Exception as e_music:
            logging.warning(f"Erro ao adicionar música '{selected_music_path}': {e_music}.")
    
    output_dir = "generated_videos"; os.makedirs(output_dir, exist_ok=True)
    video_fname = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}.mp4"
    video_output_path = os.path.join(output_dir, video_fname)
    
    logging.info(f"Escrevendo vídeo: {video_output_path} (Duração: {final_product_video.duration:.2f}s)")
    final_product_video.write_videofile(video_output_path, codec='libx264', audio_codec='aac', 
                                     fps=FPS, preset='ultrafast', threads=(os.cpu_count() or 2), logger='bar')
    logging.info("Vídeo final escrito.")

    # Limpa imagens temporárias do placeholder ou da API Gemini se foram salvas localmente
    for img_path in temp_image_paths_to_clean:
        if os.path.exists(img_path):
            try: os.remove(img_path); logging.info(f"Imagem temporária removida: {img_path}")
            except Exception as e_clean_img: logging.warning(f"Falha ao remover img temp {img_path}: {e_clean_img}")
            
    return video_output_path

# ... (upload_video e o resto do script como antes) ...
def main(channel_name_arg):
    logging.info(f"--- Iniciando para canal: {channel_name_arg} ---")
    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Config '{channel_name_arg}' não encontrada."); sys.exit(1)

    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices: selected_music_path = random.choice(music_choices)
    elif config.get("default_music_if_list_empty"): selected_music_path = config.get("default_music_if_list_empty")
    config["selected_music_path"] = selected_music_path # Passa para create_video

    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json" 
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: logging.error("Falha YouTube auth."); sys.exit(1)

    facts = get_facts_for_video(config.get("fact_keywords", []), config["gtts_language"], config["num_facts_to_use"])
    if not facts: logging.error("Sem fatos."); sys.exit(1)

    narration_audio_files = []
    temp_audio_dir = "temp_audio" # Garante que o diretório exista
    os.makedirs(temp_audio_dir, exist_ok=True)

    for i, fact in enumerate(facts):
        # Cria nome de arquivo único para cada narração
        audio_filename_temp = f"{channel_name_arg}_fact_{i+1}_{int(time.time()*1000)}_{random.randint(0,100)}.mp3"
        path = generate_audio_from_text(fact, config["gtts_language"], audio_filename_temp)
        if path: narration_audio_files.append(path)
        else: logging.warning(f"Falha áudio para fato: '{fact[:30]}...'. Fato será pulado.")
    
    # Atualiza a lista de fatos para apenas aqueles que tiveram áudio gerado
    # Isso requer mapear os áudios de volta aos fatos se alguns falharem.
    # Por simplicidade, se o número de áudios não bater, abortamos.
    if len(narration_audio_files) != config["num_facts_to_use"] or not narration_audio_files:
         logging.error(f"Esperava {config['num_facts_to_use']} áudios, mas {len(narration_audio_files)} foram gerados. Abortando.")
         for audio_f in narration_audio_files: # Limpa os que foram gerados
             if os.path.exists(audio_f): os.remove(audio_f)
         sys.exit(1)

    video_output_path = create_video_from_content(
        facts=facts, 
        narration_audio_files=narration_audio_files, 
        channel_config=config, 
        channel_title=channel_name_arg
    )
    
    for audio_f in narration_audio_files: 
        if os.path.exists(audio_f):
            try: os.remove(audio_f)
            except Exception as e: logging.warning(f"Falha ao remover áudio temp {audio_f}: {e}")

    if not video_output_path: logging.error("Falha criar vídeo."); sys.exit(1)

    title = config["video_title_template"].format(short_id=random.randint(1000,9999))
    desc_fact_sample = facts[0] if facts else "Curiosidades incríveis!"
    description = config["video_description_template"].format(fact_text_for_description=desc_fact_sample, facts_list="\n- ".join(facts))
    
    upload_video(youtube_service, video_output_path, title, description,
                 config["video_tags_list"], config["category_id"], "public")
    # ... (lógica de sucesso/falha e limpeza do vídeo como antes)
    if os.path.exists(video_output_path): # Limpeza opcional
        logging.info(f"Vídeo local {video_output_path} ainda existe. Remova manualmente ou descomente a linha no código.")
        # os.remove(video_output_path) 
    logging.info(f"--- Fim para '{channel_name_arg}' ---")


if __name__ == "__main__":
    logging.info("Script main.py executando como __main__")
    parser = argparse.ArgumentParser(description="YouTube Automation Script")
    parser.add_argument("--channel", required=True, help="Nome do canal (chave em CHANNEL_CONFIGS).")
    args = None
    try:
        args = parser.parse_args()
        main(args.channel)
    except SystemExit as e:
        if e.code != 0: logging.error(f"Script encerrado com erro (código {e.code}).")
        else: logging.info("Script concluído com sucesso.")
        # Não relançar sys.exit(0) para evitar que a Action pense que é erro.
        if e.code != 0: raise 
    except Exception as e_main_block:
        logging.error(f"ERRO INESPERADO: {e_main_block}", exc_info=True)
        sys.exit(2)
