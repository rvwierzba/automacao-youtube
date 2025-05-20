import os
import argparse
import logging 
import json
import sys 
import time
import random # Importado para seleção aleatória de música

# --- Prints de Debug Iniciais ---
try:
    print("DEBUG_PRINT: [1] Script main.py iniciado. Testando stdout.", flush=True)
    sys.stderr.write("DEBUG_PRINT_STDERR: [1] Script main.py iniciado. Testando stderr.\n")
    sys.stderr.flush()
except Exception as e_print_inicial:
    print(f"DEBUG_PRINT_EXCEPTION: Erro no print inicial: {e_print_inicial}", flush=True)

# --- Configuração do Logging ---
try:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
    print("DEBUG_PRINT: [2] logging.basicConfig chamado com sucesso.", flush=True)
    logging.info("TEST_LOG_INFO: Logging configurado.")
except Exception as e_log_config:
    print(f"DEBUG_PRINT: [2] ERRO durante logging.basicConfig: {e_log_config}", flush=True)
    sys.stderr.write(f"DEBUG_PRINT_STDERR: [2] ERRO durante logging.basicConfig: {e_log_config}\n")
    sys.stderr.flush()

# --- Restante das Importações ---
try:
    print("DEBUG_PRINT: [3] Iniciando importações principais.", flush=True)
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.http import MediaFileUpload

    from gtts import gTTS
    from moviepy.editor import (AudioFileClip, TextClip, CompositeVideoClip, 
                                ColorClip, ImageClip, CompositeAudioClip) 
    from moviepy.config import change_settings
    import moviepy.config as MOPY_CONFIG
    from PIL import Image 
    print("DEBUG_PRINT: [3] Importações principais concluídas.", flush=True)
except ImportError as e_import:
    print(f"DEBUG_PRINT_ERROR: [3] ERRO DE IMPORTAÇÃO: {e_import}", flush=True)
    logging.error(f"ERRO DE IMPORTAÇÃO GRAVE: {e_import}", exc_info=True) 
    sys.exit(1) 

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# --- CONFIGURAÇÕES GLOBAIS DOS CANAIS ---
CHANNEL_CONFIGS = {
    "fizzquirk": { 
        "video_title_template": "FizzQuirk Shorts: Fatos Incríveis! #{short_id}", # Exemplo de novo título
        "video_description_template": "Prepare-se para fatos surpreendentes com FizzQuirk!\n\nNeste vídeo:\n{facts_list}\n\n#FizzQuirk #Curiosidades #Shorts #FatosEngraçados #Aprender",
        "video_tags_list": ["fizzquirk", "curiosidades", "fatos", "shorts", "youtube shorts", "aprender", "divertido", "incrivel"],
        "background_image": "assets/backgrounds/fizzquirk_bg.jpg", # CRIE ESTA PASTA E IMAGEM, ou defina como None
        "music_options": [ 
            "assets/music/animado.mp3",
            "assets/music/fundo_misterioso.mp3",
            "assets/music/tema_calmo.mp3"
        ],
        "default_music_if_list_empty": None, # Pode ser um caminho para uma música padrão se a lista estiver vazia
        "music_volume": 0.07, # Volume da música de fundo (0.0 a 1.0). Experimente valores baixos.
        "gtts_language": "en", 
        "text_font_path": "assets/fonts/DejaVuSans-Bold.ttf", # Fonte para o texto. CRIE ESTA PASTA E ADICIONE A FONTE.
                                                              # Se None ou não encontrado, MoviePy usa um padrão.
        "fact_keywords": ["general knowledge", "science trivia", "amazing world", "weird facts"], 
        "num_facts_to_use": 6, # Aumentado para vídeos mais longos
        "category_id": "28" # Ciência e Tecnologia
    },
    "curiosidades_br": { 
        "video_title_template": "Você Sabia? Curiosidades em Português! #{short_id}",
        "video_description_template": "Descubra fatos incríveis em português!\n\nNeste vídeo:\n{facts_list}\n\n#CuriosidadesBR #VoceSabia #FatosPT",
        "video_tags_list": ["curiosidades", "português", "brasil", "você sabia", "fatos"],
        "background_image": "assets/backgrounds/curiosidadesbr_bg.png", # CRIE ESTA PASTA E IMAGEM
        "music_options": [
            "assets/music/tema_calmo.mp3", # Reutilizando ou adicione músicas específicas
            # Adicione mais caminhos de músicas aqui se desejar
        ],
        "default_music_if_list_empty": "assets/music/default_pt.mp3", # EXEMPLO
        "music_volume": 0.1,
        "gtts_language": "pt-br",
        "text_font_path": "assets/fonts/Arial.ttf", # Verifique se esta fonte está no runner ou adicione-a em assets/fonts/
        "fact_keywords": ["curiosidades brasil", "fatos em portugues", "mundo curioso pt"],
        "num_facts_to_use": 5,
        "category_id": "27" # Educação
    }
}

