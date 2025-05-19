import os
import argparse
import logging # Mantido para basicConfig
import json
import sys # Mantido para sys.exit e sys.stdout/stderr
import time

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
    logging.info("TEST_LOG_INFO: Esta é uma mensagem de teste do logging (INFO) após basicConfig.")
    logging.warning("TEST_LOG_WARNING: Esta é uma mensagem de teste do logging (WARNING) após basicConfig.")
    logging.error("TEST_LOG_ERROR: Esta é uma mensagem de teste do logging (ERROR) após basicConfig.")
except Exception as e_log_config:
    print(f"DEBUG_PRINT: [2] ERRO durante logging.basicConfig: {e_log_config}", flush=True)
    sys.stderr.write(f"DEBUG_PRINT_STDERR: [2] ERRO durante logging.basicConfig: {e_log_config}\n")
    sys.stderr.flush()

# --- Restante das Importações ---
try:
    print("DEBUG_PRINT: [3] Iniciando importações principais.", flush=True)
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow # Embora não usado diretamente para refresh agora, pode ser útil manter
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.http import MediaFileUpload

    from gtts import gTTS
    from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx
    from moviepy.config import change_settings
    import moviepy.config as MOPY_CONFIG
    from PIL import Image
    print("DEBUG_PRINT: [3] Importações principais concluídas com sucesso.", flush=True)
