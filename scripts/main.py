import os
import argparse
import logging
import json
# from googleapiclient.discovery import build # Já importado abaixo
from google_auth_oauthlib.flow import InstalledAppFlow # Ainda necessário para carregar client_secrets para refresh
from google.auth.transport.requests import Request
# import pickle # Não é estritamente necessário se usar token.json diretamente
from google.oauth2.credentials import Credentials # Importar a classe Credentials
import sys # Para sair do script em caso de erro crítico
from googleapiclient.discovery import build # Importar build aqui

# Configurar logging para enviar output para o console do Actions
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# Escopos necessários
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado
# Agora espera os caminhos para os arquivos JSON decodificados
def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None

    # 1. Tenta carregar credenciais do token.json existente
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path}...")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            # Logar aviso se o arquivo token.json estiver inválido/corrompido
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}")
            creds = None # Garantir que creds seja None se a carga falhar
    else:
         logging.warning(f"Arquivo token.json não encontrado em {token_path}. Necessário para autenticação automática.")


    # 2. Se não houver credenciais válidas, tenta atualizar usando o refresh token (se existir)
    if not creds or not creds.valid:
        logging.info("Credenciais não válidas ou não encontradas. Tentando atualizar com refresh token...")

        if creds and creds.expired and creds.refresh_token:
            logging.info("Credenciais expiradas, tentando atualizar usando refresh token existente.")
            try:
                 # A função refresh() nas credenciais carregadas já usa o client_id, client_secret, etc.
                 # que vieram do token.json (que por sua vez veio do client_secret original).
                 creds.refresh(Request())
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

            except Exception as e:
                logging.error(f"ERRO: Falha ao atualizar token de acesso com refresh token: {e}", exc_info=True)
                creds = None # A atualização falhou, credenciais não são válidas

        elif creds and not creds.refresh_token:
            logging.error("ERRO: Credenciais existentes expiradas, mas SEM refresh token disponível. Não é possível re-autorizar automaticamente.")
            # Neste ponto, no ambiente headless, não há como prosseguir.
            return None # Indica falha crítica

        else:
             logging.warning("Não foi possível carregar credenciais e nem tentar refresh (pode ser a primeira execução ou falta do arquivo token.json).")
             # No ambiente headless, se token.json não existe e não tem refresh token, não há como autenticar.
             # Em um fluxo de automação, o token.json DEVE existir e ser válido (obtido via run_local_server inicial).
             logging.error("ERRO: Necessário executar a autenticação inicial localmente com generate_token.py para criar o token.json válido.")
             return None # Indica falha crítica


    # 3. Verifica se ao final do processo temos credenciais válidas
    if not creds or not creds.valid:
         logging.error("--- Falha crítica ao obter credenciais válidas após todas as tentativas. Saindo. ---")
         return None # Indica falha total na autenticação


    logging.info("--- Autenticação bem-sucedida. Construindo serviço da API do YouTube. ---")
    # Constrói o serviço da API do YouTube com as credenciais obtidas
    return build('youtube', 'v3', credentials=creds)

