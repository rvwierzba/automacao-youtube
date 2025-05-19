import os
import argparse
import logging
import json
import sys
import time # Útil para criar nomes de arquivo únicos baseados no tempo
from googleapiclient.discovery import build # Para construir o serviço da API do YouTube
from google_auth_oauthlib.flow import InstalledAppFlow # Necessário para carregar client_secrets
from google.auth.transport.requests import Request # Para usar Requests com credenciais
from google.oauth2.credentials import Credentials # Necessário para carregar de token.json
from googleapiclient.http import MediaFileUpload # Necessário para upload de mídia

# --- Importações Adicionais Necessárias para a Criação de Conteúdo/Vídeo ---
from gtts import gTTS
from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx
from PIL import Image


# Configurar logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# Escopos
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service(client_secrets_path, token_path):
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
            # Carrega client_id, client_secret e token_uri do client_secrets.json
            # Estes são autoritativos e necessários para o refresh.
            if not os.path.exists(client_secrets_path):
                logging.error(f"ERRO CRÍTICO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh.")
                return None

            with open(client_secrets_path, 'r') as f:
                client_secrets_info = json.load(f)
            
            # Verifica se a estrutura esperada 'installed' existe
            if 'installed' not in client_secrets_info:
                logging.error(f"ERRO: Estrutura 'installed' não encontrada em {client_secrets_path}.")
                return None
            
            secrets = client_secrets_info['installed']

            # Recria o objeto Credentials com todas as informações necessárias para o refresh.
            # Isso garante que client_id e client_secret sejam definitivamente do arquivo client_secrets.json.
            # O refresh_token vem do token.json (que já está em 'creds').
            creds_for_refresh = Credentials(
                token=None, # Token de acesso atual está expirado, não é necessário aqui
                refresh_token=creds.refresh_token,
                token_uri=secrets.get('token_uri', 'https://oauth2.googleapis.com/token'), # Pega de secrets ou usa um default comum
                client_id=secrets.get('client_id'),
                client_secret=secrets.get('client_secret'),
                scopes=creds.scopes # Mantém os escopos originais
            )
            
            if not creds_for_refresh.client_id or not creds_for_refresh.client_secret:
                logging.error("ERRO: client_id ou client_secret não puderam ser obtidos de client_secrets.json.")
                return None

            logging.info(f"Tentando refresh com: client_id={creds_for_refresh.client_id}, client_secret={'***'}, refresh_token={'***' if creds_for_refresh.refresh_token else 'NONE'}, token_uri={creds_for_refresh.token_uri}")
            
            request_obj = Request()
            creds_for_refresh.refresh(request_obj)
            
            # Substitui as credenciais antigas pelas novas, atualizadas
            creds = creds_for_refresh
            logging.info("Token de acesso atualizado com sucesso usando refresh token.")

            # Salva as credenciais atualizadas de volta no token.json
            logging.info(f"Salvando token atualizado em {token_path}...")
            token_data = {
                'token': creds.token, # Este é o novo token de acesso
                'refresh_token': creds.refresh_token, # O refresh token geralmente permanece o mesmo
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret, # Agora deve estar populado
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            with open(token_path, 'w') as token_file:
                json.dump(token_data, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado com sucesso.")

        except FileNotFoundError: # Embora já verificado acima, por segurança
            logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path} durante refresh.", exc_info=True)
            creds = None
        except KeyError as e:
            logging.error(f"ERRO: Estrutura inesperada no arquivo {client_secrets_path}. Chave faltando: {e}", exc_info=True)
            creds = None
        except Exception as e:
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None # A atualização falhou

    elif not creds: # Se creds ainda é None (token.json não existia ou falhou ao carregar inicialmente)
        logging.error("--- Falha crítica: token.json não encontrado ou inválido e não pôde ser carregado.")
        logging.error("Execute a autenticação inicial LOCALMENTE para criar um token.json válido com refresh_token.")
        return None

    elif not creds.valid: # Se creds não é None, mas não é válido (e não pôde ser refreshado)
        logging.error("--- Falha crítica: Credenciais não são válidas e não puderam ser atualizadas (sem refresh token ou refresh falhou).")
        logging.error("Verifique o token.json ou execute a autenticação inicial LOCALMENTE.")
        return None

    logging.info("--- Autenticação bem-sucedida ou token válido. Construindo serviço da API do YouTube. ---")
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube: {e}", exc_info=True)
        return None

# --- FUNÇÕES PARA CRIAÇÃO DE CONTEÚDO E VÍDEO (mantidas como na sua versão) ---
def get_facts_for_video(keywords, num_facts=5):
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
        logging.info(f"Gerados {len(facts)} fatos.")
    return facts[:num_facts]

def generate_audio_from_text(text, lang='en', output_filename="audio.mp3"):
    logging.info(f"--- Gerando áudio a partir de texto (Língua: {lang}) ---")
    try:
        output_dir = "temp_audio"
        os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, output_filename)
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(audio_path)
        logging.info(f"Áudio gerado e salvo em: {audio_path}")
        return audio_path
    except Exception as e:
        logging.error(f"ERRO ao gerar áudio: {e}", exc_info=True)
        return None

