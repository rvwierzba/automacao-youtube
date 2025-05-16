import os
import argparse
import logging
import json
import sys
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# --- Importações Adicionais Necessárias para a Parte 2 ---
# Para gerar áudio a partir de texto
from gtts import gTTS
# Para processamento e edição de vídeo
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip
import moviepy.video.io.ffmpeg_tools as ffmpeg_tools
# Pode precisar de Pillow para TextClip/ImageClip dependendo da instalação MoviePy
from PIL import Image # Importar Pillow/PIL

# Configurar logging para enviar output para o console do Actions
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# Escopos necessários (manter)
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado (manter a versão corrigida)
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

    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
            logging.info(f"Carregando client_secrets de {client_secrets_path} para auxiliar o refresh...")
            # Use InstalledAppFlow para carregar client_secrets e configurar o refresh
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            # Define as credenciais existentes (com refresh token) no objeto flow
            flow.credentials = creds
            logging.info("Chamando flow.refresh_credentials()...")
            flow.refresh_credentials() # Tenta usar o refresh token
            creds = flow.credentials # Atualiza creds com o token de acesso recém-obtido
            logging.info("Token de acesso atualizado com sucesso usando refresh token.")

            logging.info(f"Salvando token atualizado em {token_path}...")
            with open(token_path, 'w') as token_file:
                token_data = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                json.dump(token_data, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado com sucesso.")

        except FileNotFoundError:
             logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh do token.", exc_info=True)
             creds = None
        except Exception as e:
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None

    elif creds and not creds.refresh_token:
        logging.error("ERRO: Credenciais existentes expiradas, mas SEM refresh token disponível em token.json. Não é possível re-autorizar automaticamente.")
        return None

    else:
         logging.error("--- Falha crítica: Não foi possível carregar credenciais de token.json E não há refresh token disponível ou válido. Necessário autenticação inicial LOCALMENTE. ---")
         return None

    if not creds or not creds.valid:
         logging.error("--- Falha crítica final ao obter credenciais válidas após todas as tentativas. Saindo. ---")
         return None

    logging.info("--- Autenticação bem-sucedida. Construindo serviço da API do YouTube. ---")
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube: {e}", exc_info=True)
        return None

# --- NOVAS FUNÇÕES PARA CRIAÇÃO DE CONTEÚDO E VÍDEO ---

# Função placeholder para obter fatos/texto (você precisa implementar a lógica real)
# Use as keywords do canal como base.
def get_facts_for_video(keywords, num_facts=5):
    logging.info(f"Gerando fatos baseados nas keywords: {keywords}")
    # >>>>> SEU CÓDIGO PARA OBTER FATOS REAIS VEM AQUI <<<<<
    # Você pode usar APIs, scraping (com cuidado e respeitando termos de serviço),
    # ou ter uma lista predefinida. Certifique-se de que os fatos são em INGLÊS.
    
    # Exemplo Simples (Substitua pela sua lógica real):
    facts = [
        "Did you know that a group of owls is called a parliament?",
        "Honey never spoils. Archaeologists have even found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still edible!",
        "The shortest war in history lasted only 38 to 45 minutes between Britain and Zanzibar on August 27, 1896.",
        "A cloud can weigh over a million pounds.",
        "The total weight of all ants on Earth is estimated to be about the same as the total weight of all humans."
    ]
    # <<<<< FIM DO SEU CÓDIGO PARA OBTER FATOS REAIS >>>>>

    logging.info(f"Gerados {len(facts)} fatos.")
    return facts

# Função para gerar áudio em inglês a partir de texto usando gTTS
def generate_audio_from_text(text, lang='en', output_filename="audio.mp3"):
    logging.info(f"Gerando áudio para o texto (língua: {lang})...")
    try:
        # Certifique-se que o output_filename está em um diretório acessível
        audio_path = os.path.join("temp", output_filename) # Salva em uma pasta temporária
        # Cria a pasta temp se não existir
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(audio_path)
        logging.info(f"Áudio gerado e salvo em: {audio_path}")
        return audio_path
    except Exception as e:
        logging.error(f"ERRO ao gerar áudio: {e}", exc_info=True)
        return None

# Função placeholder para criar o vídeo final (você precisa implementar a lógica MoviePy)
# Este é um exemplo BEM simples. Adapte para o estilo visual do seu canal.
def create_video_from_facts(facts, audio_path, channel_title="Video"):
    logging.info(f"Criando vídeo a partir de {len(facts)} fatos com áudio de {audio_path}...")
    try:
        # >>>>> SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY VEM AQUI <<<<<
        # Este código vai depender muito do visual que você quer (texto na tela, imagens, clipes, etc.)

        # Exemplo SIMPLES: Um clipe de cor preta com texto de cada fato, sincronizado com o áudio
        # Você precisará de lógica mais complexa se usar imagens ou outros visuais.

        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration # Duração total do vídeo será a do áudio

        # Criar um clipe de fundo (ex: tela preta simples)
        # Adapte a resolução (width, height) conforme seu padrão
        background_clip = ColorClip((1920, 1080), color=(0, 0, 0), duration=total_duration) # Exemplo: tela preta Full HD

        text_clips = []
        current_time = 0 # Tempo de início do clipe atual

        # Simplesmente adiciona cada fato como um TextClip com a duração total do vídeo
        # Você provavelmente vai querer dividir o áudio e sincronizar o texto com cada fato.
        # Isso requer analisar o áudio ou ter controle sobre a narração.
        combined_facts_text = "\n\n".join(facts) # Junta todos os fatos em um texto para este exemplo simples

        # Criar um TextClip com todos os fatos. Adapte a fonte, tamanho, cor, posição.
        text_clip = TextClip(combined_facts_text, fontsize=40, color='white', bg_color='black',
                             size=(1920*0.9, 1080*0.7), # Tamanho da caixa de texto
                             method='caption', # Ajusta quebras de linha
                             align='center') # Alinhamento do texto

        # Definir a duração do TextClip para a duração total do áudio
        text_clip = text_clip.set_duration(total_duration).set_position('center')


        # Combina o fundo e o texto
        final_video_clip = CompositeVideoClip([background_clip, text_clip])

        # Define o áudio do vídeo final
        final_video_clip = final_video_clip.set_audio(audio_clip)

        # --- FIM DO SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY ---
        # Lembre-se de adicionar LOGS DENTRO DESTE PROCESSO!

        # Salva o vídeo final em um arquivo (em uma pasta temporária)
        output_dir = "temp_videos"
        os.makedirs(output_dir, exist_ok=True)
        video_output_path = os.path.join(output_dir, f"{channel_title}_video_final.mp4")

        logging.info(f"Escrevendo o arquivo de vídeo final para: {video_output_path}. Isso pode levar tempo...")
        final_video_clip.write_videofile(video_output_path, codec='libx264', audio_codec='aac', fps=24) # Adapte FPS e codecs se necessário
        logging.info("Arquivo de vídeo final escrito.")

        return video_output_path

    except Exception as e:
        logging.error(f"ERRO durante a criação do vídeo: {e}", exc_info=True)
        return None

# --- FUNÇÃO DE UPLOAD (manter a versão corrigida) ---
# Adapte para o seu código de upload real se for diferente
def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    logging.info(f"--- Iniciando etapa: Upload do vídeo para o YouTube ---")
    try:
        logging.info(f"Preparando upload do arquivo: {video_path}")
        body= {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id # Ex: '28' para Ciência e Tecnologia. Adapte.
            },
            'status': {
                'privacyStatus': privacy_status # 'public', 'unlisted', ou 'private'. Adapte.
            }
        }

        # Verifica se o arquivo de vídeo existe antes de tentar fazer upload
        if not os.path.exists(video_path):
             logging.error(f"ERRO: Arquivo de vídeo para upload NÃO encontrado: {video_path}")
             return None # Retorna None em caso de erro

        # Cria o objeto MediaFileUpload para upload resumível
        media_body = MediaFileUpload(video_path, resumable=True)

        logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
        insert_request = youtube_service.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media_body
        )

        # Execute a requisição de upload. Pode adicionar um watcher de progresso aqui se a lib permitir
        logging.info("Executando requisição de upload. Isso pode levar tempo...")
        response_upload = insert_request.execute() # Executa a requisição HTTP real
        logging.info("Requisição de upload executada.")

        # Verifica a resposta do upload
        video_id = response_upload.get('id')
        if video_id:
            logging.info(f"Upload completo. Vídeo ID: {video_id}")
            # O link retornado pode ser adaptado
            logging.info(f"Link do vídeo (pode não estar ativo imediatamente): https://www.youtube.com/watch?v={video_id}")
            return video_id # Retorna o ID do vídeo se o upload for bem-sucedido
        else:
             logging.error("ERRO: Requisição de upload executada, mas a resposta não contém um ID de vídeo.", exc_info=True)
             return None # Retorna None em caso de falha no upload


    except FileNotFoundError:
        logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_path} para upload.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
        return None

    logging.info("--- Etapa concluída: Upload do vídeo para o YouTube ---")

