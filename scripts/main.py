import os
import argparse
import logging
import json
import sys
import time
import random
from gtts import gTTS
from moviepy.editor import (AudioFileClip, TextClip, CompositeVideoClip,
                            ColorClip, ImageClip, CompositeAudioClip,
                            concatenate_videoclips, concatenate_audioclips)
from moviepy.config import change_settings
import moviepy.config as MOPY_CONFIG # Para inspecionar configurações do MoviePy
from PIL import Image as PILImage, ImageDraw as PILImageDraw, ImageFont as PILImageFont # Para o placeholder de imagem

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# Tenta importar a biblioteca do Gemini, mas não falha o script inteiro se não estiver lá,
# pois a função de geração de imagem terá um fallback.
try:
    import google.generativeai as genai
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False
    logging.warning("Biblioteca google-generativeai não encontrada. Geração de imagem com Gemini estará desabilitada.")


logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# --- CONFIGURAÇÕES GLOBAIS DOS CANAIS ---
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
        "default_music_if_list_empty": None, # Pode ser um caminho para uma música padrão
        "music_volume": 0.07,
        "gtts_language": "en",
        "text_font_path_for_image": "assets/fonts/DejaVuSans-Bold.ttf", # Fonte para o texto NA IMAGEM GERADA
        "num_facts_to_use": 3, # Use 1 para testar a geração de imagem mais rapidamente
        "duration_per_fact_slide": 5, # Segundos que cada "slide" (imagem + narração do fato) durará
        "category_id": "27"  # Education
    },
    "curiosidades_br": {
        "video_title_template": "Você Sabia? #{short_id} Curiosidades em Português!",
        "video_description_template": "Descubra fatos incríveis em português!\n\nNeste vídeo:\n{fact_text_for_description}\n\n#CuriosidadesBR #VoceSabia #FatosPT",
        "video_tags_list": ["curiosidades", "português", "brasil", "você sabia", "fatos"],
        "music_options": ["assets/music/tema_calmo.mp3"], # Exemplo
        "default_music_if_list_empty": None,
        "music_volume": 0.1,
        "gtts_language": "pt-br",
        "text_font_path_for_image": "assets/fonts/Arial.ttf",
        "num_facts_to_use": 1,
        "duration_per_fact_slide": 6,
        "category_id": "27"
    }
}

