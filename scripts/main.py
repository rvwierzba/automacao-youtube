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
    #    Esto acontece si el access token ha expirado.
    if creds and creds.expired and creds.refresh_token:
        logging.info("Credenciais expiradas, tentando atualizar usando refresh token.")
        try:
             # Use InstalledAppFlow para carregar client_secrets e configurar o refresh
             # É importante carregar o client_secrets aqui para que o objeto creds saiba seu client_id/secret para o refresh.
             logging.info(f"Carregando client_secrets de {client_secrets_path} para auxiliar o refresh...")
             flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
             # Define as credenciais existentes (com refresh token) no objeto flow
             flow.credentials = creds
             logging.info("Chamando flow.refresh_credentials()...")
             # Tenta usar o refresh token para obter um novo access token. Esta llamada es NO INTERACTIVA.
             flow.refresh_credentials()
             creds = flow.credentials # Atualiza creds com o token de acesso recém-obtido
             logging.info("Token de acesso atualizado com sucesso usando refresh token.")

             # Salva as credenciais atualizadas de volta no token.json
             logging.info(f"Salvando token atualizado em {token_path}...")
             with open(token_path, 'w') as token_file:
                 # Extrai os atributos necessários do objeto Credentials para salvar no JSON
                 token_data = {
                     'token': creds.token,
                     'refresh_token': creds.refresh_token,
                     'token_uri': creds.token_uri,
                     'client_id': creds.client_id,
                     'client_secret': creds.client_secret,
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
            # Captura erros durante o processo de refresh (ex: refresh token inválido)
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None # A atualização falhou, credenciais não são válidas

    elif creds and not creds.refresh_token:
        logging.error("ERRO: Credenciais existentes expiradas, mas SEM refresh token disponível em token.json. Não é possível re-autorizar automaticamente.")
        return None

    else:
         # Caso donde token.json no existe, está vacío/corrompido, o no contenía refresh token válido para el refresh.
         logging.warning("Não foi possível carregar credenciais de token.json E não há refresh token disponível ou válido.")
         logging.error("--- Falha crítica: Necessário executar a autenticação inicial LOCALMENTE (com generate_token.py) para criar/atualizar um token.json válido com refresh token,")
         logging.error("e garantir que o arquivo canal1_token.json.base64 no repositório (ou Secret TOKEN_BASE64) contenha este token codificado CORRETAMENTE.")
         return None # Indica falha crítica na autenticação


    # 3. Verifica si al final del proceso tenemos credenciais válidas
    if not creds or not creds.valid:
         # Este log es alcanzado si todos los intentos fallaron
         logging.error("--- Falha crítica final ao obter credenciais válidas após todas as tentativas. Saindo. ---")
         return None # Indica falha total na autenticação


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

    return facts

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

        # Exemplo BÁSICO:
        W, H = 1920, 1080 # Resolução Exemplo: Full HD (adapte se necessário)
        FPS = 24 # Quadros por segundo Exemplo: 24 FPS (adapte se necessário)

        # Cria um clipe de fundo (pode ser uma cor sólida, ou carregue uma IMAGEM/VÍDEO BASE aqui)
        # Ex: background_clip = ColorClip((W, H), color=(0, 0, 0), duration=total_duration) # Fundo preto
        # Ex: background_clip = ImageClip("caminho/para/imagem_fundo.jpg").set_duration(total_duration).resize(newsize=(W,H)) # Imagem de fundo estática
        # Ex: background_clip = VideoFileClip("caminho/para/video_base.mp4").subclip(0, total_duration).resize(newsize=(W,H)) # Vídeo de fundo

        # Neste exemplo simples, criaremos clipes de texto individuais para cada fato
        # e os exibiremos sequencialmente.

        clips = [] # Lista para armazenar os clipes de vídeo
        current_text_time = 0 # Tempo de início do texto atual

        # Criar um clipe de fundo para todo o vídeo
        background_clip = ColorClip((W, H), color=(0, 0, 0), duration=total_duration) # Fundo preto

        clips.append(background_clip) # Adiciona o fundo como primeiro clipe (base)

        # Exemplo de como mostrar cada fato como texto na tela por uma fração da duração total
        # Você provavelmente vai querer sincronizar isso mais precisamente com o áudio.
        # Isso requer analisar o áudio para obter timings de fala ou ter controle sobre a narração.

        # Dividir a duração total igualmente entre os fatos para este exemplo simples
        duration_per_fact = total_duration / len(facts) if len(facts) > 0 else total_duration

        for i, fact in enumerate(facts):
            # Cria um TextClip para cada fato
            # Adapte fonte, tamanho da fonte (fontsize), cor (color), alinhamento (align), etc.
            # Certifique-se de que a fonte usada está disponível no ambiente do GitHub Actions ou a inclua.
            text_clip_fact = TextClip(fact,
                                    fontsize=40,
                                    color='white',
                                    bg_color='transparent', # Fundo transparente
                                    size=(W*0.8, None), # Largura da caixa de texto, altura automática
                                    method='caption',
                                    align='center', # Alinha o texto ao centro
                                    stroke_color='black', # Exemplo de contorno
                                    stroke_width=1)

            # Define a duração e a posição do clipe de texto do fato
            # Neste exemplo, cada fato aparece por `duration_per_fact` segundos
            # Você pode adicionar efeitos (fadeIn, fadeOut) se quiser
            text_clip_fact = text_clip_fact.set_duration(duration_per_fact)
            text_clip_fact = text_clip_fact.set_position('center') # Centraliza o texto na tela
            # Define o tempo de início do clipe de texto
            text_clip_fact = text_clip_fact.set_start(i * duration_per_fact) # Fato i começa após os fatos anteriores

            clips.append(text_clip_fact) # Adiciona o clipe de texto à lista de clipes


        # Combina todos os clipes visuais
        # Use CompositeVideoClip para sobrepor (fundo + textos)
        # Ou concatenate_videoclips para clipes que vêm um depois do outro
        final_video_clip = CompositeVideoClip(clips, size=(W, H)) # Combina o fundo e os textos sobrepostos


        # Define o áudio do vídeo final como o áudio gerado anteriormente
        final_video_clip = final_video_clip.set_audio(audio_clip)

        # Garante que a duração do vídeo final corresponda à duração do áudio
        final_video_clip = final_video_clip.set_duration(total_duration)


        # --- <<<<< FIM DO SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY >>>>> ---
        # Lembre-se de adicionar LOGS BASTANTE DETALHADOS DENTRO DESTE PROCESSO!
        # Ex: logging.info("MoviePy: Carregando clip de áudio...")
        # Ex: logging.info("MoviePy: Sincronizando clipes...")
        # Ex: logging.info("MoviePy: Iniciando a escrita do arquivo de vídeo (renderização)...")
        # Ex: logging.info(f"MoviePy: Renderizando quadro {i}/{total_quadros}...") # Si puede agregar un ciclo de progreso


        # Salva o vídeo final em un archivo
        # Use un nombre de archivo único, tal vez basado en el timestamp, y en una carpeta de salida
        timestamp = int(time.time()) # Timestamp actual para nombre único
        output_video_dir = "generated_videos"
        os.makedirs(output_video_dir, exist_ok=True) # Crea la carpeta si no existe
        video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{timestamp}_final.mp4"
        video_output_path = os.path.join(output_video_dir, video_output_filename)


        logging.info(f"Escrevendo o archivo de vídeo final para: {video_output_path}. Esto puede tardar un tiempo...") # Corregido EOL error aquí y en el log
        # Use un logger de progreso si moviepy.write_videofile soporta y configura
        final_video_clip.write_videofile(video_output_path,
                                         codec='libx264', # Codec de vídeo común y recomendado para MP4
                                         audio_codec='aac', # Codec de audio común y recomendado
                                         fps=FPS, # Quadros por segundo definidos antes
                                         threads=4 # Puede ajustar el número de threads para renderización
                                         # logger='bar' # Descomente si desea ver una barra de progreso en el log en el terminal
                                        )
        logging.info("Archivo de vídeo final escrito.")

        return video_output_path # Retorna el camino del archivo de vídeo final

    except Exception as e:
        logging.error(f"ERRO durante a criação do vídeo com MoviePy: {e}", exc_info=True)
        return None

# --- FUNÇÃO DE UPLOAD ---
# Esta função recebe o caminho do arquivo de vídeo e faz o upload para o YouTube
# Adaptação baseada no seu script upload_youtube.py
def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    logging.info(f"--- Iniciando etapa: Upload do vídeo para o YouTube ---")
    try:
        # Verifica si el archivo de vídeo final fue realmente creado y tiene contenido (tamaño > 0)
        if not os.path.exists(video_path) or not os.path.getsize(video_path) > 0:
             logging.error(f"ERRO: Arquivo de vídeo final para upload NÃO encontrado ou está vazio em: {video_path}")
             return None # Retorna None en caso de error

        logging.info(f"Preparando upload do arquivo: {video_path}")
        # Define los metadados do upload (título, descrição, tags, categoria, status de privacidade)
        body= {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id # ID da categoria do YouTube. Ex: '28' para Ciência e Tecnologia. Adapte. Lista de IDs: https://developers.google.com/youtube/v3/docs/videos#snippet.categoryId
            },
            'status': {
                'privacyStatus': privacy_status # 'public', 'unlisted', ou 'private'. Comece com 'private' para testar!
            }
            # Opcional: Adicionar 'publisheAt' para agendar o vídeo
            # 'scheduledStartTime': 'YYYY-MM-DDTHH:MM:SS.0Z' # Use 'publishAt' em vez de 'scheduledStartTime'
        }

        # Cria el objeto MediaFileUpload para upload resumível
        # O upload resumível es recomendado para arquivos maiores ou conexões instáveis
        media_body = MediaFileUpload(video_path, resumable=True)

        logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
        # Usa el método insert() da API videos().
        # Define el 'part' como 'snippet,status' para incluir los metadados y el status de privacidad.
        insert_request = youtube_service.videos().insert(
            part=','.join(body.keys()), # Partes da requisição (snippet, status)
            body=body, # Corpo da requisição com metadados do vídeo
            media_body=media_body # Corpo da mídia (el arquivo de vídeo)
        )

        # Ejecuta la requisición de upload. Esto fará o upload real.
        # Este passo puede llevar bastante tiempo dependiendo do tamanho do vídeo e conexión do runner.
        logging.info("Executando requisição de upload. Esto puede tardar un tiempo...") # Corrigido EOL error aquí y en el log
        # O Google API client suporta upload resumível automaticamente con MediaFileUpload(..., resumable=True).
        # La llamada execute() gerencia los chunks e el progreso por baixo dos panos.
        # Si precisa un watcher de progreso explícito, la documentación de la biblioteca muestra como usar un MediaUploadProgress.
        response_upload = insert_request.execute() # Ejecuta la requisición HTTP real
        logging.info("Requisição de upload executada.")

        # Verifica la respuesta del upload
        video_id = response_upload.get('id')
        if video_id:
            logging.info(f"Upload completo. Vídeo ID: {video_id}")
            # Construye el link correcto del YouTube
            logging.info(f"Link do vídeo (puede no estar activo inmediatamente si es privado): https://youtu.be/{video_id}") # Link correto do YouTube
            return video_id # Retorna el ID del vídeo si el upload fue bem-sucedido
        else:
             logging.error("ERRO: Requisição de upload executada, mas a resposta não contém um ID de vídeo.", exc_info=True)
             return None # Retorna None en caso de falha en el upload


    except FileNotFoundError:
        # Captura el error si el archivo de vídeo no fue encontrado para la MediaFileUpload
        logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_path} para upload.", exc_info=True)
        return None
    except Exception as e:
        # Captura outros errores durante el proceso de upload
        logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
        return None

    # Note: La mensaje de éxito final del upload ya está dentro del try/except arriba.
    # No necesitamos otra aquí a menos que haya lógica adicional pós-upload.


# Función principal do script
# Esta função coordena las etapas da automação para un canal específico
if __name__ == "__main__":
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel es pasado por el main.yml con el nombre del canal (ex: "fizzquirk")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado (conforme channels_config.json).")
    args = parser.parse_args()
    # Llama la función main pasando el nombre del canal
    main(args.channel)