def create_video_from_content(facts, audio_path, channel_title="Video"):
    logging.info(f"--- Criando vídeo a partir de conteúdo ({len(facts)} fatos) e áudio usando MoviePy ---")
    try:
        if not os.path.exists(audio_path):
            logging.error(f"Arquivo de áudio não encontrado: {audio_path}")
            return None
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration
        W, H = 1920, 1080
        FPS = 24
        clips = []
        background_clip = ColorClip((W, H), color=(0, 0, 0), duration=total_duration)
        clips.append(background_clip)
        duration_per_fact = total_duration / len(facts) if len(facts) > 0 else total_duration
        for i, fact in enumerate(facts):
            text_clip_fact = TextClip(fact,
                                      fontsize=40,
                                      color='white',
                                      bg_color='transparent',
                                      size=(W*0.8, None),
                                      method='caption',
                                      align='center',
                                      stroke_color='black',
                                      stroke_width=1,
                                      font='Arial'
                                     )
            text_clip_fact = text_clip_fact.set_duration(duration_per_fact)
            text_clip_fact = text_clip_fact.set_position('center')
            text_clip_fact = text_clip_fact.set_start(i * duration_per_fact)
            clips.append(text_clip_fact)
        final_video_clip = CompositeVideoClip(clips, size=(W, H))
        final_video_clip = final_video_clip.set_audio(audio_clip)
        final_video_clip = final_video_clip.set_duration(total_duration)
        timestamp = int(time.time())
        output_video_dir = "generated_videos"
        os.makedirs(output_video_dir, exist_ok=True)
        video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{timestamp}_final.mp4"
        video_output_path = os.path.join(output_video_dir, video_output_filename)
        logging.info(f"Escrevendo o arquivo de vídeo final para: {video_output_path}. Isso pode demorar um pouco...")
        final_video_clip.write_videofile(video_output_path,
                                         codec='libx264',
                                         audio_codec='aac',
                                         fps=FPS,
                                         threads=4,
                                         logger='bar'
                                        )
        logging.info("Arquivo de vídeo final escrito.")
        return video_output_path
    except Exception as e:
        logging.error(f"ERRO durante a criação do vídeo com MoviePy: {e}", exc_info=True)
        return None

def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    logging.info(f"--- Iniciando etapa: Upload do vídeo para o YouTube ---")
    try:
        if not os.path.exists(video_path) or not os.path.getsize(video_path) > 0:
            logging.error(f"ERRO: Arquivo de vídeo final para upload NÃO encontrado ou está vazio em: {video_path}")
            return None
        logging.info(f"Preparando upload do arquivo: {video_path}")
        body= {
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
        media_body = MediaFileUpload(video_path, resumable=True)
        logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
        insert_request = youtube_service.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media_body
        )
        logging.info("Executando requisição de upload. Isso pode demorar um pouco...")
        response_upload = insert_request.execute()
        logging.info("Requisição de upload executada.")
        video_id = response_upload.get('id')
        if video_id:
            logging.info(f"Upload completo. Vídeo ID: {video_id}")
            # Corrigido o link do vídeo para o formato padrão do YouTube
            logging.info(f"Link do vídeo (pode não estar ativo imediatamente se for privado): https://www.youtube.com/watch?v={video_id}")
            return video_id
        else:
            logging.error("ERRO: Requisição de upload executada, mas a resposta não contém um ID de vídeo.", exc_info=True)
            return None
    except FileNotFoundError:
        logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_path} para upload.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
        return None

# Função principal que orquestra a automação
def main(channel_name_arg):
    logging.info(f"--- Iniciando processo de automação para o canal: {channel_name_arg} ---")
    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json"
    youtube_service = get_authenticated_service(client_secrets_path, token_path)
    if not youtube_service:
        logging.error("Falha ao obter o serviço autenticado do YouTube. Encerrando o script.")
        sys.exit(1)
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
    facts = get_facts_for_video(keywords=video_keywords, num_facts=3)
    if not facts:
        logging.error("Nenhum fato foi gerado para o vídeo. Encerrando o script.")
        sys.exit(1)
    facts_for_description = "\n- ".join(facts)
    full_text_for_audio = ". ".join(facts) + "." # Adiciona um ponto final extra para garantir que o TTS termine a frase.
    audio_file_name = f"{channel_name_arg.lower()}_{int(time.time())}_audio.mp3"
    audio_file_path = generate_audio_from_text(text=full_text_for_audio, lang='en', output_filename=audio_file_name)
    if not audio_file_path:
        logging.error("Falha ao gerar o arquivo de áudio. Encerrando o script.")
        sys.exit(1)
    video_output_path = create_video_from_content(facts=facts, audio_path=audio_file_path, channel_title=channel_name_arg)
    if not video_output_path:
        logging.error("Falha ao criar o arquivo de vídeo. Encerrando o script.")
        sys.exit(1)
    final_video_title = video_title_template.format(short_id=int(time.time() % 10000))
    final_video_description = video_description_template.format(facts_list=facts_for_description)
    category_id = "28"
    privacy_status = "private"
    video_id_uploaded = upload_video(youtube_service=youtube_service,
                                     video_path=video_output_path,
                                     title=final_video_title,
                                     description=final_video_description,
                                     tags=video_tags_list,
                                     category_id=category_id,
                                     privacy_status=privacy_status)
    if video_id_uploaded:
        logging.info(f"--- Processo de automação para o canal {channel_name_arg} concluído com sucesso! ID do Vídeo: {video_id_uploaded} ---")
        try:
            if os.path.exists(audio_file_path): os.remove(audio_file_path)
            logging.info("Arquivos temporários de áudio limpos.")
        except Exception as e:
            logging.warning(f"Aviso: Não foi possível limpar arquivos temporários: {e}")
    else:
        logging.error(f"--- Falha no upload do vídeo para o canal {channel_name_arg}. ---")
        sys.exit(1)

# --- BLOCO DE EXECUÇÃO PRINCIPAL DO SCRIPT ---
if __name__ == "__main__":
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    args = parser.parse_args()
    main(args.channel)
