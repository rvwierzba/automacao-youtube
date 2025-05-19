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
# Para gerar áudio a partir de texto (Integrando scripts/video_creator.py -> criar_audio)
from gtts import gTTS
# Para processamento e edição de vídeo com MoviePy (Integrando scripts/video_creator.py -> criar_video)
# Importe as classes específicas que você vai usar para o seu vídeo.
# Classes comuns: AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx
# Integrando lógica de video_creator.py
from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx

# Pode precisar de Pillow para TextClip/ImageClip
# Certifique-se de ter 'Pillow' no seu requirements.txt
from PIL import Image # Importar Pillow/PIL


# Configurar logging para enviar output para o console do GitHub Actions
# Este logging ajudará a depurar a execução do script no ambiente do Actions.
# Use level=logging.INFO para ver as mensagens informativas sobre o progresso.
# Descomente a linha abaixo para DEBUG mais detalhado (mostrará mensagens debug do script e bibliotecas)
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')


# Escopos necessários para acessar a API do YouTube (upload é o mais comum)
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado (manter a versão corrigida)
# Esta função lida com a carga do token.json e refresh automático.
# Espera os caminhos para os arquivos JSON *já decodificados* criados pelo workflow
def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None # Inicializa credenciais como None

    # 1. Tenta carregar credenciais do token.json existente (decodificado pelo workflow)
    # Este arquivo foi criado pelo step de decodificação no main.yml a partir de canal1_token.json.base64
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path} usando from_authorized_user_file...")
            # Use Credentials.from_authorized_user_file para carregar credenciais do token.json.
            # Esta função lida automaticamente com a estrutura do token.json y su validez básica.
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            # Logar aviso si el archivo token.json está inválido/corrompido (como el error 0xf3)
            # O outros errores de parsing.
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True) # Logar traceback para entender el error de parsing
            creds = None # Garantir que creds seja None si la carga falla
    else:
        logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}. A autenticação completa pode ser necessária.")
        # Si token.json no existe, creds permanece None. El siguiente bloque lo maneja.


    # 2. Si las credenciales fueron cargadas pero están expiradas, intenta refreshar
    #   Esto acontece si el access token ha expirado.
    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
            # Use InstalledAppFlow para carregar client_secrets e configurar o refresh
            # É importante carregar o client_secrets aquí para que el objeto creds sepa su client_id/secret para el refresh.
            logging.info(f"Carregando client_secrets de {client_secrets_path} para auxiliar o refresh...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            # Define las credenciales existentes (con refresh token) en el objeto flow
            flow.credentials = creds
            logging.info("Chamando flow.refresh_credentials()...")
            # Intenta usar el refresh token para obtener un nuevo access token. Esta chamada es NO INTERACTIVA.
            # A biblioteca tentará usar o refresh_token. Se creds.refresh() estivesse disponível, seria mais direto.
            # No entanto, flow.refresh_credentials() é a maneira documentada quando se inicia com um flow.
            # Para que isso funcione corretamente, o objeto 'creds' já deve ter client_id e client_secret,
            # o que geralmente acontece se ele foi originalmente criado por um flow ou se esses campos foram
            # explicitamente carregados no token.json.
            
            # Tentativa de refresh. Nota: A API do Google Auth pode variar um pouco aqui.
            # Se creds.refresh(Request()) for o método preferido e funcionar, pode ser usado.
            # Mas flow.refresh_credentials() é mais robusto se o client_secret estiver apenas no client_secrets.json.
            creds.refresh(Request()) # Tentativa direta de refresh
            
            logging.info("Token de acesso atualizado com sucesso usando refresh token.")

            # Salva as credenciais atualizadas de volta no token.json
            logging.info(f"Salvando token atualizado em {token_path}...")
            with open(token_path, 'w') as token_file:
                # Extrai los atributos necesarios del objeto Credentials para salvar en el JSON
                token_data = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret, # Pode ser None se não estiver no token original
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None # Incluir data de expiração
                }
                json.dump(token_data, token_file, indent=4)
            logging.info(f"Arquivo {token_path} atualizado com sucesso.")

        except FileNotFoundError:
            # Este erro não deveria acontecer si el workflow creó client_secrets.json correctamente
            logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh do token.", exc_info=True)
            creds = None # Falha crítica
        except Exception as e:
            # Captura errores durante el proceso de refresh (ex: refresh token inválido)
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None # A atualização falhou, credenciais não são válidas

    elif creds and not creds.refresh_token and creds.expired: # Adicionado creds.expired aqui
        logging.error("ERRO: Credenciais existentes expiradas, mas SEM refresh token disponível em token.json. Não é possível re-autorizar automaticamente.")
        return None
    elif not creds : # Se creds é None desde o início (token.json não existia ou falhou ao carregar)
        logging.warning("Não foi possível carregar credenciais de token.json.")
        logging.error("--- Falha crítica: Necessário executar a autenticação inicial LOCALMENTE (com generate_token.py) para criar/atualizar um token.json válido com refresh token,")
        logging.error("e garantir que o arquivo canal1_token.json.base64 no repositório (o Secret TOKEN_BASE64) contenha este token codificado CORRETAMENTE.")
        return None # Indica falha crítica na autenticação

    # 3. Verifica si al final del proceso tenemos credenciais válidas
    if not creds or not creds.valid:
        # Este log es alcanzado si todos los intentos fallaron o se o token não foi refreshado e está inválido
        logging.error("--- Falha crítica final ao obter credenciais válidas após todas as tentativas. Saindo. ---")
        return None # Indica falha total na autenticación


    logging.info("--- Autenticação bem-sucedida. Construindo serviço da API do YouTube. ---")
    # Constrói o serviço da API do YouTube com as credenciais obtidas
    try:
        youtube_service = build('youtube', 'v3', credentials=creds)
        logging.info("Serviço 'youtube', 'v3' construído.")
        return youtube_service
    except Exception as e:
        # Captura falhas na construção do objeto de serviço da API
        logging.error(f"ERRO: Falha ao construir o serviço da API do YouTube: {e}", exc_info=True)
        return None

