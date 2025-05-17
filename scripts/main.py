import os
import argparse
import logging
import json
import sys
import time # Importar módulo time, útil para nomes de arquivo únicos
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow # Necessário para carregar client_secrets
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials # Necessário para carregar de token.json
from googleapiclient.http import MediaFileUpload # Necessário para upload de mídia

# --- Importações Adicionais Necessárias para a Criação de Conteúdo/Vídeo ---
# Para gerar áudio a partir de texto
from gtts import gTTS
# Para processamento e edição de vídeo
# Importe as classes específicas que você vai usar do MoviePy
# Exemplo de classes comuns: AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip, vfx, VideoFileClip

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

# Função para obter o serviço autenticado (manter a versão corrigida)
# Esta função lida com a carga do token.json e refresh automático.
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
# Este é um exemplo BEM simples (texto na tela preta) que você deve adaptar.
# Você precisará de lógica mais complexa para visuais, sincronização detalhada, etc.
# Recebe a lista de fatos, caminho do áudio e o título do canal
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
        # Se precisar de imagens/clipes, certifique-se de que foram baixados/gerenciados antes desta função.

        # Exemplo BÁSICO:
        W, H = 1920, 1080 # Resolução Exemplo: Full HD
        FPS = 24 # Quadros por segundo Exemplo: 24 FPS

        # Cria um clipe de fundo (cor sólida, ou carregue uma imagem/vídeo base aqui)
        background_clip = ColorClip((W, H), color=(0, 0, 0), duration=total_duration) # Fundo preto


        # Exemplo de como adicionar texto. Você provavelmente vai querer que os fatos apareçam um por um,
        # sincronizados com o áudio. Isso é mais complexo e requer dividir o áudio ou a lógica de narração.
        # Este exemplo simplesmente junta todos os fatos em um TextClip longo que aparece por toda a duração.

        # Combinar fatos para um TextClip simples (adapte se quiser fatos individuais)
        combined_facts_text = "\n\n".join(facts) # Junta fatos com 2 quebras de linha

        # Cria o TextClip com o texto combinado
        # Adapte fonte, tamanho da fonte (fontsize), cor (color), alinhamento (align), etc.
        # certifique-se de que a fonte usada está disponível no ambiente do GitHub Actions ou a inclua.
        text_clip = TextClip(combined_facts_text,
                             fontsize=40,
                             color='white',
                             bg_color='transparent', # Fundo transparente para sobrepor o background_clip
                             size=(W*0.9, H*0.8), # Tamanho da caixa de texto (90% da largura, 80% da altura)
                             method='caption', # Tenta ajustar quebras de linha automaticamente
                             align='center', # Alinha o texto ao centro
                             stroke_color='black', # Exemplo de contorno
                             stroke_width=1, # Exemplo de largura do contorno
                             kerning=0) # Ajuste de espaçamento entre caracteres se necessário


        # Define a duração e posição do TextClip
        text_clip = text_clip.set_duration(total_duration).set_position('center') # Duração total, centralizado

        # Combina o clipe de fundo e o TextClip. A ordem importa (fundo primeiro).
        # Se você tiver múltiplos clipes de vídeo, use concatenate_videoclip