except ImportError as e_import:
    print(f"DEBUG_PRINT_ERROR: [3] ERRO DE IMPORTAÇÃO: {e_import}", flush=True)
    logging.error(f"ERRO DE IMPORTAÇÃO GRAVE: {e_import}", exc_info=True)
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service(client_secrets_path, token_path):
    print("DEBUG_PRINT: [FUNC_AUTH] Entrando em get_authenticated_service.", flush=True)
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None

    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path} usando from_authorized_user_file...")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True)
            creds = None 
    else:
        logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")

    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh.")
                print(f"DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO CRÍTICO: client_secrets.json não encontrado em {client_secrets_path}", flush=True)
                return None 
            with open(client_secrets_path, 'r') as f:
                client_secrets_info = json.load(f)
            if 'installed' not in client_secrets_info:
                logging.error(f"ERRO: Estrutura 'installed' não encontrada em {client_secrets_path}.")
                print(f"DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO: Estrutura 'installed' não encontrada em {client_secrets_path}", flush=True)
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
            if not creds_for_refresh.client_id or not creds_for_refresh.client_secret or not creds_for_refresh.refresh_token:
                missing_parts = []
                if not creds_for_refresh.client_id: missing_parts.append("client_id (de client_secrets.json)")
                if not creds_for_refresh.client_secret: missing_parts.append("client_secret (de client_secrets.json)")
                if not creds_for_refresh.refresh_token: missing_parts.append("refresh_token (do token.json)")
                logging.error(f"ERRO: Informações cruciais para refresh faltando: {', '.join(missing_parts)}. Verifique client_secrets.json e token.json.")
                print(f"DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO: Informações cruciais para refresh faltando: {', '.join(missing_parts)}", flush=True)
                return None
            logging.info(f"Tentando refresh com: client_id={creds_for_refresh.client_id}, client_secret={'***'}, refresh_token={'***'}, token_uri={creds_for_refresh.token_uri}")
            request_obj = Request() 
            creds_for_refresh.refresh(request_obj) 
            creds = creds_for_refresh 
            logging.info("Token de acesso atualizado com sucesso usando refresh token.")
            logging.info(f"Salvando token atualizado em {token_path}...")
            token_data_to_save = {
                'token': creds.token, 
                'refresh_token': creds.refresh_token, 
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret, 
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None 
            }
            with open(token_path, 'w') as token_file:
                json.dump(token_data_to_save, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado com sucesso.")
        except FileNotFoundError:
            logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path} durante a tentativa de refresh.", exc_info=True)
            creds = None 
        except KeyError as e:
            logging.error(f"ERRO: Estrutura inesperada no arquivo {client_secrets_path} (chave faltando: {e}). Não foi possível obter informações para refresh.", exc_info=True)
            creds = None
        except Exception as e:
            logging.error(f"ERRO: Falha desconhecida ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None 
    elif not creds:
        logging.error("--- Falha crítica: token.json não encontrado ou inválido e não pôde ser carregado.")
        logging.error("Execute a autenticação inicial LOCALMENTE para criar um token.json válido com refresh_token.")
        print("DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO: token.json não encontrado ou inválido.", flush=True)
        return None
    elif not creds.valid:
        logging.error("--- Falha crítica: Credenciais não são válidas e não puderam ser atualizadas.")
        logging.error("Verifique o token.json ou execute a autenticação inicial LOCALMENTE.")
        print("DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO: Credenciais inválidas e refresh falhou.", flush=True)
        return None

    logging.info("--- Autenticação bem-sucedida ou token válido. Construindo serviço da API do YouTube. ---")
    print("DEBUG_PRINT: [FUNC_AUTH] Autenticação OK. Construindo serviço.", flush=True)
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        print("DEBUG_PRINT: [FUNC_AUTH] Serviço construído. Saindo de get_authenticated_service.", flush=True)
        return youtube_service
    except Exception as e:
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube com as credenciais obtidas: {e}", exc_info=True)
        print(f"DEBUG_PRINT_ERROR: [FUNC_AUTH] ERRO ao construir serviço: {e}", flush=True)
        return None

def get_facts_for_video(keywords, num_facts=5):
    print(f"DEBUG_PRINT: [FUNC_GET_FACTS] Keywords: {keywords}, Num_facts: {num_facts}", flush=True)
    logging.info(f"--- Obtendo fatos para o vídeo (Língua: Inglês) ---")
    logging.info(f"Keywords fornecidas: {keywords}")
    facts = [
        "Did you know that a group of owls is called a parliament? It's a wise gathering!",
        "Honey never spoils. Archaeologists have even found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still edible!",
        "The shortest war in history lasted only 38 to 45 minutes between Britain and Zanzibar on August 27, 1896.",
        "A cloud can weigh over a million pounds. That's heavier than some small planes!",
        "If you could harness the energy of a lightning bolt, you could toast 100,000 slices of bread.",
        "The average person walks the equivalent of three times around the world in a lifetime."
    ]
    if not facts:
        logging.warning("Nenhum fato foi gerado ou encontrado.")
    else:
        logging.info(f"Gerados {len(facts)} fatos (serão usados {num_facts}).")
    return facts[:num_facts]

def generate_audio_from_text(text, lang='en', output_filename="audio.mp3"):
    print(f"DEBUG_PRINT: [FUNC_GEN_AUDIO] Iniciando. Texto: '{text[:30]}...', Lang: {lang}, Output: {output_filename}", flush=True)
    logging.info(f"--- Gerando áudio a partir de texto (Língua: {lang}) ---")
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
        logging.error(f"ERRO ao gerar áudio: {e}", exc_info=True)
        return None

def create_video_from_content(facts, audio_path, channel_title="Video"):
    print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Entrando. Áudio: {audio_path}", flush=True)
    logging.info(f"--- Criando vídeo a partir de conteúdo ({len(facts)} fatos) e áudio usando MoviePy ---")
    
    try:
        current_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
        logging.info(f"MoviePy: IMAGEMAGICK_BINARY detectado ANTES da tentativa de configuração: '{current_im_binary}'")
        print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] MoviePy IMAGEMAGICK_BINARY ANTES: '{current_im_binary}'", flush=True)

        imagemagick_path = "/usr/bin/convert" # Caminho esperado após 'sudo apt-get install imagemagick'
        
        if os.path.exists(imagemagick_path):
            logging.info(f"MoviePy: Executável 'convert' encontrado em '{imagemagick_path}'. Tentando configurar...")
            print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] 'convert' encontrado em '{imagemagick_path}'. Configurando...", flush=True)
            change_settings({"IMAGEMAGICK_BINARY": imagemagick_path})
            # Verifica se a configuração foi aplicada
            new_im_binary = MOPY_CONFIG.get_setting("IMAGEMAGICK_BINARY")
            logging.info(f"MoviePy: IMAGEMAGICK_BINARY APÓS change_settings: '{new_im_binary}'")
            print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] MoviePy IMAGEMAGICK_BINARY APÓS: '{new_im_binary}'", flush=True)
            if new_im_binary != imagemagick_path:
                 logging.warning(f"MoviePy: ATENÇÃO! change_settings pode não ter surtido efeito total. IMAGEMAGICK_BINARY ainda é '{new_im_binary}'")
                 print(f"DEBUG_PRINT_WARNING: [FUNC_CREATE_VIDEO] change_settings pode não ter funcionado como esperado.", flush=True)
        else:
            logging.warning(f"MoviePy: Executável 'convert' do ImageMagick NÃO encontrado em '{imagemagick_path}'. TextClip pode falhar se MoviePy não o encontrar automaticamente ou se a config padrão for 'unset'.")
            print(f"DEBUG_PRINT_WARNING: [FUNC_CREATE_VIDEO] 'convert' NÃO encontrado em '{imagemagick_path}'.", flush=True)
    except Exception as e_conf:
        logging.warning(f"MoviePy: Exceção ao tentar configurar IMAGEMAGICK_BINARY: {e_conf}", exc_info=True)
        print(f"DEBUG_PRINT_ERROR: [FUNC_CREATE_VIDEO] Exceção ao configurar IMAGEMAGICK_BINARY: {e_conf}", flush=True)

    try:
        print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Verificando existência do arquivo de áudio: {audio_path}", flush=True)
        if not audio_path or not os.path.exists(audio_path) or not os.path.getsize(audio_path) > 0:
            size = -1
            exists = False
            if audio_path and os.path.exists(audio_path):
                size = os.path.getsize(audio_path)
                exists = True
            logging.error(f"ERRO CRÍTICO: Arquivo de áudio não encontrado ou está vazio antes de iniciar MoviePy. Caminho: {audio_path}, Existe: {exists}, Tamanho: {size}")
            print(f"DEBUG_PRINT_ERROR: [FUNC_CREATE_VIDEO] Arquivo de áudio não encontrado/vazio. Caminho: {audio_path}, Existe: {exists}, Tamanho: {size}", flush=True)
            return None
            
        logging.info(f"Arquivo de áudio '{audio_path}' encontrado e válido para MoviePy.")
        print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Arquivo de áudio '{audio_path}' OK.", flush=True)
        
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration
        W, H = 1920, 1080; FPS = 24
        clips = [ColorClip((W, H), color=(0, 0, 0), duration=total_duration)]
        duration_per_fact = total_duration / len(facts) if facts and len(facts) > 0 else total_duration
        
        for i, fact in enumerate(facts):
            print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Criando TextClip para fato {i+1}: '{fact[:30]}...'", flush=True)
            logging.info(f"Criando TextClip para o fato {i+1}: '{fact[:30]}...'")
            # Simplificado para teste, sem fonte específica, sem stroke
            text_clip_fact = TextClip(fact, fontsize=40, color='white', method='caption', align='center', size=(W*0.8, None))
            text_clip_fact = text_clip_fact.set_duration(duration_per_fact).set_position('center').set_start(i * duration_per_fact)
            clips.append(text_clip_fact)
            
        final_video_clip = CompositeVideoClip(clips, size=(W, H)).set_audio(audio_clip).set_duration(total_duration)
        output_video_dir = "generated_videos"
        os.makedirs(output_video_dir, exist_ok=True)
        video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{int(time.time())}_final.mp4"
        video_output_path = os.path.join(output_video_dir, video_output_filename)
        
        logging.info(f"Escrevendo o arquivo de vídeo final para: {video_output_path}...")
        print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Escrevendo vídeo para: {video_output_path}", flush=True)
        final_video_clip.write_videofile(video_output_path, codec='libx264', audio_codec='aac', fps=FPS, threads=4, logger='bar')
        logging.info("Arquivo de vídeo final escrito.")
        print(f"DEBUG_PRINT: [FUNC_CREATE_VIDEO] Vídeo escrito. Saindo.", flush=True)
        return video_output_path
        
    except Exception as e:
        logging.error(f"ERRO durante a criação do vídeo com MoviePy: {e}", exc_info=True)
        print(f"DEBUG_PRINT_ERROR: [FUNC_CREATE_VIDEO] ERRO MoviePy: {e}", flush=True)
        if "unset" in str(e).lower():
            logging.error("DETALHE: O erro contém a palavra 'unset'. Verifique a configuração do IMAGEMAGICK_BINARY do MoviePy e se o ImageMagick está instalado e no PATH do runner.")
        return None

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Entrando. Vídeo: {video_path}", flush=True)
    logging.info(f"--- Iniciando etapa: Upload do vídeo para o YouTube ---")
    try:
        if not video_path or not os.path.exists(video_path) or not os.path.getsize(video_path) > 0:
            size = -1
            exists = False
            if video_path and os.path.exists(video_path):
                size = os.path.getsize(video_path)
                exists = True
            logging.error(f"ERRO: Arquivo de vídeo final para upload NÃO encontrado ou está vazio. Caminho: {video_path}, Existe: {exists}, Tamanho: {size}")
            print(f"DEBUG_PRINT_ERROR: [FUNC_UPLOAD_VIDEO] Vídeo não encontrado/vazio. Caminho: {video_path}, Existe: {exists}, Tamanho: {size}", flush=True)
            return None
            
        logging.info(f"Preparando upload do arquivo: {video_path} (Tamanho: {os.path.getsize(video_path)} bytes)")
        print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Preparando upload de: {video_path}", flush=True)
        body= {
            'snippet': { 'title': title, 'description': description, 'tags': tags, 'categoryId': category_id },
            'status': { 'privacyStatus': privacy_status }
        }
        media_body = MediaFileUpload(video_path, chunksize=-1, resumable=True) # chunksize=-1 para um único chunk se pequeno, ou deixe resumable gerenciar
        logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
        print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Chamando API para upload...", flush=True)
        insert_request = youtube_service.videos().insert(part=','.join(body.keys()), body=body, media_body=media_body)
        
        response_upload = None
        retry_count = 0
        max_retries = 3
        while response_upload is None and retry_count < max_retries:
            try:
                print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Tentativa de upload {retry_count + 1}/{max_retries}...", flush=True)
                logging.info(f"Executando requisição de upload (tentativa {retry_count + 1}). Isso pode demorar...")
                response_upload, done = insert_request.next_chunk() # Para uploads resumíveis e progresso
                if done:
                    logging.info("Upload concluído após next_chunk.")
                    break # Sai do loop while se 'done' for True
                if response_upload is not None: # next_chunk pode retornar (None, False)
                    logging.info(f"Progresso do upload: {int(response_upload.progress() * 100)}%")
                    print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Progresso: {int(response_upload.progress() * 100)}%", flush=True)
            except Exception as e_upload_chunk:
                logging.error(f"Erro durante next_chunk na tentativa {retry_count + 1}: {e_upload_chunk}", exc_info=True)
                print(f"DEBUG_PRINT_ERROR: [FUNC_UPLOAD_VIDEO] Erro no next_chunk {retry_count + 1}: {e_upload_chunk}", flush=True)
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(5 * retry_count) # Backoff exponencial simples
                else:
                    logging.error("Máximo de tentativas de upload atingido.")
                    return None # Falha após todas as tentativas

        if not response_upload or not response_upload.get('id'): # Se 'done' foi true, response_upload é o resultado final.
            logging.error("ERRO: Requisição de upload executada, mas a resposta final não contém um ID de vídeo ou falhou após retentativas.")
            print(f"DEBUG_PRINT_ERROR: [FUNC_UPLOAD_VIDEO] Upload falhou ou resposta inválida: {response_upload}", flush=True)
            return None

        video_id = response_upload.get('id')
        logging.info(f"Upload completo. Vídeo ID: {video_id}")
        logging.info(f"Link do vídeo (pode não estar ativo imediatamente se for privado): https://www.youtube.com/watch?v={video_id}")
        print(f"DEBUG_PRINT: [FUNC_UPLOAD_VIDEO] Upload OK. Vídeo ID: {video_id}. Saindo.", flush=True)
        return video_id
        
    except FileNotFoundError: # Deveria ser pego pela verificação inicial, mas por segurança
        logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_path} para upload.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
        print(f"DEBUG_PRINT_ERROR: [FUNC_UPLOAD_VIDEO] Exceção no upload: {e}", flush=True)
        return None