# --- FUNÇÕES PARA CRIAÇÃO DE CONTEÚDO E VÍDEO ---

# Função para obter fatos/texto (você precisa implementar a lógica real)
# Use as keywords do canal como base. A linguagem deve ser INGLÊS ('en').
# Retorna uma LISTA de strings, onde cada string é um fato.
# Baseado em scripts/video_creator.py -> criar_video, adaptando a obtenção do texto
def get_facts_for_video(keywords, num_facts=5):
    logging.info(f"--- Obtendo fatos para o vídeo (Língua: Inglês) ---")
    logging.info(f"Keywords fornecidas: {keywords}")
    # >>>>> SEU CÓDIGO PARA OBTER FATOS REAIS EM INGLÊS VEM AQUI <<<<<
    # Use as keywords como base para buscar fatos (ex: APIs externas, scraping - CUIDADO!, lista predefinida).
    # Esta é uma implementação BÁSICA e ESTÁTICA com alguns exemplos. SUBSTITUA PELA SUA LÓGICA REAL.
    # Certifique-se de que o texto obtido está formatado corretamente para Text-to-Speech e exibição.

    # Exemplo Simples Estático (Substitua pela sua lógica real que gera/busca fatos em INGLÊS):
    facts = [
        "Did you know that a group of owls is called a parliament? It's a wise gathering!",
        "Honey never spoils. Archaeologists have even found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still edible!",
        "The shortest war in history lasted only 38 to 45 minutes between Britain and Zanzibar on August 27, 1896.",
        "A cloud can weigh over a million pounds. That's heavier than some small planes!",
        "If you could harness the energy of a lightning bolt, you could toast 100,000 slices of bread.",
        "The average person walks the equivalent of three times around the world in a lifetime."
    ]
    # <<<<< FIM DO SEU CÓDIGO PARA OBTER FATOS REAIS >>>>>

    if not facts:
        logging.warning("Nenhum fato foi gerado ou encontrado.")
    else:
        logging.info(f"Gerados {len(facts)} fatos.")

    return facts[:num_facts] # Retorna o número de fatos solicitado

# Função para gerar áudio em inglês a partir de texto usando gTTS
# Salva o arquivo de áudio em uma pasta temporária
# Baseado em scripts/video_creator.py -> criar_audio
def generate_audio_from_text(text, lang='en', output_filename="audio.mp3"):
    logging.info(f"--- Gerando áudio a partir de texto (Língua: {lang}) ---")
    try:
        # Define o caminho de saída dentro de uma pasta temporária para áudios
        output_dir = "temp_audio"
        os.makedirs(output_dir, exist_ok=True) # Cria la carpeta temp_audio si no existe
        audio_path = os.path.join(output_dir, output_filename)

        tts = gTTS(text=text, lang=lang, slow=False) # lang='en' para inglês
        tts.save(audio_path)
        logging.info(f"Áudio gerado e salvo em: {audio_path}")
        return audio_path
    except Exception as e:
        logging.error(f"ERRO ao gerar áudio: {e}", exc_info=True)
        return None