def get_authenticated_service(client_secrets_path, token_path):
    # ... (esta função permanece igual à última versão funcional que corrigiu a autenticação)
    print("DEBUG_PRINT: [FUNC_AUTH] Entrando em get_authenticated_service.", flush=True)
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path}...")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True)
            creds = None 
    else:
        logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")

    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar...")
        try:
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}.")
                return None 
            with open(client_secrets_path, 'r') as f:
                client_secrets_info = json.load(f)
            if 'installed' not in client_secrets_info:
                logging.error(f"ERRO: Estrutura 'installed' não encontrada em {client_secrets_path}.")
                return None 
            secrets = client_secrets_info['installed']
            creds_for_refresh = Credentials(
                token=None,
                refresh_token=creds.refresh_token,
                token_uri=secrets.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=secrets.get('client_id'),
                client_secret=secrets.get('client_secret'),
                scopes=creds.scopes
            )
            if not all([creds_for_refresh.client_id, creds_for_refresh.client_secret, creds_for_refresh.refresh_token]):
                logging.error(f"ERRO: Informações cruciais para refresh faltando.")
                return None
            logging.info(f"Tentando refresh com client_id: {creds_for_refresh.client_id}")
            request_obj = Request() 
            creds_for_refresh.refresh(request_obj) 
            creds = creds_for_refresh 
            logging.info("Token atualizado. Salvando...")
            token_data_to_save = {
                'token': creds.token, 'refresh_token': creds.refresh_token, 
                'token_uri': creds.token_uri, 'client_id': creds.client_id,
                'client_secret': creds.client_secret, 'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None 
            }
            with open(token_path, 'w') as token_file:
                json.dump(token_data_to_save, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado.")
        except Exception as e:
            logging.error(f"ERRO ao atualizar token: {e}", exc_info=True)
            creds = None 
    elif not creds:
        logging.error("--- Falha: token.json não encontrado/inválido.")
        return None
    elif not creds.valid:
        logging.error("--- Falha: Credenciais inválidas e não puderam ser atualizadas.")
        return None

    logging.info("--- Autenticação OK. Construindo serviço API YouTube. ---")
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        logging.error(f"ERRO ao construir serviço API: {e}", exc_info=True)
        return None

def get_facts_for_video(keywords, language, num_facts=6): # Aumentado num_facts
    print(f"DEBUG_PRINT: [FUNC_GET_FACTS] Keywords: {keywords}, Idioma para fatos (idealmente): {language}, Num_facts: {num_facts}", flush=True)
    logging.info(f"--- Obtendo {num_facts} fatos. Keywords: {keywords}. Idioma ideal: {language} ---")
    
    # ========================== ATENÇÃO: LÓGICA DE FATOS MULTILÍNGUES ===============================
    # Esta função PRECISA ser adaptada por você para retornar fatos no 'language' especificado.
    # A implementação atual é apenas um placeholder com listas fixas.
    # =============================================================================================
    all_facts_placeholder_en = [
        "A group of owls is called a parliament.", "Honey never spoils.",
        "The shortest war in history lasted 38 minutes.", "A cloud can weigh over a million pounds.",
        "Lightning can toast 100,000 slices of bread.", "You walk 3 times around the world in a lifetime.",
        "Octopuses have three hearts.", "Butterflies taste with their feet."
    ]
    all_facts_placeholder_pt = [
        "Um grupo de corujas é chamado 'parlamento'.", "O mel nunca estraga.",
        "A guerra mais curta durou 38 minutos.", "Uma nuvem pode pesar mais de 450 toneladas!",
        "Um raio pode torrar 100.000 pães.", "Você anda 3 voltas ao mundo na vida.",
        "Polvos têm três corações.", "Borboletas sentem gosto com os pés."
    ]
    
    facts_to_use = []
    if language.startswith("pt"):
        logging.info(f"Usando fatos placeholder em Português para o idioma '{language}'. Adapte esta função!")
        facts_to_use = all_facts_placeholder_pt
    else: # Default para Inglês
        logging.info(f"Usando fatos placeholder em Inglês para o idioma '{language}'. Adapte esta função!")
        facts_to_use = all_facts_placeholder_en
    
    if len(facts_to_use) < num_facts:
        logging.warning(f"Atenção: Solicitados {num_facts} fatos, mas apenas {len(facts_to_use)} disponíveis para '{language}'. Usando todos os disponíveis.")
        selected_facts = facts_to_use
    else:
        selected_facts = random.sample(facts_to_use, num_facts) # Pega uma amostra aleatória se houver mais fatos que o necessário

    logging.info(f"Selecionados {len(selected_facts)} fatos.")
    return selected_facts

def generate_audio_from_text(text, lang, output_filename="audio.mp3"):
    # ... (função mantida como na última versão funcional) ...
    print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] Iniciando. Idioma TTS: {lang}, Output: {output_filename}", flush=True)
    logging.info(f"--- Gerando áudio (Idioma: {lang}) ---")
    try:
        output_dir = "temp_audio"
        if not os.path.exists(output_dir):
            print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] Criando diretório: {output_dir}", flush=True)
            os.makedirs(output_dir, exist_ok=True)
        
        audio_path = os.path.join(output_dir, output_filename)
        print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] Caminho completo do áudio: {audio_path}", flush=True)

        tts = gTTS(text=text, lang=lang, slow=False)
        print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] Objeto gTTS criado. Tentando salvar em {audio_path}...", flush=True)
        tts.save(audio_path)
        
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] SUCESSO: Áudio salvo e arquivo existe e não está vazio em: {audio_path} (Tamanho: {os.path.getsize(audio_path)} bytes)", flush=True)
            logging.info(f"Áudio gerado e salvo em: {audio_path}")
            return audio_path
        else:
            size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1
            print(f"DEBUG_PRINT_ERROR: [FUNC_GEN_AUDIO] FALHA: Áudio NÃO foi salvo corretamente em {audio_path}. Existe? {os.path.exists(audio_path)}. Tamanho: {size}", flush=True)
            logging.error(f"FALHA ao salvar áudio ou arquivo vazio em {audio_path}. Existe? {os.path.exists(audio_path)}. Tamanho: {size}")
            return None
            
    except Exception as e:
        print(f"DEBUG_PRINT_ERROR: [FUNC_GEN_AUDIO] Exceção durante geração de áudio: {e}", flush=True)
        logging.error(f"ERRO ao gerar áudio para idioma '{lang}': {e}", exc_info=True)
        return None