def main(channel_name_arg):
    print(f"DEBUG_PRINT: [4] Entrando na função main. Canal: {channel_name_arg}", flush=True)
    logging.info(f"--- Iniciando processo de automação para o canal: {channel_name_arg} ---")
    
    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json"

    print("DEBUG_PRINT: [4.1] Chamando get_authenticated_service...", flush=True)
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    
    if not youtube_service:
        print("DEBUG_PRINT_ERROR: [4.2] Falha ao obter youtube_service. Encerrando.", flush=True)
        logging.error("Falha ao obter o serviço autenticado do YouTube. Encerrando o script.")
        sys.exit(1) 
    
    print("DEBUG_PRINT: [4.3] youtube_service obtido com sucesso.", flush=True)
    logging.info("Serviço do YouTube autenticado com sucesso.")

    if channel_name_arg == "fizzquirk":
        video_keywords = ["fizzquirk", "curiosidades gerais", "fatos divertidos"]
        video_title_template = "Curiosidades Incríveis com FizzQuirk! #{short_id}"
        video_description_template = "Prepare-se para fatos surpreendentes com FizzQuirk!\n\nNeste vídeo:\n{facts_list}\n\n#FizzQuirk #Curiosidades #Fatos"
        video_tags_list = ["fizzquirk", "curiosidades", "fatos", "shorts", "youtube shorts"]
    else:
        video_keywords = [channel_name_arg, "curiosidades", "fatos interessantes"]
        video_title_template = f"Vídeo de Curiosidades sobre {channel_name_arg.capitalize()}! #{int(time.time() % 10000)}"
        video_description_template = f"Descubra fatos surpreendentes neste vídeo gerado para o canal {channel_name_arg.capitalize()}.\n\nFatos:\n{{facts_list}}\n\n#{channel_name_arg.capitalize()} #Curiosidades"
        video_tags_list = [channel_name_arg, "curiosidades", "fatos", "automatizado"]
    
    logging.info(f"Keywords para o vídeo: {video_keywords}")
    print(f"DEBUG_PRINT: [4.4] Keywords: {video_keywords}", flush=True)
    facts = get_facts_for_video(keywords=video_keywords, num_facts=3) 
    
    if not facts:
        logging.error("Nenhum fato foi gerado para o vídeo. Encerrando o script.")
        print("DEBUG_PRINT_ERROR: [4.4.1] Nenhum fato gerado. Encerrando.", flush=True)
        sys.exit(1)
    
    facts_for_description = "\n- ".join(facts)
    full_text_for_audio = ". ".join(facts) + "."
    audio_file_name = f"{channel_name_arg.lower()}_{int(time.time())}_audio.mp3"

    print(f"DEBUG_PRINT: [4.5] Gerando áudio para: {audio_file_name}", flush=True)
    audio_file_path = generate_audio_from_text(text=full_text_for_audio, lang='en', output_filename=audio_file_name)
    if not audio_file_path:
        logging.error("Falha ao gerar o arquivo de áudio. Encerrando o script.")
        print("DEBUG_PRINT_ERROR: [4.5.1] Falha ao gerar áudio. Encerrando.", flush=True)
        sys.exit(1)

    print(f"DEBUG_PRINT: [4.6] Criando vídeo com áudio: {audio_file_path}", flush=True)
    video_output_path = create_video_from_content(facts=facts, audio_path=audio_file_path, channel_title=channel_name_arg)
    if not video_output_path:
        logging.error("Falha ao criar o arquivo de vídeo. Encerrando o script.")
        print("DEBUG_PRINT_ERROR: [4.6.1] Falha ao criar vídeo. Encerrando.", flush=True)
        sys.exit(1)

    final_video_title = video_title_template.format(short_id=int(time.time() % 10000))
    final_video_description = video_description_template.format(facts_list=facts_for_description)
    category_id = "28"
    privacy_status = "private"

    print(f"DEBUG_PRINT: [4.7] Fazendo upload do vídeo: {final_video_title}", flush=True)
    video_id_uploaded = upload_video(youtube_service=youtube_service,
                                     video_path=video_output_path,
                                     title=final_video_title,
                                     description=final_video_description,
                                     tags=video_tags_list,
                                     category_id=category_id,
                                     privacy_status=privacy_status)
    if video_id_uploaded:
        logging.info(f"--- Processo de automação para o canal {channel_name_arg} concluído com sucesso! ID do Vídeo: {video_id_uploaded} ---")
        print(f"DEBUG_PRINT: [4.8] SUCESSO! Vídeo ID: {video_id_uploaded}", flush=True)
        try:
            if audio_file_path and os.path.exists(audio_file_path): os.remove(audio_file_path)
            logging.info("Arquivos temporários de áudio limpos.")
        except Exception as e_clean:
            logging.warning(f"Aviso: Não foi possível limpar arquivos temporários: {e_clean}")
    else:
        logging.error(f"--- Falha no upload do vídeo para o canal {channel_name_arg}. ---")
        print(f"DEBUG_PRINT_ERROR: [4.8] FALHA no upload.", flush=True)
        sys.exit(1)
    
    print("DEBUG_PRINT: [4.9] Fim da função main.", flush=True)