# Função para criar o vídeo final usando MoviePy
# Adapte esta função COMPLETAMENTE para o estilo visual do seu canal!
# Recebe a lista de fatos, caminho do áudio, e o título do canal (para nomear o arquivo)
# Baseado em scripts/video_creator.py -> criar_video, adaptando a lógica MoviePy
def create_video_from_content(facts, audio_path, channel_title="Video"):
    logging.info(f"--- Criando vídeo a partir de conteúdo ({len(facts)} fatos) e áudio usando MoviePy ---")
    try:
        # Carrega o clipe de áudio gerado
        if not os.path.exists(audio_path):
            logging.error(f"Arquivo de áudio não encontrado: {audio_path}")
            return None

        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration # A duração do vídeo será a do áudio

        # --- >>>>> SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY VEM AQUI <<<<< ---
        # Este código é um EXEMPLO BÁSICO de um vídeo simples: tela preta com texto.
        # Adapte-o COMPLETAMENTE ao estilo visual do seu canal (imagens, animações, transições, etc.).
        # Se precisar de imagens/clipes, certifique-se de que foram baixados/gerenciados ANTES desta função e use os caminhos aqui.

        W, H = 1920, 1080 # Resolução Exemplo: Full HD (adapte se necessário)
        FPS = 24 # Quadros por segundo Exemplo: 24 FPS (adapte se necessário)

        clips = [] # Lista para armazenar os clipes de vídeo

        # Criar um clipe de fundo para todo o vídeo
        background_clip = ColorClip((W, H), color=(0, 0, 0), duration=total_duration) # Fundo preto
        clips.append(background_clip) # Adiciona o fundo como primeiro clipe (base)

        # Dividir a duração total igualmente entre os fatos para este exemplo simples
        duration_per_fact = total_duration / len(facts) if len(facts) > 0 else total_duration

        for i, fact in enumerate(facts):
            text_clip_fact = TextClip(fact,
                                      fontsize=40,
                                      color='white',
                                      bg_color='transparent',
                                      size=(W*0.8, None), # Largura da caixa de texto, altura automática
                                      method='caption', # Quebra de linha automática
                                      align='center',
                                      stroke_color='black',
                                      stroke_width=1,
                                      font='Arial' # Exemplo de fonte, certifique-se que está disponível
                                     )

            text_clip_fact = text_clip_fact.set_duration(duration_per_fact)
            text_clip_fact = text_clip_fact.set_position('center')
            text_clip_fact = text_clip_fact.set_start(i * duration_per_fact)

            clips.append(text_clip_fact)


        final_video_clip = CompositeVideoClip(clips, size=(W, H))
        final_video_clip = final_video_clip.set_audio(audio_clip)
        final_video_clip = final_video_clip.set_duration(total_duration) # Garante a duração correta

        # --- <<<<< FIM DO SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY >>>>> ---
        
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
                                         threads=4, # Ajuste conforme necessário
                                         logger='bar' # Mostra uma barra de progresso no console
                                        )
        logging.info("Arquivo de vídeo final escrito.")

        return video_output_path

    except Exception as e:
        logging.error(f"ERRO durante a criação do vídeo com MoviePy: {e}", exc_info=True)
        return None