def create_video_from_content(facts, narration_audio_path, channel_title="Video", 
                              background_image_path=None, music_path=None, music_volume=0.1, 
                              font_path=None):
    print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Entrando. Narração: {narration_audio_path}, FundoImg: {background_image_path}, Música: {music_path}, Fonte: {font_path}", flush=True)
    logging.info(f"--- Criando vídeo ({len(facts)} fatos) para '{channel_title}' ---")
    
    try:
        current_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
        logging.info(f"MoviePy: IMAGEMAGICK_BINARY ANTES: '{current_im_binary}'")
        imagemagick_path = "/usr/bin/convert" 
        if os.path.exists(imagemagick_path) and current_im_binary != imagemagick_path : # Só reconfigura se necessário
            logging.info(f"MoviePy: Configurando IMAGEMAGICK_BINARY para '{imagemagick_path}'")
            change_settings({"IMAGEMAGICK_BINARY": imagemagick_path})
            new_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
            logging.info(f"MoviePy: IMAGEMAGICK_BINARY APÓS: '{new_im_binary}'")
        elif not os.path.exists(imagemagick_path):
             logging.warning(f"MoviePy: 'convert' NÃO encontrado em '{imagemagick_path}'. TextClip pode usar fallback ou falhar se IMAGEMAGICK_BINARY for '{current_im_binary}'.")
    except Exception as e_conf:
        logging.warning(f"MoviePy: Exceção ao configurar IMAGEMAGICK_BINARY: {e_conf}")

    try:
        if not narration_audio_path or not os.path.exists(narration_audio_path) or not os.path.getsize(narration_audio_path) > 0:
            logging.error(f"ERRO CRÍTICO: Arquivo de narração não encontrado/vazio: {narration_audio_path}")
            return None
            
        narration_clip = AudioFileClip(narration_audio_path)
        total_duration = narration_clip.duration
        W, H = 1080, 1920; FPS = 24 # Formato Shorts (vertical)
        
        base_visual_clip = None
        if background_image_path and os.path.exists(background_image_path):
            try:
                logging.info(f"Usando imagem de fundo: {background_image_path}")
                base_visual_clip = ImageClip(background_image_path).set_duration(total_duration).resize(width=W, height=H).set_fps(FPS)
            except Exception as e_bg:
                logging.warning(f"Erro ao carregar imagem de fundo '{background_image_path}': {e_bg}. Usando fundo preto.")
                base_visual_clip = ColorClip(size=(W, H), color=(0, 0, 0), duration=total_duration, ismask=False).set_fps(FPS)
        else:
            if background_image_path: logging.warning(f"Imagem de fundo não encontrada: '{background_image_path}'. Usando fundo preto.")
            else: logging.info("Nenhuma imagem de fundo. Usando fundo preto.")
            base_visual_clip = ColorClip(size=(W, H), color=(0, 0, 0), duration=total_duration, ismask=False).set_fps(FPS)

        video_clips_list = [base_visual_clip]
        duration_per_fact = total_duration / len(facts) if facts and len(facts) > 0 else total_duration
        
        actual_font = font_path if font_path and os.path.exists(font_path) else 'DejaVu-Sans-Bold' # Fallback mais seguro que Arial
        if font_path and not os.path.exists(font_path):
            logging.warning(f"Arquivo de fonte '{font_path}' não encontrado. Usando fallback '{actual_font}'.")
        logging.info(f"Usando fonte para TextClip: {actual_font}")

        for i, fact in enumerate(facts):
            logging.info(f"Criando TextClip para fato {i+1}...")
            txt_clip = TextClip(fact, fontsize=70, color='white', font=actual_font,
                                method='caption', align='center', size=(W*0.85, None), # Aumentado um pouco a largura
                                stroke_color='black', stroke_width=2.5)
            txt_clip = txt_clip.set_position('center').set_duration(duration_per_fact).set_start(i * duration_per_fact).set_fps(FPS)
            video_clips_list.append(txt_clip)
            
        final_video_visual_part = CompositeVideoClip(video_clips_list, size=(W, H)).set_fps(FPS)

        # Áudio
        final_audio_segments = [narration_clip]
        if music_path and os.path.exists(music_path):
            try:
                logging.info(f"Adicionando música: {music_path}, Volume: {music_volume}")
                music_clip_orig = AudioFileClip(music_path)
                # Normalizar ou ajustar volume da música
                music_clip = music_clip_orig.volumex(music_volume)

                if music_clip.duration < total_duration:
                    # Looping de forma mais suave, se possível, ou apenas repetir N vezes
                    # Para evitar um loop muito abrupto, pode ser melhor ter uma música mais longa ou fade in/out no loop
                    num_loops = int(total_duration / music_clip.duration) + 1
                    looped_segments = [music_clip] * num_loops
                    music_clip_looped = concatenate_audioclips(looped_segments)
                    music_final = music_clip_looped.subclip(0, total_duration)
                else:
                    music_final = music_clip.subclip(0, total_duration)
                
                final_audio_segments.append(music_final)
                composed_audio = CompositeAudioClip(final_audio_segments) # Narração sobrepõe a música
                final_video_visual_part = final_video_visual_part.set_audio(composed_audio)
            except Exception as e_music:
                logging.warning(f"Erro ao processar música '{music_path}': {e_music}. Vídeo sem música de fundo.")
                final_video_visual_part = final_video_visual_part.set_audio(narration_clip)
        else:
            if music_path: logging.warning(f"Arquivo de música NÃO encontrado: {music_path}. Sem música.")
            else: logging.info("Nenhuma música de fundo especificada.")
            final_video_visual_part = final_video_visual_part.set_audio(narration_clip)
            
        output_video_dir = "generated_videos"
        os.makedirs(output_video_dir, exist_ok=True)
        video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}_final.mp4"
        video_output_path = os.path.join(output_video_dir, video_output_filename)
        
        logging.info(f"Escrevendo vídeo final: {video_output_path}...")
        final_video_visual_part.write_videofile(video_output_path, codec='libx264', audio_codec='aac', 
                                             fps=FPS, preset='ultrafast', threads=os.cpu_count() or 2, logger='bar')
        logging.info("Vídeo final escrito.")
        return video_output_path
        
    except Exception as e:
        logging.error(f"ERRO CRÍTICO em create_video_from_content: {e}", exc_info=True)
        return None

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    # ... (função mantida como na última versão funcional, com a correção do link no log) ...
    print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Entrando. Vídeo: {video_path}, Título: {title}, Privacidade: {privacy_status}", flush=True)
    logging.info(f"--- Iniciando etapa: Upload do vídeo '{title}' para o YouTube com status '{privacy_status}' ---")
    try:
        if not video_path or not os.path.exists(video_path) or not os.path.getsize(video_path) > 0:
            logging.error(f"ERRO: Arquivo de vídeo para upload NÃO encontrado ou vazio: {video_path}")
            return None
            
        logging.info(f"Preparando upload: {video_path} (Tamanho: {os.path.getsize(video_path)} bytes)")
        body= {
            'snippet': { 'title': title, 'description': description, 'tags': tags, 'categoryId': category_id },
            'status': { 'privacyStatus': privacy_status }
        }
        media_body = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        logging.info("Chamando youtube.videos().insert()...")
        insert_request = youtube_service.videos().insert(part=','.join(body.keys()), body=body, media_body=media_body)
        
        response_upload_final = None; done = False
        while not done:
            try:
                status, response_chunk = insert_request.next_chunk() 
                if status: logging.info(f"Progresso: {int(status.progress() * 100)}%")
                if response_chunk is not None: 
                    done = True; response_upload_final = response_chunk 
                    logging.info("Upload concluído.")
            except Exception as e_upload_chunk:
                logging.error(f"Erro durante next_chunk: {e_upload_chunk}", exc_info=True)
                return None 

        if not response_upload_final or not response_upload_final.get('id'):
            logging.error(f"ERRO: Upload falhou ou resposta final inválida: {response_upload_final}")
            return None

        video_id = response_upload_final.get('id')
        logging.info(f"Upload completo. Vídeo ID: {video_id}")
        logging.info(f"Link do vídeo (visível como '{privacy_status}'): https://www.youtube.com/watch?v={video_id}")
        return video_id
        
    except Exception as e:
        logging.error(f"ERRO durante upload: {e}", exc_info=True)
        return None