def get_authenticated_service(client_secrets_path, token_path):
    # ... (Esta função permanece como na última versão funcional)
    logging.info("--- Tentando obter serviço autenticado ---")
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
                creds = None # Invalida creds se o refresh falhar
        if not creds or not creds.valid: # Se ainda não é válido (sem refresh token ou refresh falhou)
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: client_secrets.json não encontrado em {client_secrets_path}")
                return None
            logging.info("Executando novo fluxo de autorização...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0) # Para ambiente local/primeira vez
            # Em CI, este passo interativo falhará. O token.json deve ser pré-autorizado.
        if creds: # Salva o token (novo ou atualizado)
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            logging.info(f"Token salvo/atualizado em {token_path}")
    if not creds or not creds.valid:
        logging.error("Falha final ao obter credenciais válidas.")
        return None
    logging.info("Serviço autenticado com sucesso.")
    return build('youtube', 'v3', credentials=creds)


def get_facts_for_video(keywords, language, num_facts=1):
    logging.info(f"Obtendo {num_facts} fatos para idioma '{language}' com keywords: {keywords}")
    # ========================== ATENÇÃO: LÓGICA DE FATOS MULTILÍNGUES ===============================
    # Esta função PRECISA ser adaptada por você para retornar fatos REAIS
    # no IDIOMA ESPECIFICADO ('language') e relacionados às 'keywords'.
    # A implementação atual é apenas um placeholder com listas fixas.
    # =============================================================================================
    facts_db = {
        "en": [
            "A group of flamingos is called a 'flamboyance'.",
            "Honey is the only food that never spoils.",
            "The unicorn is the national animal of Scotland.",
            "A shrimp's heart is in its head.",
            "Slugs have four noses.",
            "It is impossible for most people to lick their own elbow."
        ],
        "pt-br": [
            "Um grupo de flamingos é chamado de 'flamboiada'.",
            "O mel é o único alimento que nunca estraga.",
            "O unicórnio é o animal nacional da Escócia.",
            "O coração de um camarão fica na cabeça.",
            "Lesmas têm quatro narizes.",
            "É impossível para a maioria das pessoas lamber o próprio cotovelo."
        ]
    }
    available_facts = facts_db.get(language, facts_db["en"]) # Fallback para inglês
    if len(available_facts) < num_facts:
        logging.warning(f"Não há fatos suficientes para '{language}'. Solicitados: {num_facts}, Disponíveis: {len(available_facts)}")
        return available_facts # Retorna o que tiver
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
    logging.info(f"Gerando imagem placeholder para: '{fact_text[:30]}...'")
    try:
        # Gradiente
        r1, g1, b1 = random.randint(60, 180), random.randint(60, 180), random.randint(60, 180)
        r2, g2, b2 = min(255, r1 + 40), min(255, g1 + 40), min(255, b1 + 40)
        
        img = PILImage.new("RGB", (width, height))
        draw = PILImageDraw.Draw(img)
        for y in range(height):
            r = int(r1 + (r2 - r1) * y / height)
            g = int(g1 + (g2 - g1) * y / height)
            b = int(b1 + (b2 - b1) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Texto
        padding = int(width * 0.08)
        max_text_width = width - 2 * padding
        
        try:
            font_size = int(height / 18) # Ajuste conforme necessário
            font = PILImageFont.truetype(font_path, font_size)
        except IOError:
            logging.warning(f"Fonte '{font_path}' não encontrada ou inválida. Usando fonte padrão.")
            font_size = int(height / 22)
            font = PILImageFont.load_default(size=font_size)

        lines = []
        words = fact_text.split()
        current_line = ""
        for word in words:
            bbox = draw.textbbox((0,0), current_line + word + " ", font=font)
            if bbox[2] - bbox[0] <= max_text_width:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        lines.append(current_line.strip())
        
        total_text_height = sum(draw.textbbox((0,0), line, font=font)[3] - draw.textbbox((0,0), line, font=font)[1] for line in lines)
        total_text_height += (len(lines) - 1) * (font_size * 0.2) # Espaçamento entre linhas
        
        y_text = (height - total_text_height) / 2
        text_color = (255, 255, 255); stroke_color = (0,0,0); stroke_width = 2
        
        for line in lines:
            bbox = draw.textbbox((0,0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x_text = (width - line_width) / 2
            # Desenha a borda (stroke)
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx*dx + dy*dy <= stroke_width*stroke_width : # Stroke circular aproximado
                        draw.text((x_text + dx, y_text + dy), line, font=font, fill=stroke_color)
            draw.text((x_text, y_text), line, font=font, fill=text_color) # Desenha o texto
            y_text += line_height + (font_size * 0.2)

        temp_img_dir = "temp_images"
        os.makedirs(temp_img_dir, exist_ok=True)
        temp_img_path = os.path.join(temp_img_dir, f"img_{random.randint(1000,9999)}.png")
        img.save(temp_img_path)
        image_clip = ImageClip(temp_img_path).set_duration(duration).set_fps(24)
        # os.remove(temp_img_path) # Removido para inspeção, mas idealmente seria limpo depois
        logging.info(f"Imagem placeholder salva em {temp_img_path}")
        return image_clip
    except Exception as e:
        logging.error(f"Erro ao gerar imagem placeholder: {e}", exc_info=True)
        return ColorClip(size=(width, height), color=(80, 80, 120), duration=duration).set_fps(24)


def generate_image_with_gemini_api(fact_text, duration): # Esta é a função que você precisa implementar corretamente
    logging.warning("*" * 80)
    logging.warning("ATENÇÃO: A função 'generate_image_with_gemini_api' precisa ser implementada!")
    logging.warning("Ela deve usar a API do Gemini para gerar uma imagem baseada no 'fact_text'.")
    logging.warning("O código atual é apenas um placeholder com uma cor sólida.")
    logging.warning("Verifique a documentação da API do Gemini para geração de imagens (ex: Imagen via Vertex AI).")
    logging.warning("*" * 80)
    
    # Placeholder: Retorna um clipe de cor sólida. Substitua pela chamada real à API.
    # Exemplo hipotético (NÃO FUNCIONAL DIRETAMENTE COM 'gemini-pro-vision' PARA GERAÇÃO):
    # if GEMINI_SDK_AVAILABLE:
    #     gemini_api_key = os.environ.get("GEMINI_API_KEY")
    #     if gemini_api_key:
    #         try:
    #             genai.configure(api_key=gemini_api_key)
    #             # Você precisará usar o modelo e método CORRETO para text-to-image aqui.
    #             # Exemplo: model = genai.GenerativeModel('seu-modelo-de-geracao-de-imagem')
    #             # response = model.generate_content(f"Uma imagem ilustrando: {fact_text}")
    #             # Lógica para processar 'response' e obter os bytes da imagem...
    #             # image_bytes = ...
    #             # temp_img_path = os.path.join("temp_images", "gemini_img.png")
    #             # with open(temp_img_path, 'wb') as f:
    #             #     f.write(image_bytes)
    #             # return ImageClip(temp_img_path).set_duration(duration).resize(height=1920).set_fps(24)
    #             logging.info("Chamada simulada à API Gemini (implementação pendente).")
    #         except Exception as e:
    #             logging.error(f"Erro ao tentar usar API Gemini (simulado): {e}")
    #     else:
    #         logging.error("Chave GEMINI_API_KEY não configurada para geração de imagem.")
            
    # Retorna o placeholder melhorado se a API Gemini não for usada ou falhar:
    return generate_dynamic_image_placeholder(fact_text, 1080, 1920, "assets/fonts/DejaVuSans-Bold.ttf", duration)


def create_video_from_content(facts, narration_audio_files, channel_config, channel_title="Video"):
    logging.info(f"--- Criando vídeo para '{channel_title}' com {len(facts)} fatos ---")
    W, H = 1080, 1920  # Formato Shorts (vertical)
    FPS = 24
    slide_duration = channel_config.get("duration_per_fact_slide", 5) # Duração de cada slide

    # Configuração do ImageMagick (mantida)
    try:
        current_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
        if current_im_binary == "unset" or not os.path.exists(current_im_binary): # Se 'unset' ou não existir
            imagemagick_path = "/usr/bin/convert" 
            if os.path.exists(imagemagick_path):
                logging.info(f"MoviePy: Configurando IMAGEMAGICK_BINARY para '{imagemagick_path}'")
                change_settings({"IMAGEMAGICK_BINARY": imagemagick_path})
            else:
                 logging.warning(f"MoviePy: 'convert' NÃO encontrado em '{imagemagick_path}'. TextClip pode usar fallback.")
    except Exception as e_conf:
        logging.warning(f"MoviePy: Exceção ao configurar IMAGEMAGICK_BINARY: {e_conf}")

    video_slide_clips = []
    narration_audioclips_for_concat = []
    
    for i, fact_text in enumerate(facts):
        narration_path = narration_audio_files[i]
        if not os.path.exists(narration_path):
            logging.error(f"Arquivo de narração '{narration_path}' não encontrado para o fato: {fact_text[:30]}... Pulando.")
            continue

        narration_audio_segment = AudioFileClip(narration_path)
        # A duração do slide será a maior entre a narração (+ pequena pausa) e a duração mínima configurada.
        current_fact_duration = max(narration_audio_segment.duration + 0.5, slide_duration) 
        
        # 1. Gerar imagem (usando o placeholder melhorado ou sua futura integração Gemini)
        dynamic_image_clip = generate_image_with_gemini_api(fact_text, current_fact_duration) # Passa a duração calculada
        dynamic_image_clip = dynamic_image_clip.set_fps(FPS)
        
        # Ajusta o áudio da narração para a duração do slide (se for mais curto, não estica; se for mais longo, será cortado pela duração do slide)
        narration_audio_segment = narration_audio_segment.subclip(0, min(narration_audio_segment.duration, current_fact_duration))
        
        # Adiciona o clipe visual e o áudio da narração à lista para concatenação
        video_slide_clips.append(dynamic_image_clip.set_duration(current_fact_duration))
        # Cria um clipe de áudio silencioso com a duração do slide e sobrepõe a narração nele
        # para garantir que cada segmento de áudio tenha a duração correta para a concatenação.
        silent_segment = AudioFileClip(narration_path).subclip(0,0).set_duration(current_fact_duration) # Áudio silencioso
        narration_on_silent_bg = CompositeAudioClip([silent_segment, narration_audio_segment])
        narration_audioclips_for_concat.append(narration_on_silent_bg)

    if not video_slide_clips:
        logging.error("Nenhum slide de vídeo foi gerado.")
        return None

    final_visual_part = concatenate_videoclips(video_slide_clips).set_fps(FPS)
    final_narration_audio = concatenate_audioclips(narration_audioclips_for_concat)
    
    final_video_with_narration = final_visual_part.set_audio(final_narration_audio)
    total_video_duration = final_video_with_narration.duration # Duração total real

    # Adicionar música de fundo
    final_video_with_all_audio = final_video_with_narration
    music_path = channel_config.get("music_path") # Pega o caminho da música selecionada aleatoriamente
    music_volume = channel_config.get("music_volume", 0.1)

    if music_path and os.path.exists(music_path):
        try:
            logging.info(f"Adicionando música: {music_path}, Volume: {music_volume}")
            music_clip_orig = AudioFileClip(music_path)
            music_clip = music_clip_orig.volumex(music_volume)
            
            if music_clip.duration < total_video_duration:
                num_loops = int(total_video_duration / music_clip.duration) + 1
                looped_segments = [music_clip] * num_loops
                music_final = concatenate_audioclips(looped_segments).subclip(0, total_video_duration)
            else:
                music_final = music_clip.subclip(0, total_video_duration)
            
            composed_audio = CompositeAudioClip([final_video_with_narration.audio, music_final])
            final_video_with_all_audio = final_video_with_narration.set_audio(composed_audio)
        except Exception as e_music:
            logging.warning(f"Erro ao adicionar música '{music_path}': {e_music}. Vídeo sem música.")
    else:
        if music_path: logging.warning(f"Arquivo de música não encontrado: {music_path}.")
        else: logging.info("Nenhuma música de fundo especificada.")

    output_dir = "generated_videos"
    os.makedirs(output_dir, exist_ok=True)
    video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}_final.mp4"
    video_output_path = os.path.join(output_dir, video_output_filename)
    
    logging.info(f"Escrevendo vídeo final: {video_output_path} (Duração: {final_video_with_all_audio.duration:.2f}s)...")
    final_video_with_all_audio.write_videofile(video_output_path, codec='libx264', audio_codec='aac', 
                                         fps=FPS, preset='ultrafast', threads=os.cpu_count() or 2, logger='bar')
    logging.info("Vídeo final escrito.")
    return video_output_path

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    # ... (função upload_video como na última versão funcional)
    logging.info(f"--- Upload: '{title}', Status: '{privacy_status}' ---")
    try:
        if not video_path or not os.path.exists(video_path): # Checagem extra
            logging.error(f"ERRO Upload: Arquivo de vídeo NÃO encontrado em {video_path}")
            return None
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        request_body = {
            'snippet': {'title': title, 'description': description, 'tags': tags, 'categoryId': category_id},
            'status': {'privacyStatus': privacy_status}
        }
        logging.info(f"Corpo da requisição para upload: {json.dumps(request_body, indent=2)}")
        request = youtube_service.videos().insert(part=','.join(request_body.keys()), body=request_body, media_body=media)
        
        response = None; done = False
        while not done:
            status, response_chunk = request.next_chunk()
            if status: logging.info(f"Upload: {int(status.progress() * 100)}%")
            if response_chunk is not None: done = True; response = response_chunk
        
        video_id = response.get('id')
        if video_id:
            logging.info(f"Upload completo! Vídeo ID: {video_id}")
            logging.info(f"Link: https://www.youtube.com/watch?v={video_id}")
            return video_id
        else:
            logging.error(f"Upload falhou ou resposta da API não contém ID. Resposta: {response}")
            return None
    except Exception as e:
        logging.error(f"ERRO CRÍTICO durante upload: {e}", exc_info=True)
        return None

def main(channel_name_arg):
    logging.info(f"--- Iniciando para canal: {channel_name_arg} ---")
    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Configuração para '{channel_name_arg}' não encontrada. Verifique CHANNEL_CONFIGS.")
        sys.exit(1)

    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json" 
    
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: logging.error("Falha na autenticação."); sys.exit(1)
    logging.info("Serviço YouTube autenticado.")

    facts = get_facts_for_video(
        keywords=config.get("fact_keywords", ["general facts"]), 
        language=config["gtts_language"], 
        num_facts=config["num_facts_to_use"]
    )
    if not facts: logging.error("Nenhum fato obtido."); sys.exit(1)

    narration_audio_files = []
    for i, fact in enumerate(facts):
        audio_filename = f"{channel_name_arg}_fact_{i+1}_{int(time.time())}.mp3"
        path = generate_audio_from_text(fact, config["gtts_language"], audio_filename)
        if not path: logging.error(f"Falha ao gerar áudio para o fato: {fact[:30]}..."); continue # Pula este fato se o áudio falhar
        narration_audio_files.append(path)

    if not narration_audio_files:
        logging.error("Nenhum arquivo de narração foi gerado. Não é possível criar o vídeo.")
        sys.exit(1)
    
    # Seleciona música de fundo
    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices:
        selected_music_path = random.choice(music_choices)
        logging.info(f"Música de fundo selecionada: {selected_music_path}")
    elif config.get("default_music_if_list_empty"):
        selected_music_path = config.get("default_music_if_list_empty")
        logging.info(f"Usando música de fundo padrão: {selected_music_path}")
    else:
        logging.info("Nenhuma música de fundo configurada.")

    video_output_path = create_video_from_content(
        facts=facts, # Passa os textos dos fatos para a função de imagem
        narration_audio_files=narration_audio_files, 
        channel_title=channel_name_arg,
        music_path=selected_music_path,
        music_volume=config.get("music_volume", 0.08),
        font_path=config.get("text_font_path_for_image"),
        text_on_screen_font_path=config.get("text_font_path_for_image") # Pode ser diferente se precisar
    )
    
    # Limpeza dos áudios de narração individuais
    for audio_file in narration_audio_files:
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                logging.info(f"Arquivo de áudio temporário removido: {audio_file}")
            except Exception as e_clean_audio:
                logging.warning(f"Não foi possível remover áudio temporário {audio_file}: {e_clean_audio}")

    if not video_output_path: logging.error("Falha ao criar vídeo."); sys.exit(1)

    final_video_title = config["video_title_template"].format(short_id=int(time.time() % 1000)) # ID curto para título
    # Para a descrição, vamos usar apenas o primeiro fato como exemplo ou um resumo
    fact_text_for_description = facts[0] if facts else "Descubra fatos incríveis!"
    final_video_description = config["video_description_template"].format(fact_text_for_description=fact_text_for_description, facts_list="\n- ".join(facts))
    
    privacy_status = "public"

    video_id_uploaded = upload_video(youtube_service, video_output_path, final_video_title,
                                     final_video_description, config["video_tags_list"],
                                     config["category_id"], privacy_status)
    if video_id_uploaded:
        logging.info(f"--- SUCESSO '{channel_name_arg}'! VÍDEO PÚBLICO ID: {video_id_uploaded} ---")
        if os.path.exists(video_output_path): # Opcional: remover vídeo local após upload
            try:
                # os.remove(video_output_path)
                # logging.info(f"Vídeo local removido: {video_output_path}")
                pass # Deixe comentado para poder inspecionar o vídeo gerado
            except Exception as e_clean_vid:
                logging.warning(f"Não foi possível remover vídeo local {video_output_path}: {e_clean_vid}")
    else:
        logging.error(f"--- FALHA no upload para '{channel_name_arg}'. ---")
        sys.exit(1)
    
    logging.info(f"--- Fim do processo para '{channel_name_arg}' ---")

if __name__ == "__main__":
    logging.info("INFO_LOG: [MAIN_BLOCK_2] Script main.py executando.")
    parser = argparse.ArgumentParser(description="Automatiza YouTube para canal.")
    parser.add_argument("--channel", required=True, help="Nome do canal (chave em CHANNEL_CONFIGS).")
    args = None
    try:
        args = parser.parse_args()
        logging.info(f"Argumentos: {args}")
        main(args.channel)
        logging.info(f"Execução para '{args.channel}' CONCLUÍDA.")
    except SystemExit as e:
        if e.code != 0: # Apenas relança se for um código de erro real
            logging.error(f"Script encerrado com SystemExit({e.code}) para canal '{args.channel if args else 'N/A'}'.")
            raise
        else: # Código 0 é sucesso
             logging.info(f"Script encerrado com SystemExit({e.code}) - Saída normal.")
    except Exception as e_main_block:
        logging.error(f"ERRO INESPERADO NO BLOCO PRINCIPAL para '{args.channel if args else 'N/A'}': {e_main_block}", exc_info=True)
        sys.exit(2)
