import os
import argparse
import logging
import json
import sys
import time
import random

# Para geração de áudio
from gtts import gTTS

# Para edição de vídeo
from moviepy.editor import (AudioFileClip, TextClip, CompositeVideoClip,
                            ColorClip, ImageClip, CompositeAudioClip,
                            concatenate_videoclips, concatenate_audioclips)
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

# Para a API Gemini/Vertex AI (instale google-cloud-aiplatform)
try:
    from google.cloud import aiplatform
    # from google.protobuf import json_format # Se for usar IAPredictionClient
    # from google.protobuf.struct_pb2 import Value # Se for usar IAPredictionClient
    VERTEX_AI_SDK_AVAILABLE = True
except ImportError:
    VERTEX_AI_SDK_AVAILABLE = False
    logging.warning("Biblioteca google-cloud-aiplatform não encontrada. Geração de imagem com Vertex AI Imagen estará desabilitada.")
    logging.warning("Instale com: pip install google-cloud-aiplatform")


logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

CHANNEL_CONFIGS = {
    "fizzquirk": {
        "video_title_template": "FizzQuirk Fact Shorts! #{short_id}",
        "video_description_template": "Astounding fact of the day by FizzQuirk!\n\nFact:\n{fact_text_for_description}\n\n#FizzQuirk #Shorts #AmazingFacts #Trivia",
        "video_tags_list": ["fizzquirk", "facts", "trivia", "shorts", "fun facts", "learning"],
        "music_options": [
            "assets/music/animado.mp3",
            "assets/music/fundo_misterioso.mp3",
            "assets/music/tema_calmo.mp3"
        ],
        "default_music_if_list_empty": None,
        "music_volume": 0.07,
        "gtts_language": "en",
        "text_font_path_for_image": "assets/fonts/DejaVuSans-Bold.ttf", # Fonte para o texto na imagem (placeholder)
        "num_facts_to_use": 2, # Reduzido para testes mais rápidos
        "duration_per_fact_slide": 6, # Segundos que cada slide (imagem + narração) durará
        "category_id": "27",  # Education
        # Configurações para Vertex AI Imagen (você precisará preencher)
        "gcp_project_id": os.environ.get("GCP_PROJECT_ID"), # Defina como variável de ambiente
        "gcp_location": os.environ.get("GCP_LOCATION", "us-central1"), # Ex: us-central1
        "imagen_model_name": "imagegeneration@006" # Verifique o nome do modelo mais recente
    },
    # Você pode adicionar outras configurações de canal aqui
}