def main(channel_name_arg):
    print(f"DEBUG_PRINT: [4] Entrando na função main. Canal solicitado: {channel_name_arg}", flush=True)
    logging.info(f"--- Iniciando processo para canal: {channel_name_arg} ---")

    config = CHANNEL_CONFIGS.get(channel_name_arg)
    if not config:
        logging.error(f"Configuração para o canal '{channel_name_arg}' não encontrada em CHANNEL_CONFIGS.")
        sys.exit(1)
    
    logging.info(f"Configurações para '{channel_name_arg}': Título='{config['video_title_template']}', Idioma TTS='{config['gtts_language']}', NumFatos='{config['num_facts_to_use']}'")

    client_secrets_path = "credentials/client_secret.json" 
    token_path = "credentials/token.json" # Usando o token decodificado pelo YAML (originalmente de canal1_token.json.base64)
    
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service: sys.exit(1) 
    logging.info("Serviço do YouTube autenticado.")

    facts = get_facts_for_video(
        keywords=config["fact_keywords"], 
        language=config["gtts_language"], 
        num_facts=config["num_facts_to_use"]
    )
    if not facts: 
        logging.error("Nenhum fato obtido. Encerrando."); sys.exit(1)
    
    facts_for_description = "\n- ".join(facts)
    # Para gTTS, um texto muito longo pode falhar. Juntar com pausas pode ser melhor se os fatos forem longos individualmente.
    full_text_for_audio = ". ".join(facts) + "." 
    audio_file_name = f"{channel_name_arg.lower()}_{int(time.time())}_narration.mp3"

    narration_audio_file_path = generate_audio_from_text(
        text=full_text_for_audio, 
        lang=config["gtts_language"], 
        output_filename=audio_file_name
    )
    if not narration_audio_file_path: 
        logging.error("Falha ao gerar áudio da narração."); sys.exit(1)

    # Seleção de música de fundo
    selected_music_path = None
    music_choices = config.get("music_options", [])
    if music_choices and isinstance(music_choices, list) and len(music_choices) > 0:
        selected_music_path = random.choice(music_choices)
        logging.info(f"Música de fundo selecionada: {selected_music_path}")
    elif config.get("default_music_if_list_empty"): # Fallback para uma música padrão se a lista estiver vazia
        selected_music_path = config.get("default_music_if_list_empty")
        logging.info(f"Usando música de fundo padrão: {selected_music_path}")
    else:
        logging.info("Nenhuma música de fundo configurada ou lista vazia.")

    video_output_path = create_video_from_content(
        facts=facts, 
        narration_audio_path=narration_audio_file_path, 
        channel_title=channel_name_arg,
        background_image_path=config.get("background_image"),
        music_path=selected_music_path,
        music_volume=config.get("music_volume", 0.1), # Default volume se não especificado
        font_path=config.get("text_font_path")
    )
    if not video_output_path: 
        logging.error("Falha ao criar vídeo."); sys.exit(1)

    final_video_title = config["video_title_template"].format(short_id=int(time.time() % 10000))
    final_video_description = config["video_description_template"].format(facts_list=facts_for_description)
    
    privacy_status = "public" 

    video_id_uploaded = upload_video(youtube_service=youtube_service,
                                     video_path=video_output_path,
                                     title=final_video_title,
                                     description=final_video_description,
                                     tags=config["video_tags_list"],
                                     category_id=config["category_id"],
                                     privacy_status=privacy_status)
    if video_id_uploaded:
        logging.info(f"--- SUCESSO para '{channel_name_arg}'! VÍDEO PÚBLICO ID: {video_id_uploaded} ---")
        try:
            if narration_audio_file_path and os.path.exists(narration_audio_file_path): os.remove(narration_audio_file_path)
            # Decida se quer apagar o vídeo local:
            # if video_output_path and os.path.exists(video_output_path): os.remove(video_output_path)
            logging.info("Limpeza de arquivo de narração concluída.")
        except Exception as e_clean:
            logging.warning(f"Aviso ao limpar arquivos: {e_clean}")
    else:
        logging.error(f"--- FALHA no upload para '{channel_name_arg}'. ---")
        sys.exit(1)
    
    logging.info(f"--- Fim do processo para canal '{channel_name_arg}' ---")