if __name__ == "__main__":
    print("DEBUG_PRINT: [MAIN_BLOCK_1] Entrou em if __name__ == '__main__'.", flush=True)
    logging.info("INFO_LOG: [MAIN_BLOCK_2] Script main.py está sendo executado via __main__ (mensagem do logging).")
    
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    
    print(f"DEBUG_PRINT: [MAIN_BLOCK_3] Argumentos crus (sys.argv): {sys.argv}", flush=True)
    args = None # Inicializa args
    try:
        args = parser.parse_args()
        print(f"DEBUG_PRINT: [MAIN_BLOCK_4] Argumentos parseados: {args}", flush=True)
        
        print(f"DEBUG_PRINT: [MAIN_BLOCK_5] Chamando main('{args.channel}')", flush=True)
        main(args.channel)
        print("DEBUG_PRINT: [MAIN_BLOCK_6] Chamada para main() concluída.", flush=True)
        logging.info("INFO_LOG: [MAIN_BLOCK_7] Execução do __main__ concluída com sucesso (implícito sys.exit(0)).")

    except SystemExit as e:
        # Se o código for 0, significa um sys.exit(0) intencional, não relançar como erro.
        # Se for diferente de 0, é um erro real.
        if e.code is None or e.code == 0:
            print(f"DEBUG_PRINT: [MAIN_BLOCK_EXIT_0] SystemExit capturado no bloco __main__ com código {e.code}. Considerando sucesso ou saída normal.", flush=True)
            logging.info(f"INFO_LOG: [MAIN_BLOCK_EXIT_0] Script encerrado com sys.exit({e.code}).")
        else:
            print(f"DEBUG_PRINT_ERROR: [MAIN_BLOCK_ERROR] SystemExit capturado no bloco __main__ com código {e.code}. Isso indica uma falha.", flush=True)
            logging.info(f"INFO_LOG: [MAIN_BLOCK_ERROR] Script encerrado com sys.exit({e.code}).")
            raise # Re-levanta a SystemExit para que o GitHub Actions veja o código de saída de erro
    except Exception as e_main_block:
        print(f"DEBUG_PRINT_ERROR: [MAIN_BLOCK_ERROR] Exceção INESPERADA no bloco __main__: {e_main_block}", flush=True)
        logging.error(f"ERRO GRAVE E INESPERADO NO BLOCO __main__: {e_main_block}", exc_info=True)
        sys.exit(2)
