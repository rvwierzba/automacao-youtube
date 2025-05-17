import os
import argparse
import logging
import json
import sys
import time # Útil para criar nomes de arquivo únicos baseados no tempo
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow # Necessário para carregar client_secrets
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials # Necessário para carregar de token.json
from googleapiclient.http import MediaFileUpload # Necessário para upload de mídia

# --- Importações Adicionais Necessárias para a Criação de Conteúdo/Vídeo ---
# Para gerar áudio a partir de texto
from gtts import gTTS
# Para processamento e edição de vídeo com MoviePy
# Importe as classes específicas que você vai usar para o seu vídeo.
# Classes comuns: AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx
from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip, VideoFileClip, vfx

# Pode precisar de Pillow para TextClip/ImageClip
# Certifique-se de ter 'Pillow' no seu requirements.txt
from PIL import Image # Importar Pillow/PIL


# Configurar logging para enviar output para o console do GitHub Actions
# Use level=logging.INFO para ver as mensagens informativas sobre o progresso.
# Descomente a linha abaixo para DEBUG mais detalhado (mostrará mensagens debug)
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')


# Escopos necessários para acessar a API do YouTube (upload)
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado
# Esta função lida com a carga do token.json e refresh automático.
# Espera os caminhos para os arquivos JSON *já decodificados* criados pelo workflow
def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None # Inicializa credenciais como None

    # 1. Tenta carregar credenciais do token.json existente (decodificado pelo workflow)
    # Este arquivo foi decodificado pelo workflow a partir de canal1_token.json.base64
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path} usando from_authorized_user_file...")
            # Use from_authorized_user_file para carregar credenciais do token.json
            # Esta função lida automaticamente com a estrutura do token.json
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            # Logar aviso se o arquivo token.json estiver inválido/corrompido (como o erro 0xf3, AGORA RESOLVIDO!)
            # Ou outros erros de parsing.
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True) # Logar traceback para entender o erro de parsing
            creds = None # Garantir que creds seja None se a carga falhar
    else:
         logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")
         # Se token.json não existe, creds permanece None. O próximo bloco lida com isso.


    # 2. Se as credenciais foram carregadas mas estão expiradas, tenta refreshar
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
             # Tenta usar o refresh token para obter um novo access token. Esta chamada é NÃO INTERATIVA.
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
             # Este erro não deveria acontecer se o workflow criou client_secrets.json
             logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para refresh do token.", exc_info=True)
             creds = None # Falha crítica
        except Exception as e:
            # Captura erros durante o processo de refresh
            logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
            creds = None # A atualização falhou, credenciais não são válidas

    elif creds and not creds.refresh_token:
        logging.error("ERRO: Credenciais existentes expiradas, mas SEM refresh token disponível em token.json. Não é possível re-autorizar automaticamente.")
        return None

    else:
         # Caso onde token.json não existe, estava vazio/corrompido, ou não continha refresh token válido.
         logging.warning("Não foi possível carregar credenciais de token.json E não há refresh token disponível ou válido.")
         logging.error("--- Falha crítica: Necessário executar a autenticação inicial LOCALMENTE (com generate_token.py) para criar/atualizar um token.json válido com refresh token,")
         logging.error("e garantir que o arquivo canal1_token.json.base64 no repositório (ou Secret TOKEN_BASE64) contenha este token codificado CORRETAMENTE.")
         return None # Indica falha crítica na autenticação


    # 3. Verifica se ao final do processo temos credenciais válidas
    if not creds or not creds.valid:
         # Este log é atingido se todas as tentativas falharam
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
                                    align='center',
                                    stroke_color='black',
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
        # Ou concatenate_videoclips se você tiver clipes que vêm um depois do outro
        final_video_clip = CompositeVideoClip(clips, size=(W, H)) # Combina o fundo e os textos sobrepostos


        # Define o áudio do vídeo final como o áudio gerado anteriormente
        final_video_clip = final_video_clip.set_audio(audio_clip)

        # Garante que a duração do vídeo final corresponda à duração do áudio
        final_video_clip = final_video_clip.set_duration(total_duration)


        # --- <<<<< FIM DO SEU CÓDIGO DE CRIAÇÃO/EDIÇÃO DE VÍDEO COM MOVIEPY >>>>> ---
        # Lembre-se de adicionar LOGS BASTANTE DETALHADOS DENTRO DESTE PROCESSO!
        # Ex: logging.info("MoviePy: Carregando clip de áudio...")
        # Ex: logging.info("MoviePy: Sincronizando clipes...")
        # Ex: logging.info(f"MoviePy: Criando TextClip para o fato '{fact[:20]}...'")
        # Ex: logging.info("MoviePy: Iniciando a escrita do arquivo de vídeo (renderização)...")
        # Ex: logging.info(f"MoviePy: Renderizando quadro {i}/{total_quadros}...") # Se puder adicionar um loop de progresso


        # Salva o vídeo final em um arquivo
        # Use um nome de arquivo único, talvez baseado no timestamp, e em uma pasta de saída
        timestamp = int(time.time()) # Timestamp atual para nome único
        output_video_dir = "generated_videos"
        os.makedirs(output_video_dir, exist_ok=True) # Cria la carpeta si no existe
        video_output_filename = f"{channel_title.replace(' ', '_').lower()}_{timestamp}_final.mp4"
        video_output_path = os.path.join(output_video_dir, video_output_filename)


        logging.info(f"Escrevendo o arquivo de vídeo final para: {video_output_path}. Isso pode levar tempo...")
        # Use um logger de progresso se moviepy.write_videofile suportar e você configurar
        final_video_clip.write_videofile(video_output_path,
                                         codec='libx264', # Codec de vídeo comum e recomendado para MP4
                                         audio_codec='aac', # Codec de áudio comum e recomendado
                                         fps=FPS, # Quadros por segundo definidos antes
                                         threads=4 # Pode ajustar o número de threads para renderização
                                         # logger='bar' # Descomente se quiser ver uma barra de progresso no log no terminal
                                        )
        logging.info("Arquivo de vídeo final escrito.")

        return video_output_path # Retorna o caminho do arquivo de vídeo final

    except Exception as e:
        # Captura erros durante a criação do vídeo (MoviePy, etc.)
        logging.error(f"ERRO durante a criação do vídeo com MoviePy: {e}", exc_info=True)
        return None