def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado para YouTube API ---")
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            logging.warning(f"Não foi possível carregar token de {token_path}: {e}")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logging.info("Token expirado, tentando refresh...")
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Falha ao atualizar token: {e}")
                creds = None
        if not creds or not creds.valid:
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: client_secrets.json não encontrado em {client_secrets_path}")
                return None
            logging.info("Executando novo fluxo de autorização...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        if creds:
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            logging.info(f"Token salvo/atualizado em {token_path}")
    if not creds or not creds.valid:
        logging.error("Falha final ao obter credenciais válidas para YouTube.")
        return None
    logging.info("Serviço YouTube autenticado com sucesso.")
    return build('youtube', 'v3', credentials=creds)

def get_facts_for_video(keywords, language, num_facts=1):
    logging.info(f"Obtendo {num_facts} fatos para idioma '{language}' com keywords: {keywords}")
    facts_db = {
        "en": [
            "A group of flamingos is called a 'flamboyance'.",
            "Honey is the only food that never spoils.",
            "The unicorn is the national animal of Scotland.",
            "A single strand of spaghetti is called a 'spaghetto'." # Adicionado novo fato
        ],
        "pt-br": [ # Exemplo em português
            "O mel é o único alimento que realmente nunca estraga.",
            "O Oceano Pacífico é maior que todas as massas de terra combinadas."
        ]
    }
    available_facts = facts_db.get(language, facts_db["en"])
    if len(available_facts) < num_facts:
        logging.warning(f"Fatos insuficientes para '{language}'. Solicitados: {num_facts}, Disponíveis: {len(available_facts)}")
        return available_facts
    return random.sample(available_facts, num_facts)

def generate_audio_from_text(text, lang, output_filename):
    logging.info(f"Gerando áudio para: '{text[:50]}...' (Idioma: {lang})")
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        output_dir = "temp_audio"
        os.makedirs(output_dir, exist_ok=True)
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

def generate_dynamic_image_placeholder(fact_text, width, height, font_path, duration):
    """Gera uma imagem placeholder com fundo gradiente e o texto do fato."""
    logging.info(f"Gerando imagem PLACEHOLDER para: '{fact_text[:30]}...'")
    try:
        r1, g1, b1 = random.randint(60, 180), random.randint(60, 180), random.randint(60, 180)
        r2, g2, b2 = min(255, r1 + 40), min(255, g1 + 40), min(255, b1 + 40)
        img = PILImage.new("RGB", (width, height))
        draw = PILImageDraw.Draw(img)
        for y in range(height):
            r_curr = int(r1 + (r2 - r1) * y / height)
            g_curr = int(g1 + (g2 - g1) * y / height)
            b_curr = int(b1 + (b2 - b1) * y / height)
            draw.line([(0, y), (width, y)], fill=(r_curr, g_curr, b_curr))

        padding = int(width * 0.08); max_text_width = width - 2 * padding
        try:
            font_size = int(height / 20) # Ajustado para ser um pouco maior
            font = PILImageFont.truetype(font_path, font_size)
        except IOError:
            logging.warning(f"Fonte '{font_path}' não encontrada. Usando fonte padrão.")
            font_size = int(height / 25)
            font = PILImageFont.load_default(size=font_size)

        lines = []; words = fact_text.split(); current_line = ""
        for word in words:
            bbox = draw.textbbox((0,0), current_line + word + " ", font=font)
            if bbox[2] - bbox[0] <= max_text_width: current_line += word + " "
            else: lines.append(current_line.strip()); current_line = word + " "
        lines.append(current_line.strip())
        
        line_heights = [draw.textbbox((0,0), line, font=font)[3] - draw.textbbox((0,0), line, font=font)[1] for line in lines]
        spacing = int(font_size * 0.25)
        total_text_height = sum(line_heights) + (len(lines) - 1) * spacing
        
        y_text = (height - total_text_height) / 2
        text_color=(255, 255, 255); stroke_color=(0,0,0); stroke_width=max(1, int(font_size/20)) # Stroke relativo
        
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0,0), line, font=font); line_width = bbox[2] - bbox[0]
            x_text = (width - line_width) / 2
            for dx_s in range(-stroke_width, stroke_width + 1):
                for dy_s in range(-stroke_width, stroke_width + 1):
                    if dx_s*dx_s + dy_s*dy_s <= stroke_width*stroke_width:
                         draw.text((x_text + dx_s, y_text + dy_s), line, font=font, fill=stroke_color)
            draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += line_heights[i] + spacing

        temp_img_dir = "temp_images"; os.makedirs(temp_img_dir, exist_ok=True)
        temp_img_path = os.path.join(temp_img_dir, f"placeholder_{random.randint(1000,9999)}.png")
        img.save(temp_img_path)
        image_clip = ImageClip(temp_img_path).set_duration(duration).set_fps(24)
        # Considerar remover temp_img_path após o uso se não precisar para debug
        # os.remove(temp_img_path)
        logging.info(f"Imagem placeholder salva em {temp_img_path}")
        return image_clip
    except Exception as e:
        logging.error(f"Erro ao gerar imagem placeholder: {e}", exc_info=True)
        return ColorClip(size=(width, height), color=(random.randint(50,100), random.randint(50,100), random.randint(50,100)), duration=duration).set_fps(24)