if __name__ == "__main__":
    print("DEBUG_PRINT: [MAIN_BLOCK_1] __main__ executado.", flush=True)
    logging.info("INFO_LOG: [MAIN_BLOCK_2] Script main.py está sendo executado.")
    
    parser = argparse.ArgumentParser(description="Automatiza o YouTube para um canal específico.")
    parser.add_argument("--channel", required=True, help="Nome do canal (deve ser uma chave em CHANNEL_CONFIGS).")
    
    args = None 
    try:
        args = parser.parse_args()
        print(f"DEBUG_PRINT: [MAIN_BLOCK_4] Argumentos parseados: {args}", flush=True)
        main(args.channel)
        logging.info(f"INFO_LOG: [MAIN_BLOCK_7] Execução para '{args.channel}' concluída com sucesso.")
    except SystemExit as e:
        if e.code is None or e.code == 0:
            print(f"DEBUG_PRINT: [MAIN_BLOCK_EXIT_0] SystemExit com código {e.code}. Saída normal.", flush=True)
        else:
            print(f"DEBUG_PRINT_ERROR: [MAIN_BLOCK_ERROR] SystemExit com código {e.code}. Falha.", flush=True)
            logging.error(f"Script encerrado com sys.exit({e.code}) para canal '{args.channel if args and hasattr(args, 'channel') else 'N/A'}'.") 
            raise 
    except Exception as e_main_block:
        print(f"DEBUG_PRINT_ERROR: [MAIN_BLOCK_ERROR] Exceção INESPERADA: {e_main_block}", flush=True)
        logging.error(f"ERRO GRAVE NO BLOCO __main__ para canal '{args.channel if args and hasattr(args, 'channel') else 'N/A'}': {e_main_block}", exc_info=True)
        sys.exit(2)