# --- FUNÇÃO DE UPLOAD ---
# Esta função recebe o caminho do arquivo de vídeo e faz o upload para o YouTube
# Adaptação baseada no seu script upload_youtube.py
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

    # Caminhos para os arquivos de credenciais
    # Estes caminhos são relativos à raiz do repositório onde o script é executado no GitHub Actions
    client_secrets_path = "credentials/client_secret.json"
    token_path = "credentials/token.json"

    # 1. Obter serviço autenticado do YouTube
    youtube_service = get_authenticated_service(client_secrets_path, token_path)

    if not youtube_service:
        logging.error("Falha ao obter o serviço autenticado do YouTube. Encerrando o script.")
        sys.exit(1) # Encerra o script com código de erro

    logging.info("Serviço do YouTube autenticado com sucesso.")

    # 2. Obter/Gerar conteúdo para o vídeo
    # Adapte esta parte para carregar keywords do seu 'channels_config.json' ou outra fonte
    # Por enquanto, usando um exemplo genérico.
    if channel_name_arg == "fizzquirk": # Exemplo de como personalizar por canal
        video_keywords = ["fizzquirk", "curiosidades gerais", "fatos divertidos"]
        video_title_template = "Curiosidades Incríveis com FizzQuirk! #{short_id}"
        video_description_template = "Prepare-se para fatos surpreendentes com FizzQuirk!\n\nNeste vídeo:\n{facts_list}\n\n#FizzQuirk #Curiosidades #Fatos"
        video_tags_list = ["fizzquirk", "curiosidades", "fatos", "shorts", "youtube shorts"]
    else: # Configuração padrão ou para outros canais
        video_keywords = [channel_name_arg, "curiosidades", "fatos interessantes"]
        video_title_template = f"Vídeo de Curiosidades sobre {channel_name_arg.capitalize()}! #{int(time.time() % 10000)}" # Adiciona um ID curto
        video_description_template = f"Descubra fatos surpreendentes neste vídeo gerado para o canal {channel_name_arg.capitalize()}.\n\nFatos:\n{{facts_list}}\n\n#{channel_name_arg.capitalize()} #Curiosidades"
        video_tags_list = [channel_name_arg, "curiosidades", "fatos", "automatizado"]
    
    logging.info(f"Keywords para o vídeo: {video_keywords}")
    facts = get_facts_for_video(keywords=video_keywords, num_facts=3) # Reduzido para 3 fatos para vídeos mais curtos

    if not facts:
        logging.error("Nenhum fato foi gerado para o vídeo. Encerrando o script.")
        sys.exit(1)

    facts_for_description = "\n- ".join(facts)
    full_text_for_audio = ". ".join(facts) # Adiciona ponto final para melhor leitura do TTS

    # 3. Gerar áudio a partir do texto
    audio_file_name = f"{channel_name_arg.lower()}_{int(time.time())}_audio.mp3"
    audio_file_path = generate_audio_from_text(text=full_text_for_audio, lang='en', output_filename=audio_file_name)

    if not audio_file_path:
        logging.error("Falha ao gerar o arquivo de áudio. Encerrando o script.")
        sys.exit(1)

    # 4. Criar o vídeo
    video_output_path = create_video_from_content(facts=facts, audio_path=audio_file_path, channel_title=channel_name_arg)

    if not video_output_path:
        logging.error("Falha ao criar o arquivo de vídeo. Encerrando o script.")
        sys.exit(1)

    # 5. Fazer upload do vídeo
    # Prepara os metadados do vídeo
    final_video_title = video_title_template.format(short_id=int(time.time() % 10000))
    final_video_description = video_description_template.format(facts_list=facts_for_description)
    
    category_id = "28"  # Ciência e Tecnologia. Outros comuns: 22 (Pessoas e Blogs), 24 (Entretenimento)
    privacy_status = "private"  # MUDE PARA 'public' QUANDO ESTIVER PRONTO PARA PUBLICAR DE VERDADE

    video_id_uploaded = upload_video(youtube_service=youtube_service,
                                     video_path=video_output_path,
                                     title=final_video_title,
                                     description=final_video_description,
                                     tags=video_tags_list,
                                     category_id=category_id,
                                     privacy_status=privacy_status)

    if video_id_uploaded:
        logging.info(f"--- Processo de automação para o canal {channel_name_arg} concluído com sucesso! ID do Vídeo: {video_id_uploaded} ---")
        # Limpar arquivos temporários se desejar (opcional)
        try:
            if os.path.exists(audio_file_path): os.remove(audio_file_path)
            # if os.path.exists(video_output_path): os.remove(video_output_path) # Não remova o vídeo final se quiser guardá-lo
            logging.info("Arquivos temporários de áudio limpos.")
        except Exception as e:
            logging.warning(f"Aviso: Não foi possível limpar arquivos temporários: {e}")
    else:
        logging.error(f"--- Falha no upload do vídeo para o canal {channel_name_arg}. ---")
        sys.exit(1)

# --- BLOCO DE EXECUÇÃO PRINCIPAL DO SCRIPT ---
# Este bloco deve vir DEPOIS da definição da função main e de todas as outras funções.
if __name__ == "__main__":
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel é passado pelo main.yml com o nome do canal (ex: "fizzquirk")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado (conforme channels_config.json).")
    args = parser.parse_args()
    
    # Chama a função main passando o nome do canal
    main(args.channel)