def generate_image_with_vertex_ai_imagen(project_id, location, model_name, fact_text, duration, font_path_for_fallback):
    """Gera uma imagem usando Vertex AI Imagen API ou retorna um placeholder em caso de falha."""
    logging.info(f"Tentando gerar imagem com Vertex AI Imagen para: '{fact_text[:30]}...'")
    
    if not VERTEX_AI_SDK_AVAILABLE:
        logging.warning("SDK Vertex AI não disponível. Usando placeholder.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

    if not all([project_id, location, model_name]):
        logging.error("ID do projeto, localização ou nome do modelo Vertex AI não configurados. Usando placeholder.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

    try:
        aiplatform.init(project=project_id, location=location)
        # O modelo exato e os parâmetros podem variar. Consulte a documentação do Vertex AI Imagen.
        # Exemplo para modelos de geração de imagem mais recentes (pode precisar de ajustes):
        model = aiplatform.ImageGenerationModel.from_pretrained(model_name) # Ex: "imagegeneration@005" ou "imagegeneration@006"
        
        # Defina o número de imagens a serem geradas (normalmente 1 para este caso)
        # O prompt pode ser mais elaborado para melhores resultados.
        prompt_for_imagen = (
            f"Generate a visually stunning and captivating image that illustrates the following amazing fact, "
            f"suitable for a vertical short-form video (9:16 aspect ratio). "
            f"The image should be vibrant, high-quality, and directly relevant to the theme of the fact. "
            f"Fact: '{fact_text}'. "
            f"Style: digital art, cinematic lighting, eye-catching."
        )

        response = model.generate_images(
            prompt=prompt_for_imagen,
            number_of_images=1,
            # Outros parâmetros opcionais:
            # aspect_ratio="9:16", # Se o modelo suportar diretamente
            # negative_prompt="text, words, blurry, low quality, watermark",
            # seed=random.randint(0, 100000)
        )
        
        if response.images:
            image_obj = response.images[0] # Pega a primeira imagem gerada
            
            temp_img_dir = "temp_images_vertex"; os.makedirs(temp_img_dir, exist_ok=True)
            generated_image_path = os.path.join(temp_img_dir, f"vertex_img_{random.randint(1000,9999)}.png")
            image_obj.save(location=generated_image_path, include_generation_parameters=False)
            
            logging.info(f"Imagem gerada com Vertex AI Imagen e salva em: {generated_image_path}")
            # Carrega a imagem salva com MoviePy e ajusta para o formato vertical se necessário
            img_clip = ImageClip(generated_image_path).set_duration(duration).set_fps(24)
            # Garante que a imagem tenha a proporção correta (9:16) para vídeo vertical
            # Se o modelo Imagen não gerar na proporção exata, podemos redimensionar/cortar aqui.
            # Exemplo: se a imagem for quadrada, cortar para 9:16.
            # Ou, se o modelo Imagen tiver parâmetro aspect_ratio="9:16", melhor ainda.
            # if img_clip.w / img_clip.h != 9/16:
            #    img_clip = img_clip.resize(height=1920) # ou width=1080 e cortar/adicionar barras
            #    img_clip = crop(img_clip, width=1080, height=1920, x_center=img_clip.w/2, y_center=img_clip.h/2)
            return img_clip.resize(height=1920) # Simplesmente redimensiona pela altura
        else:
            logging.error("Vertex AI Imagen API não retornou imagens.")
            return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)

    except Exception as e:
        logging.error(f"Erro ao gerar imagem com Vertex AI Imagen: {e}", exc_info=True)
        logging.error("Certifique-se que sua conta de serviço (se estiver usando uma) tem o papel 'Vertex AI User'.")
        return generate_dynamic_image_placeholder(fact_text, 1080, 1920, font_path_for_fallback, duration)


def create_video_from_content(facts, narration_audio_files, channel_config, channel_title="Video"):
    logging.info(f"--- Criando vídeo para '{channel_title}' com {len(facts)} fatos ---")
    W, H = 1080, 1920; FPS = 24
    default_slide_duration = channel_config.get("duration_per_fact_slide", 5)
    font_path_for_placeholder = channel_config.get("text_font_path_for_image", "assets/fonts/DejaVuSans-Bold.ttf")

    try: # Configuração do ImageMagick
        # ... (código de configuração do ImageMagick como na versão anterior)
        current_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
        if current_im_binary == "unset" or not os.path.exists(current_im_binary):
            common_paths = ["/usr/bin/convert", "/usr/local/bin/convert", "/opt/homebrew/bin/convert"]
            found_path = None
            for p in common_paths:
                if os.path.exists(p): found_path = p; break
            if found_path:
                logging.info(f"MoviePy: Configurando IMAGEMAGICK_BINARY para '{found_path}'")
                change_settings({"IMAGEMAGICK_BINARY": found_path})
            else:
                logging.warning("MoviePy: 'convert' (ImageMagick) não encontrado nos caminhos comuns.")
    except Exception as e_conf: logging.warning(f"MoviePy: Exceção ao configurar IMAGEMAGICK_BINARY: {e_conf}")

    video_slide_clips = []; narration_audioclips_for_concat = []
    
    for i, fact_text in enumerate(facts):
        narration_path = narration_audio_files[i]
        if not os.path.exists(narration_path):
            logging.error(f"Áudio '{narration_path}' não encontrado para fato: {fact_text[:30]}... Pulando."); continue

        narration_audio_segment = AudioFileClip(narration_path)
        current_fact_duration = max(narration_audio_segment.duration + 0.75, default_slide_duration) # Pausa maior
        
        # Gerar imagem (com Vertex AI Imagen ou placeholder)
        dynamic_image_clip = generate_image_with_vertex_ai_imagen(
            project_id=channel_config.get("gcp_project_id"),
            location=channel_config.get("gcp_location"),
            model_name=channel_config.get("imagen_model_name"),
            fact_text=fact_text,
            duration=current_fact_duration,
            font_path_for_fallback=font_path_for_placeholder
        )
        dynamic_image_clip = dynamic_image_clip.set_fps(FPS).set_duration(current_fact_duration)
        
        video_slide_clips.append(dynamic_image_clip)
        
        # Áudio da narração para este slide
        narration_audio_segment_adjusted = narration_audio_segment.subclip(0, min(narration_audio_segment.duration, current_fact_duration))
        # Para garantir que cada segmento de áudio tenha a duração correta para a concatenação,
        # criamos um clipe de áudio silencioso com a duração do slide e sobrepomos a narração.
        silent_for_fact_duration = AudioFileClip(narration_path).subclip(0,0).set_duration(current_fact_duration)
        narration_final_for_slide = CompositeAudioClip([silent_for_fact_duration, narration_audio_segment_adjusted])
        narration_audioclips_for_concat.append(narration_final_for_slide)

    if not video_slide_clips: logging.error("Nenhum slide de vídeo foi gerado."); return None

    final_visual_part = concatenate_videoclips(video_slide_clips, method="compose").set_fps(FPS)
    final_narration_audio = concatenate_audioclips(narration_audioclips_for_concat)
    final_video_with_narration = final_visual_part.set_audio(final_narration_audio)
    total_video_duration = final_video_with_narration.duration

    # Música de fundo
    final_video_with_all_audio = final_video_with_narration
    selected_music_path = channel_config.get("selected_music_path") # Obtém a música já selecionada
    music_volume = channel_config.get("music_volume", 0.1)

    if selected_music_path and os.path.exists(selected_music_path):
        try:
            # ... (Lógica de adição de música como antes) ...
            logging.info(f"Adicionando música: {selected_music_path}, Volume: {music_volume}")
            music_clip_orig = AudioFileClip(selected_music_path)
            music_clip = music_clip_orig.volumex(music_volume)
            
            if music_clip.duration < total_video_duration:
                num_loops = int(total_video_duration / music_clip.duration) + 1
                music_final = concatenate_audioclips([music_clip] * num_loops).subclip(0, total_video_duration)
            else:
                music_final = music_clip.subclip(0, total_video_duration)
            
            composed_audio = CompositeAudioClip([final_video_with_narration.audio, music_final])
            final_video_with_all_audio = final_video_with_narration.set_audio(composed_audio)
        except Exception as e_music:
            logging.warning(f"Erro ao adicionar música '{selected_music_path}': {e_music}.")
    # ... (Resto da função para salvar o vídeo como antes) ...
    output_dir = "generated_videos"; os.makedirs(output_dir, exist_ok=True)
    video_fname = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}.mp4"
    video_output_path = os.path.join(output_dir, video_fname)
    logging.info(f"Escrevendo vídeo: {video_output_path} (Duração: {final_video_with_all_audio.duration:.2f}s)")
    final_video_with_all_audio.write_videofile(video_output_path, codec='libx264', audio_codec='aac',
                                             fps=FPS, preset='ultrafast', threads=(os.cpu_count() or 2), logger='bar')
    logging.info("Vídeo final escrito.")
    return video_output_path