# --- FIM DA FUNÇÃO DE UPLOAD ---


# Função principal do script (manter e integrar as novas chamadas)
def main(channel_name): # Renomeado para channel_name para clareza
    logging.info(f"--- Início do script de automação para o canal: {channel_name} ---")

    # Define os caminhos esperados para os arquivos JSON decodificados pelo workflow
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    config_path = os.path.join(base_dir, 'config', 'channels_config.json') # Caminho para o arquivo de configuração

    # --- Carregar Configuração do Canal ---
    logging.info(f"Carregando configuração do canal de {config_path}...")
    channel_config = None
    try:
        with open(config_path, 'r', encoding='utf-8') as f: # Garante leitura em UTF-8
            config_data = json.load(f)
            # Encontra a configuração para o canal específico pelo nome
            for channel_data in config_data.get('channels', []):
                if channel_data.get('name') == channel_name:
                    channel_config = channel_data
                    break
            if channel_config:
                 logging.info(f"Configuração encontrada para o canal '{channel_name}'.")
            else:
                 logging.error(f"ERRO: Configuração NÃO encontrada para o canal '{channel_name}' no arquivo {config_path}.")
                 sys.exit(1) # Sai se a configuração do canal não for encontrada

    except FileNotFoundError:
         logging.error(f"ERRO CRÍTICO: Arquivo de configuração NÃO encontrado em {config_path}. Certifique-se de que ele existe.")
         sys.exit(1)
    except json.JSONDecodeError:
         logging.error(f"ERRO CRÍTICO: Erro ao decodificar o arquivo de configuração {config_path}. Verifique a sintaxe JSON.", exc_info=True)
         sys.exit(1)
    except Exception as e:
         logging.error(f"ERRO inesperado ao carregar a configuração do canal: {e}", exc_info=True)
         sys.exit(1)


    # Define caminhos para credenciais com base na configuração do canal
    client_secrets_base64_path = os.path.join(credentials_dir, channel_config.get('client_secret_file', ''))
    token_base64_path = os.path.join(credentials_dir, channel_config.get('token_file', ''))

    # No workflow, decodificamos os arquivos .base64 para .json na pasta credentials
    client_secrets_path = os.path.join(credentials_dir, 'client_secret.json')
    token_path = os.path.join(credentials_dir, 'token.json')


    # Adiciona verificações para garantir que os arquivos JSON decodificados existem
    logging.info("Verificando arquivos de credenciais decodificados (client_secret.json e token.json) criados pelo workflow...")
    if not os.path.exists(client_secrets_path):
         logging.error(f"ERRO CRÍTICO: Arquivo client_secret.json NÃO encontrado em {client_secrets_path} após decodificação pelo workflow. Verifique o step 'Decodificar arquivos .base64 do Repositório' no main.yml e o arquivo de entrada {channel_config.get('client_secret_file', '')}.")
         sys.exit(1)
    if not os.path.exists(token_path):
        logging.error(f"ERRO CRÍTICO: Arquivo token.json NÃO encontrado em {token_path} após decodificação pelo workflow. Certifique-se de que {channel_config.get('token_file', '')} existe e contém dados válidos para decodificar.")
        sys.exit(1)

    logging.info("Arquivos de credenciais decodificados encontrados em credentials/.")


    # Obtém o serviço do YouTube autenticado passando os caminhos dos arquivos decodificados
    logging.info("Chamando get_authenticated_service() para autenticar com token.json e client_secret.json...")
    youtube = get_authenticated_service(client_secrets_path, token_path)
    logging.info("Chamada a get_authenticated_service() concluída.")

    # Verifica se a autenticação foi bem-sucedida (se get_authenticated_service retornou um objeto build)
    if youtube is None:
        logging.error("Falha final na autenticação do serviço YouTube. Saindo do script.")
        sys.exit(1)

    logging.info("Serviço do YouTube autenticado com sucesso e pronto para uso da API.")

    # --- INÍCIO DA SEGUNDA PARTE: CRIAÇÃO DE CONTEÚDO E VÍDEO ---

    try:
        logging.info("--- Iniciando etapa: CRIAÇÃO DE CONTEÚDO, VÍDEO E UPLOAD ---")

        # 1. Obter fatos/texto
        logging.info("Obtendo fatos para o vídeo...")
        # Use as keywords do canal
        keywords = channel_config.get('keywords', '').split(',') # Obtém keywords da config
        keywords = [k.strip() for k in keywords if k.strip()] # Limpa espaços e remove vazias
        if not keywords:
             logging.warning("Nenhuma keyword encontrada na configuração do canal. Gerando fatos padrão.")

        facts = get_facts_for_video(keywords) # Chama sua função para obter fatos

        if not facts:
             logging.error("ERRO: Não foi possível gerar fatos para o vídeo. Saindo.")
             sys.exit(1)
        logging.info(f"Fatos obtidos: {facts}")

        # 2. Gerar áudio a partir dos fatos
        # Combine todos os fatos em um texto para a narração
        audio_text = ".\n".join(facts) + "." # Junta fatos com ponto e quebra de linha
        audio_path = generate_audio_from_text(audio_text, lang='en', output_filename=f"{channel_name}_audio.mp3")

        if not audio_path:
             logging.error("ERRO: Falha ao gerar o arquivo de áudio. Saindo.")
             sys.exit(1)
        logging.info(f"Arquivo de áudio gerado: {audio_path}")


        # 3. Criar o vídeo a partir do áudio e fatos/visuais
        # Aqui você chama sua lógica MoviePy. Adapte a chamada conforme sua função.
        # O exemplo simples de create_video_from_facts está incluído acima.
        logging.info("Chamando função para criar o vídeo final...")
        video_output_path = create_video_from_facts(facts, audio_path, channel_title=channel_config.get('title', 'Video')) # Use título da config

        if not video_output_path or not os.path.exists(video_output_path):
             logging.error("ERRO: Falha ao criar o arquivo de vídeo final. Saindo.")
             sys.exit(1)
        logging.info(f"Arquivo de vídeo final criado: {video_output_path}")


        # 4. Fazer o upload do vídeo para o YouTube
        logging.info("Preparando dados para upload...")
        video_title = f"{channel_config.get('title', 'New Video')} - {facts[0][:50]}..." # Título do vídeo (adapte)
        video_description = channel_config.get('description', 'An interesting video.') # Descrição do vídeo
        video_tags = keywords # Usa as keywords como tags
        category_id = '28' # ID da categoria do YouTube (ex: 28 para Ciência e Tecnologia). Adapte.
        privacy_status = 'private' # private, unlisted, ou public. Comece com private para testar.

        logging.info("Chamando função de upload...")
        uploaded_video_id = upload_video(youtube, video_output_path, video_title, video_description, video_tags, category_id, privacy_status)

        if not uploaded_video_id:
             logging.error("ERRO: O upload do vídeo falhou. Saindo.")
             sys.exit(1)
        logging.info(f"Vídeo enviado com sucesso! ID: {uploaded_video_id}")


        # --- FIM DA SEGUNDA PARTE ---


    except Exception as e:
        # Captura erros inesperados que ocorram nesta segunda parte
        logging.error(f"ERRO INESPERADO durante a criação/upload do vídeo: {e}", exc_info=True)
        sys.exit(1)


    logging.info("--- Script de automação finalizado com sucesso ---")


# Configuração do parser de argumentos (manter)
if __name__ == "__main__":
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel é passado pelo main.yml com o nome do canal (ex: "fizzquirk")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado (conforme channels_config.json).")
    args = parser.parse_args()
    # Chama a função main passando o nome do canal
    main(args.channel)