# --- FUNÇÃO DE UPLOAD ---
# Esta função recebe o caminho do arquivo de vídeo e faz o upload para o YouTube
# Adaptação baseada no seu script upload_youtube.py
def upload_video(youtube_service, video_path, title, description, tags, category_id, privacy_status):
    logging.info(f"--- Iniciando etapa: Upload do vídeo para o YouTube ---")
    try:
        # Verifica se o arquivo de vídeo final foi realmente criado e tem conteúdo (tamanho > 0)
        if not os.path.exists(video_path) or not os.path.getsize(video_path) > 0:
             logging.error(f"ERRO: Arquivo de vídeo final para upload NÃO encontrado ou está vazio em: {video_path}")
             return None # Retorna None em caso de erro

        logging.info(f"Preparando upload do arquivo: {video_path}")
        # Define os metadados do vídeo (título, descrição, tags, categoria, status de privacidade)
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

        # Cria o objeto MediaFileUpload para upload resumível
        # O upload resumível é recomendado para arquivos maiores ou conexões instáveis
        media_body = MediaFileUpload(video_path, resumable=True)

        logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
        # Usa o método insert() da API videos().
        # Define o 'part' como 'snippet,status' para incluir os metadados e o status de privacidade.
        insert_request = youtube_service.videos().insert(
            part=','.join(body.keys()), # Partes da requisição (snippet, status)
            body=body, # Corpo da requisição com metadados do vídeo
            media_body=media_body # Corpo da mídia (o arquivo de vídeo)
        )

        # Execute a requisição de upload. Isso fará o upload real.
        # Este passo pode levar bastante tempo dependendo do tamanho do vídeo e conexão do runner.
        logging.info("Executando requisição de upload. Isso pode levar tempo...")
        # O Google API client suporta upload resumível automaticamente com MediaFileUpload(..., resumable=True).
        # A chamada execute() gerencia os chunks e o progresso por baixo dos panos.
        # Se você precisar de um watcher de progresso explícito, a documentação da biblioteca mostra como usar um MediaUploadProgress.
        response_upload = insert_request.execute() # Executa a requisição HTTP real
        logging.info("Requisição de upload executada.")

        # Verifica a resposta do upload
        video_id = response_upload.get('id')
        if video_id:
            logging.info(f"Upload completo. Vídeo ID: {video_id}")
            # Construa o link correto do YouTube
            logging.info(f"Link do vídeo (pode não estar ativo imediatamente se for privado): https://www.youtube.com/watch?v={video_id}")
            return video_id # Retorna o ID do vídeo se o upload for bem-sucedido
        else:
             logging.error("ERRO: Requisição de upload executada, mas a resposta não contém um ID de vídeo.", exc_info=True)
             return None # Retorna None em caso de falha no upload


    except FileNotFoundError:
        # Captura o erro se o arquivo de vídeo não for encontrado para a MediaFileUpload
        logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_path} para upload.", exc_info=True)
        return None
    except Exception as e:
        # Captura outros erros durante o processo de upload
        logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
        return None

    # Note: A mensagem de sucesso final do upload já está dentro do try/except acima.
    # Não precisamos de outra aqui a menos que haja lógica adicional pós-upload.