# Função principal do script
def main(channel):
    logging.info(f"--- Início do script de automação para o canal: {channel} ---")

    # Define os caminhos esperados para os arquivos JSON decodificados pelo workflow
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    client_secrets_path = os.path.join(credentials_dir, 'client_secret.json')
    token_path = os.path.join(credentials_dir, 'token.json') # Caminho para o token.json decodificado

    # Adiciona verificações para garantir que os arquivos JSON decodificados existem
    logging.info("Verificando arquivos de credenciais decodificados...")
    if not os.path.exists(client_secrets_path):
         logging.error(f"ERRO CRÍTICO: Arquivo client_secret.json NÃO encontrado em {client_secrets_path}. Verifique o step de decodificação no main.yml e o arquivo de entrada canal1_client_secret.json.base64.")
         sys.exit(1)
    if not os.path.exists(token_path):
         logging.error(f"ERRO CRÍTICO: Arquivo token.json NÃO encontrado em {token_path}. Verifique o step de decodificação no main.yml e o arquivo de entrada canal1_token.json.base64.")
         # No fluxo de automação agendada, o token.json deve existir e ser válido.
         # Se ele não existe aqui, é um erro crítico.
         sys.exit(1)
    logging.info("Arquivos de credenciais decodificados encontrados.")


    # Obtém o serviço do YouTube autenticado passando os caminhos dos arquivos decodificados
    youtube = get_authenticated_service(client_secrets_path, token_path)

    # Verifica se a autenticação foi bem-sucedida
    if youtube is None:
        logging.error("Falha na autenticação do serviço YouTube. Saindo do script.")
        sys.exit(1) # Sai se get_authenticated_service retornou None

    logging.info("Serviço do YouTube autenticado com sucesso e pronto para uso da API.")

    # --- ADICIONE SEUS PASSOS DE AUTOMAÇÃO PRINCIPAL AQUI E COLOQUE LOGS DETALHADOS ---
    # O código abaixo é o que estava no seu main() original após a autenticação.
    # Mova seus outros processos (criação de vídeo, upload) para DENTRO deste try...except.

    try:
        logging.info("--- Iniciando operações da API do YouTube (buscar canal, uploads, etc.) ---")

        logging.info("Buscando informações do canal (mine=True)...")
        request_channel = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        # Adicione log ANTES de cada chamada .execute() pois elas fazem a requisição de rede real
        logging.info("Chamando youtube.channels().list().execute()...")
        response_channel = request_channel.execute()
        logging.info("youtube.channels().list().execute() concluído.")
        # logging.info(f"Informações do canal: {response_channel}") # Descomente para debug detalhado da resposta


        if not ('items' in response_channel and response_channel['items']):
             logging.error("ERRO: Não foi possível obter informações do seu canal (mine=True). Verifique as permissões das credenciais.")
             sys.exit(1) # Saia se não encontrar seu próprio canal


        logging.info("Buscando ID da playlist de uploads...")
        # Adicione verificações se as chaves existem na resposta
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

        # Exemplo de como iterar pelos vídeos enviados - Adicione logs aqui
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


        # --- SEU CÓDIGO PARA CRIAR VÍDEO E FAZER UPLOAD VEM AQUI ---
        # ADICIONE LOGS BASTANTE DETALHADOS NESTA SEÇÃO!

        logging.info("--- Iniciando etapa: Criação de conteúdo (texto, áudio, imagens) ---")
        # Coloque seu código para criar o conteúdo aqui
        # Ex: gerar_texto()
        # Ex: gerar_audio(texto)
        # Ex: baixar_imagens()
        logging.info("--- Etapa concluída: Criação de conteúdo ---")

        logging.info("--- Iniciando etapa: Processamento / Edição de vídeo (com MoviePy, etc.) ---")
        # Coloque seu código para usar MoviePy ou outra biblioteca aqui
        # Ex: video_final_path = criar_video_final(audio_path, imagem_paths, duracao)
        # !!! ADICIONE LOGS DENTRO DESTE PROCESSO. É UM LUGAR COMUM PARA TRAVAR !!!
        # Ex: logging.info("MoviePy: Carregando clip de áudio...")
        # Ex: logging.info("MoviePy: Adicionando imagem X ao vídeo...")
        # Ex: logging.info("MoviePy: Iniciando renderização final...")
        # Ex: logging.info("MoviePy: Renderização X% completa...") # Se sua lib tiver progresso
        logging.info("--- Etapa concluída: Processamento / Edição de vídeo ---")


        logging.info("--- Iniciando etapa: Upload do vídeo para o YouTube ---")
        video_file_path = "caminho/para/seu/video.mp4" # <--- SUBSTITUA PELO CAMINHO REAL DO SEU VÍDEO FINAL
        video_title = "Título do Seu Vídeo" # <--- SUBSTITUA PELO TÍTULO REAL
        video_description = "Descrição do Seu Vídeo" # <--- SUBSTITUA PELA DESCRIÇÃO REAL
        video_tags = ["tag1", "tag2"] # <--- SUBSTITUA PELAS TAGS REAIS

        # Exemplo de como chamar a API de upload (adapte conforme sua implementação)
        # Certifique-se de que sua função de upload lida com o corpo da requisição (snippet, status)
        # e o media body (o arquivo de vídeo em si).
        try:
            # Ex: request_upload = youtube.videos().insert(...)
            # Ex: response_upload = request_upload.execute()
            logging.info(f"Chamando API de upload para {video_file_path} com título '{video_title}'...")

            # --- SEU CÓDIGO REAL DE UPLOAD VAI AQUI ---
            # Se usar google-api-python-client, a estrutura será algo como:
            # body= {
            #     'snippet': {
            #         'title': video_title,
            #         'description': video_description,
            #         'tags': video_tags,
            #         'categoryId': '28' # Exemplo: Categoria Ciência e Tecnologia
            #     },
            #     'status': {
            #         'privacyStatus': 'private' # ou 'public', 'unlisted'
            #     }
            # }
            # media_body = MediaFileUpload(video_file_path, resumable=True)
            # insert_request = youtube.videos().insert(
            #     part=','.join(body.keys()),
            #     body=body,
            #     media_body=media_body
            # )
            # response_upload = insert_request.execute()
            # logging.info(f"Upload completo. ID do vídeo: {response_upload.get('id')}")
            # ---------------------------------------

            logging.info("--- Etapa concluída: Upload do vídeo para o YouTube ---")


        except FileNotFoundError:
            logging.error(f"ERRO: Arquivo de vídeo final não encontrado em {video_file_path} para upload.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
            sys.exit(1)


        # --- FIM DOS SEUS PASSOS DE AUTOMAÇÃO ---


    except Exception as e:
        # Captura erros inesperados que possam ocorrer em outras partes do script principal
        # após a autenticação inicial.
        logging.error(f"ERRO INESPERADO no script principal (fora das etapas conhecidas): {e}", exc_info=True) # Imprime o traceback
        sys.exit(1) # Garante que o workflow falhe

    logging.info("--- Script de automação finalizado com sucesso ---")


# Configuração do parser de argumentos (manter)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel "fizzquirk" é passado pelo main.yml
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    args = parser.parse_args()
    main(args.channel)