def main(channel_name_arg):
    logging.info(f"--- Iniciando para canal: {channel_name_arg} ---")
    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Config '{channel_name_arg}' não encontrada."); sys.exit(1)

    # Seleciona música de fundo ANTES para que possa ser passada para create_video
    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices: selected_music_path = random.choice(music_choices)
    elif config.get("default_music_if_list_empty"): selected_music_path = config.get("default_music_if_list_empty")
    if selected_music_path: logging.info(f"Música selecionada: {selected_music_path}")
    else: logging.info("Nenhuma música de fundo.")
    config["selected_music_path"] = selected_music_path # Adiciona ao config para uso posterior

    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json"
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: logging.error("Falha YouTube auth."); sys.exit(1)

    facts = get_facts_for_video(config.get("fact_keywords", []), config["gtts_language"], config["num_facts_to_use"])
    if not facts: logging.error("Sem fatos."); sys.exit(1)

    narration_audio_files = []
    for i, fact in enumerate(facts):
        audio_fname = f"{channel_name_arg}_fact_{i+1}_{int(time.time()*10)}.mp3" # Nome de arquivo mais único
        path = generate_audio_from_text(fact, config["gtts_language"], audio_fname)
        if path: narration_audio_files.append(path)
        else: logging.error(f"Falha áudio para: {fact[:30]}..."); # Decide se quer parar ou continuar

    if not narration_audio_files or len(narration_audio_files) != len(facts): # Checa se todos os áudios foram gerados
        logging.error("Nem todos os áudios de narração foram gerados. Abortando criação do vídeo.")
        # Limpa áudios parciais
        for audio_f in narration_audio_files:
            if os.path.exists(audio_f): os.remove(audio_f)
        sys.exit(1)

    video_output_path = create_video_from_content(facts, narration_audio_files, config, channel_name_arg)

    for audio_f in narration_audio_files: # Limpa áudios de narração
        if os.path.exists(audio_f):
            try: os.remove(audio_f)
            except Exception as e: logging.warning(f"Falha ao remover {audio_f}: {e}")

    if not video_output_path: logging.error("Falha criar vídeo."); sys.exit(1)

    title = config["video_title_template"].format(short_id=random.randint(1000,9999))
    desc_fact = facts[0] if facts else "Fatos incríveis!"
    description = config["video_description_template"].format(fact_text_for_description=desc_fact, facts_list="\n- ".join(facts))
    
    video_id = upload_video(youtube_service, video_output_path, title, description,
                             config["video_tags_list"], config["category_id"], "public")
    if video_id:
        logging.info(f"--- SUCESSO '{channel_name_arg}'! VÍDEO ID: {video_id} ---")
        logging.info(f"Link correto: https://www.youtube.com/watch?v={video_id}")
        # if os.path.exists(video_output_path): os.remove(video_output_path) # Opcional
    else:
        logging.error(f"--- FALHA upload '{channel_name_arg}'. ---"); sys.exit(1)
    logging.info(f"--- Fim para '{channel_name_arg}' ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Automation Script")
    parser.add_argument("--channel", required=True, help="Channel key from CHANNEL_CONFIGS")
    args = parser.parse_args()
    main(args.channel)