# Função principal do script
# Esta função coordena as etapas da automação para um canal específico
def main(channel_name):
    logging.info(f"--- Início do script de automação para o canal: {channel_name} ---")

    # Define os caminhos esperados para os arquivos JSON decodificados pelo workflow
    # Estes arquivos SÃO criados pelo step de decodificação no main.yml
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    config_path = os.path.join(base_dir, 'config', 'channels_config.json') # Caminho para o arquivo de configuração


    # --- Carregar Configuração do Canal ---
    logging.info(f"Carregando configuração do canal de {config_path}...")
    channel_config = None
    try:
        # Garante leitura em UTF-8, crucial para arquivos de configuração
        with open(config_path, 'r', encoding='utf-8') as f:
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


    # Define caminhos para credenciais com base na configuração do canal carregada
    # Estes são os nomes dos arquivos .base64 NO REPOSITÓRIO.
    client_secrets_base64_filename = channel_config.get('client_secret_file')
    token_base64_filename = channel_config.get('token_file')

    # Verifica se os nomes dos arquivos de credenciais foram encontrados na configuração
    if not client_secrets_base64_filename:
        logging.error(f"ERRO CRÍTICO: 'client_secret_file' não especificado para o canal '{channel_name}' em {config_path}.")
        sys.exit(1)
    if not token_base64_filename:
        logging.error(f"ERRO CRÍTICO: 'token_file' não especificado para o canal '{channel_name}' em {config_path}.")
        sys.exit(1)

    # Define os caminhos completos esperados para os arquivos JSON *decodificados*
    # que são criados na pasta credentials/ pelo workflow.
    client_secrets_path = os.path.join(credentials_dir, 'client_secret.json') # Assume que o workflow sempre decodifica para este nome
    token_path = os.path.join(credentials_dir, 'token.json') # Assume que o workflow sempre decodifica para este nome


    # Adiciona verificações para garantir que os arquivos JSON decodificados existem APÓS o step de decodificação do workflow
    logging.info("Verificando arquivos de credenciais decodificados (client_secret.json e token.json) criados pelo workflow...")
    if not os.path.exists(client_secrets_path):
         logging.error(f"ERRO CRÍTICO: Arquivo client_secret.json NÃO encontrado em {client_secrets_path}. Verifique o step 'Decodificar arquivos .base64 do Repositório' no main.yml e o arquivo de entrada {client_secrets_base64_filename} no repositório.")
         sys.exit(1)
    if not os.path.exists(token_path):
        logging.error(f"ERRO CRÍTICO: Arquivo token.json NÃO encontrado em {token_path}. Verifique o step 'Decodificar arquivos .base64 do Repositório' no main.yml e o arquivo de entrada {token_base64_filename} no repositório.")
        sys.exit(1)

    logging.info("Arquivos de credenciais decodificados encontrados em credentials/.")


    # Obtém o serviço do YouTube autenticado passando os caminhos dos arquivos JSON decodificados
    logging.info("Chamando get_authenticated_service() para autenticar com token.json e client_secrets.json...")
    youtube = get_authenticated_service(client_secrets_path, token_path)
    logging.info("Chamada a get_authenticated_service() concluída.")

    # Verifica se a autenticação foi bem-sucedida (se get_authenticated_service retornou um objeto build)
    if youtube is None:
        logging.error("Falha final na autenticação do serviço YouTube. Saindo do script.")
        sys.exit(1)

    logging.info("Serviço do YouTube autenticado com sucesso e pronto para uso da API.")

    # --- INÍCIO DA SEGUNDA PARTE: CRIAÇÃO DE CONTEÚDO E VÍDEO ---
    # Este bloco agora contém as chamadas para as novas funções de criação/upload

    try:
        logging.info("--- Iniciando etapa: CRIAÇÃO DE CONTEÚDO, VÍDEO E UPLOAD ---")

        # --- Seu código existente para interagir com a API (buscar canal, uploads, playlists) ---
        # Este código estava no seu main() original. Mantive os logs e a estrutura.
        logging.info("Iniciando operações iniciais da API do YouTube (buscar canal, uploads, etc.)...")

        logging.info("Buscando informações do canal (mine=True)...")
        request_channel = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        logging.info("Chamando youtube.channels().list().execute()...")
        response_channel = request_channel.execute()
        logging.info("youtube.channels().list().execute() concluído.")
        # logging.info(f"Informações do canal: {response_channel}") # Descomente para debug detalhado da resposta


        if not ('items' in response_channel and response_channel['items']):
             logging.error("ERRO: Não foi possível obter informações do seu canal (mine=True). Verifique as permissões das credenciais.")
             sys.exit(1)


        logging.info("Buscando ID da playlist de uploads...")
        uploads_playlist_id = response_channel['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        logging.info(f"ID da playlist de uploads encontrado: {uploads_playlist_id}")

        logging.info("Buscando uploads da playlist...")
        request_uploads = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id
        )
        logging.info("Chamando youtube.playlistItems().list().execute()...")
        response_uploads = request_uploads.execute()
        logging.info("youtube.playlistItems().list().execute() concluído.")
        # logging.info(f"Uploads do canal: {response_uploads}") # Descomente para debug detalhado

        if 'items' in response_uploads and response_uploads['items']:
            logging.info(f"Encontrados {len(response_uploads['items'])} vídeos na playlist de uploads.")
            for i, item in enumerate(response_uploads['items']):
                video_id = item['contentDetails']['videoId']
                video_title = item['snippet']['title']
                logging.info(f"Processando vídeo {i+1}: ID={video_id}, Título='{video_title}'")
        else:
             logging.info("Nenhum vídeo encontrado na playlist de uploads.")


        logging.info("Buscando playlists do canal (mine=True)...")
        request_playlists = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True
        )
        logging.info("Chamando youtube.playlists().list().execute()...")
        response_playlists = request_playlists.execute()
        logging.info("youtube.playlists().list().execute() concluído.")
        # logging.info(f'Playlists do canal: {response_playlists}') # Descomente para debug detalhado

        logging.info("--- Etapa de operações iniciais da API concluída. ---")

        # --- CRIAÇÃO DE CONTEÚDO (texto, áudio, visuais) ---

        logging.info("--- Iniciando etapa: Criação de conteúdo (texto, áudio, visuais) ---")

        # 1. Obter fatos/texto (chama a função que você implementará)
        logging.info("Obtendo fatos para o vídeo...")
        # Obtém as keywords da configuração do canal
        keywords = channel_config.get('keywords', '').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        if not keywords:
             logging.warning("Nenhuma keyword encontrada na configuração do canal. Considere adicionar keywords no channels_config.json.")
        # Chama a função placeholder (adicione sua lógica real DENTRO dela)
        # Retorna uma lista de strings (os fatos)
        facts = get_facts_for_video(keywords) # <<< Sua lógica real para obter fatos em INGLÊS

        if not facts:
             logging.error("ERRO: Não foi possível gerar fatos para o vídeo. Saindo.")
             sys.exit(1)
        logging.info(f"Fatos obtidos: {facts}")

        # 2. Gerar áudio a partir dos fatos em inglês
        logging.info("Gerando áudio a partir dos fatos...")
        audio_text = ".\n".join(facts) + "." # Combina fatos em um texto para narração
        # Chama a função generate_audio_from_text (já implementada acima)
        # Salva o áudio em temp_audio/{nomedocanal}_audio_{timestamp}.mp3
        audio_path = generate_audio_from_text(audio_text, lang='en', output_filename=f"{channel_name}_audio_{int(time.time())}.mp3")

        if not audio_path:
             logging.error("ERRO: Falha ao gerar o arquivo de áudio. Saindo.")
             sys.exit(1)
        logging.info(f"Arquivo de áudio gerado: {audio_path}")

        # 3. Preparar visuais (Este é um placeholder importante - você precisa baixar ou gerar imagens/vídeos)
        logging.info("Preparando visuais para o vídeo (imagens/clipes)...")
        # >>>>> SEU CÓDIGO PARA PREPARAR VISUAIS VEM AQUI <<<<<
        # Implemente sua lógica para baixar, gerar ou selecionar imagens/vídeos
        # que serão usados na edição do vídeo, talvez baseados nos fatos ou keywords.
        # Você precisará dos caminhos desses arquivos para a função create_video_from_content.
        # Exemplo:
        # image_paths = download_images_related_to_facts(facts) # Sua função para baixar imagens
        # video_clip_paths = get_stock_footage(keywords) # Sua função para obter clipes de vídeo
        logging.info("Preparação de visuais concluída (assumindo lógica implementada).")


        logging.info("--- Etapa concluída: Criação de conteúdo (texto, áudio, visuais) ---")


        # --- PROCESSAMENTO / EDIÇÃO DE VÍDEO ---

        logging.info("--- Iniciando etapa: Processamento / Edição de vídeo ---")

        # 4. Criar o vídeo a partir do áudio e visuais usando MoviePy
        # Chama a função que você implementará (create_video_from_content)
        # Adapte a chamada conforme sua implementação de create_video_from_content
        # A função create_video_from_content (exemplo simples) está incluída acima.
        logging.info("Chamando função para criar o vídeo final com MoviePy...")
        # Passe os fatos, o áudio e os caminhos dos visuais (imagens/clipes) para esta função.
        # Exemplo: video_output_path = create_video_from_content(facts, audio_path, image_paths, video_clip_paths, channel_title=channel_config.get('title', 'Video'))
        video_output_path = create_video_from_content(facts, audio_path, channel_title=channel_config.get('title', 'Video')) # <<< Sua lógica MoviePy dentro desta função

        if not video_output_path or not os.path.exists(video_output_path) or os.path.getsize(video_output_path) == 0:
             logging.error("ERRO: Falha ao criar o arquivo de vídeo final ou o arquivo está vazio. Saindo.")
             sys.exit(1) # Sai se o arquivo de vídeo não foi criado ou está vazio
        logging.info(f"Arquivo de vídeo final criado: {video_output_path}")

        # 5. Gerar legendas (Opcional e Mais Avançado) - Se quiser isso agora, precisa implementar.
        # logging.info("Iniciando geração de legendas (Opcional)...")
        # >>>>> SEU CÓDIGO PARA GERAR LEGENDAS VEM AQUI (OPCIONAL) <<<<<
        # Use uma API de Speech-to-Text (como Google Cloud Speech-to-Text)
        # no arquivo de áudio gerado, e sincronizar o texto com o tempo.
        # Ex: legenda_path = generate_subtitles(audio_path, lang='en')
        # if legenda_path and os.path.exists(legenda_path):
        #      logging.info(f"Arquivo de legendas gerado: {legenda_path}")
        # else:
        #      logging.warning("Geração de legendas falhou ou não foi implementada.")
        # <<<<< FIM DO SEU CÓDIGO PARA GERAR LEGENDAS >>>>>
        # logging.info("Geração de legendas concluída (Opcional).")


        logging.info("--- Etapa concluída: Processamento / Edição de vídeo ---")


        # --- UPLOAD PARA O YOUTUBE ---

        # 6. Fazer o upload do vídeo para o YouTube
        logging.info("--- Iniciando etapa: Upload do vídeo para o YouTube ---")
        # Adapte os metadados do upload conforme a configuração do canal e o conteúdo do vídeo
        video_title = f"{channel_config.get('title', 'New Video')} - Daily Fact #{int(time.time())}" # Exemplo de título dinâmico com timestamp
        video_description = channel_config.get('description', 'An interesting video.')
        video_tags = keywords
        category_id = '28' # Ex: Ciência e Tecnologia. Adapte. Lista de IDs: https://developers.google.com/youtube/v3/docs/videos#snippet.categoryId
        privacy_status = 'private' # private, unlisted, ou public. Comece com 'private' para testar!

        # Chama a função de upload (já implementada acima)
        logging.info("Chamando função de upload...")
        uploaded_video_id = upload_video(youtube, video_output_path, video_title, video_description, video_tags, category_id, privacy_status)

        if not uploaded_video_id:
             # A mensagem de erro específica já foi logada dentro de upload_video
             logging.error("O upload do vídeo falhou.")
             sys.exit(1) # Sai com erro se o upload falhou
        logging.info(f"Vídeo enviado com sucesso! ID: {uploaded_video_id}")

        # 7. Adicionar legendas ao vídeo (Opcional e Mais Avançado)
        # Se você gerou um arquivo de legendas no passo 5 e o upload foi bem-sucedido, pode adicioná-lo aqui.
        # if uploaded_video_id and 'legenda_path' in locals() and legenda_path and os.path.exists(legenda_path):
        #     logging.info(f"Adicionando legendas {legenda_path} ao vídeo {uploaded_video_id}...")
        #     >>> SEU CÓDIGO PARA ADICIONAR LEGENDAS VIA API VEM AQUI (OPCIONAL) <<<
        #     Isso envolve usar o método captions().insert() da API do YouTube Data API v3.
        #     logging.info("Adição de legendas concluída (Opcional).")


        logging.info("--- Etapa concluída: Upload do vídeo para o YouTube ---")


        # --- FIM DA SEGUNDA PARTE (CRIAÇÃO/UPLOAD) ---


    except Exception as e:
        # Este bloco captura erros inesperados que ocorram em qualquer lugar
        # dentro do bloco try principal, após a autenticação.
        logging.error(f"ERRO INESPERADO durante a execução da automação: {e}", exc_info=True)
        sys.exit(1)


    logging.info("--- Script de automação finalizado com sucesso ---")


# Configuração do parser de argumentos (manter)
# Esta função coordena as etapas da automação para um canal específico
if __name__ == "__main__":
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel é passado pelo main.yml com o nome do canal (ex: "fizzquirk")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado (conforme channels_config.json).")
    args = parser.parse_args()
    # Chama a função main passando o nome do canal
    main(args.channel)
