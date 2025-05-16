import os
import argparse
import logging
import json
# Não precisamos mais decodificar base64 DENTRO deste script, o workflow faz isso.
# import base64
from googleapiclient.discovery import build
# InstalledAppFlow ainda é útil para carregar o client_secrets para o processo de refresh, mas NÃO para run_local_server.
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# Não precisamos mais de pickle se estivermos usando token.json diretamente.
# import pickle
from google.oauth2.credentials import Credentials # Importar a classe Credentials para carregar de token.json
import sys # Para sair do script em caso de erro crítico
# Importar a classe para upload de mídia (necessário para o upload)
from googleapiclient.http import MediaFileUpload


# Configurar logging para enviar output para o console do Actions
# Use level=logging.INFO para ver as mensagens informativas que adicionarmos
# stream=sys.stdout força a saída imediata para o console, útil para debug.
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

# Escopos necessários para acessar a API do YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Função para obter o serviço autenticado
# Agora espera os caminhos para os arquivos JSON *já decodificados* criados pelo workflow
def get_authenticated_service(client_secrets_path, token_path):
    logging.info("--- Tentando obter serviço autenticado ---")
    creds = None # Inicializa credenciais como None

    # 1. Tenta carregar credenciais do token.json existente
    # Este arquivo foi decodificado pelo workflow a partir de canal1_token.json.base64
    if os.path.exists(token_path):
        try:
            logging.info(f"Tentando carregar credenciais de {token_path}...")
            # Carrega as credenciais diretamente do arquivo token.json usando a biblioteca google-auth
            # O erro 'utf-8' codec... 0xf3 acontece AQUI.
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Credenciais carregadas com sucesso de token.json.")
        except Exception as e:
            # Logar aviso se o arquivo token.json estiver inválido/corrompido (como o erro 0xf3)
            logging.warning(f"Não foi possível carregar credenciais de {token_path}: {e}", exc_info=True) # Logar traceback para entender o erro de parsing
            creds = None # Garantir que creds seja None se a carga falhar
    else:
         logging.warning(f"Arquivo token.json NÃO encontrado em {token_path}.")
         # Se token.json não existe, creds permanece None. O próximo bloco lida com isso.


    # 2. Se não houver credenciais válidas (primeira carga falhou, expirou, etc.), tenta atualizar usando o refresh token
    #    Isso acontece se o access token expirou, ou se a carga inicial de token.json falhou mas continha info de refresh.
    #    NOTA: A biblioteca google-auth geralmente precisa do client_secrets para realizar o refresh.
    if not creds or not creds.valid:
        logging.info("Credenciais não válidas ou não encontradas. Tentando atualizar com refresh token (se disponível)...")

        # Verifica se há um refresh token para tentar usar
        # Se creds foi carregado parcialmente (e.g., arquivo token.json inválido), pode não ter refresh_token válido.
        # A melhor forma é tentar carregar o flow com client_secrets e ver se ele consegue usar o token_path para refresh.

        # Tenta usar InstalledAppFlow com os caminhos para client_secrets e token para gerenciar refresh
        if os.path.exists(client_secrets_path):
             try:
                 logging.info(f"Carregando Flow com client_secrets de {client_secrets_path} e token de {token_path}...")
                 # from_client_secrets_file com token=token_path tenta carregar e gerenciar o refresh
                 # É importante que o arquivo token.json contenha 'refresh_token', 'client_id', 'client_secret', etc.
                 flow = InstalledAppFlow.from_client_secrets_file(
                     client_secrets_path, SCOPES,
                     # Especifica o arquivo token.json como o local onde as credenciais autorizadas são armazenadas
                     token=token_path
                 )
                 logging.info("Flow carregado. Verificando e atualizando credenciais...")

                 # A linha abaixo tentará carregar de token_path, verificar validade e refreshar se necessário
                 # Como run_local_server foi removido, ele não tentará abrir um browser se o refresh falhar.
                 # Ele simplesmente não retornará credenciais válidas.
                 flow.run_console() # run_console() tenta carregar/refreshar sem servidor local
                 creds = flow.credentials # Pega as credenciais (atualizadas ou não) do flow

                 if creds and creds.valid:
                     logging.info("Credenciais validadas/atualizadas via flow.run_console().")
                     # Se o refresh ocorreu, o run_console já salva automaticamente o token atualizado em token_path.
                     # Não precisamos salvar manualmente aqui novamente.
                     logging.info(f"Arquivo {token_path} deve estar atualizado agora pelo flow.")
                 else:
                     logging.warning("Credenciais não válidas após tentativa com flow.run_console().")


             except FileNotFoundError:
                 # Este erro não deveria acontecer se o workflow criou client_secrets.json
                 logging.error(f"ERRO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Necessário para autenticação/refresh.", exc_info=True)
                 creds = None # Falha crítica
             except Exception as e:
                # Captura erros durante o processo de refresh via flow
                logging.error(f"ERRO: Falha durante a tentativa de autenticação/refresh via flow: {e}", exc_info=True)
                # O erro 'utf-8' codec 0xf3 PODE acontecer aqui também se o token.json lido pelo flow estiver corrompido.
                creds = None # A tentativa falhou, credenciais não são válidas

        else:
             # Este erro não deveria acontecer se o workflow criou client_secrets.json
             logging.error(f"ERRO CRÍTICO: Arquivo client_secrets.json NÃO encontrado em {client_secrets_path}. Autenticação impossível.", exc_info=True)
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


# Função principal do script
def main(channel):
    logging.info(f"--- Início do script de automação para o canal: {channel} ---")

    # Define os caminhos esperados para os arquivos JSON decodificados pelo workflow
    # Estes arquivos SÃO criados pelo step de decodificação no main.yml
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    client_secrets_path = os.path.join(credentials_dir, 'client_secret.json')
    token_path = os.path.join(credentials_dir, 'token.json') # Caminho para o token.json decodificado

    # Adiciona verificações para garantir que os arquivos JSON decodificados existem
    # Estas verificações devem passar se o step de decodificação no main.yml for bem-sucedido
    logging.info("Verificando arquivos de credenciais decodificados (client_secret.json e token.json) criados pelo workflow...")
    if not os.path.exists(client_secrets_path):
         logging.error(f"ERRO CRÍTICO: Arquivo client_secret.json NÃO encontrado em {client_secrets_path}. Verifique o step 'Decodificar arquivos .base64 do Repositório' no main.yml e o arquivo de entrada canal1_client_secret.json.base64.")
         sys.exit(1) # Sai se client_secret.json não foi criado
    # Verifica a existência de token.json. get_authenticated_service lida com o conteúdo inválido.
    if not os.path.exists(token_path):
        logging.error(f"ERRO CRÍTICO: Arquivo token.json NÃO encontrado em {token_path}. Verifique o step 'Decodificar arquivos .base64 do Repositório' no main.yml e o arquivo de entrada canal1_token.json.base64.")
        sys.exit(1) # Sai se token.json não foi criado

    logging.info("Arquivos de credenciais decodificados encontrados em credentials/.")


    # Obtém o serviço do YouTube autenticado passando os caminhos dos arquivos decodificados
    logging.info("Chamando get_authenticated_service() para autenticar com token.json e client_secret.json...")
    youtube = get_authenticated_service(client_secrets_path, token_path)
    logging.info("Chamada a get_authenticated_service() concluída.")

    # Verifica se a autenticação foi bem-sucedida (se get_authenticated_service retornou um objeto build)
    if youtube is None:
        # A mensagem de erro específica já foi logada dentro de get_authenticated_service
        logging.error("Falha final na autenticação do serviço YouTube. Saindo do script.")
        sys.exit(1) # Sai se get_authenticated_service retornou None

    logging.info("Serviço do YouTube autenticado com sucesso e pronto para uso da API.")

    # --- ADICIONE SEUS PASSOS DE AUTOMAÇÃO PRINCIPAL AQUI E COLOQUE LOGS DETALHADOS ---
    # Mova seus processos de criação de vídeo e upload para DENTRO deste bloco try...except.

    try:
        logging.info("--- Iniciando etapa: Operações iniciais da API do YouTube (buscar canal, uploads, etc.) ---")

        # --- Seu código existente para interagir com a API (buscar canal, uploads, playlists) ---
        # Ex: youtube.channels().list(...).execute()
        # Ex: youtube.playlistItems().list(...).execute()
        # Ex: youtube.playlists().list(...).execute()
        # ADICIONE LOGS ANTES DE CADA CHAMADA .execute()

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
        # >>>>> COLOQUE SEU CÓDIGO DE CRIAÇÃO DE CONTEÚDO AQUI <<<<<
        # Ex: gerar_texto()
        # Ex: gerar_audio(texto)
        # Ex: baixar_imagens()
        logging.info("--- Etapa concluída: Criação de conteúdo ---")

        logging.info("--- Iniciando etapa: Processamento / Edição de vídeo (com MoviePy, etc.) ---")
        # >>>>> COLOQUE SEU CÓDIGO DE PROCESSAMENTO/EDIÇÃO DE VÍDEO AQUI <<<<<
        # Ex: video_final_path = criar_video_final(audio_path, imagem_paths, duracao)
        # !!! ADICIONE LOGS DENTRO DESTE PROCESSO. É UM LUGAR COMUM PARA TRAVAR EM AMBIENTES HEADLESS !!!
        # Ex: logging.info("MoviePy: Carregando clip de áudio...")
        # Ex: logging.info("MoviePy: Adicionando imagem X ao vídeo...")
        # Ex: logging.info("MoviePy: Iniciando renderização final...")
        # Ex: logging.info("MoviePy: Renderização X% completa...") # Se sua lib tiver progresso
        logging.info("--- Etapa concluída: Processamento / Edição de vídeo ---")


        logging.info("--- Iniciando etapa: Upload do vídeo para o YouTube ---")
        # >>>>> COLOQUE SEU CÓDIGO DE UPLOAD AQUI <<<<<
        # Adapte as variáveis e a lógica de upload conforme seu script.
        video_file_path = "caminho/para/seu/video.mp4" # <--- SUBSTITUA PELO CAMINHO REAL DO SEU VÍDEO FINAL
        video_title = "Título do Seu Vídeo" # <--- SUBSTITUA PELO TÍTULO REAL
        video_description = "Descrição do Seu Vídeo" # <--- SUBSTITUA PELA DESCRIÇÃO REAL
        video_tags = ["tag1", "tag2"] # <--- SUBSTITUA PELAS TAGS REAIS
        category_id = '28' # <--- SUBSTITUA PELA ID DA CATEGORIA CORRETA (Ex: '28' para Ciência e Tecnologia)
        privacy_status = 'private' # <--- SUBSTITUA PARA 'public' ou 'unlisted' QUANDO ESTIVER PRONTO

        # Exemplo de como chamar a API de upload (adapte conforme sua implementação)
        # Certifique-se de que sua função de upload lida com o corpo da requisição (snippet, status)
        # e o media body (o arquivo de vídeo em si).
        try:
            logging.info(f"Preparando upload do arquivo: {video_file_path}")
            body= {
                'snippet': {
                    'title': video_title,
                    'description': video_description,
                    'tags': video_tags,
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy_status
                }
            }

            # Verifica se o arquivo de vídeo existe antes de tentar fazer upload
            if not os.path.exists(video_file_path):
                 logging.error(f"ERRO: Arquivo de vídeo para upload NÃO encontrado: {video_file_path}")
                 sys.exit(1) # Sai se o arquivo de vídeo não existe

            # Cria o objeto MediaFileUpload
            media_body = MediaFileUpload(video_file_path, resumable=True)

            logging.info("Chamando youtube.videos().insert() para iniciar o upload...")
            # Usa o método insert() da API videos()
            insert_request = youtube.videos().insert(
                part=','.join(body.keys()), # Partes da requisição (snippet, status)
                body=body, # Corpo da requisição com metadados do vídeo
                media_body=media_body # Corpo da mídia (o arquivo de vídeo)
            )

            # Execute a requisição de upload. Isso fará o upload real.
            # Este passo pode levar bastante tempo dependendo do tamanho do vídeo e da conexão.
            # Pode adicionar um watcher de progresso aqui se a biblioteca google-api-python-client suportar callbacks.
            logging.info("Executando requisição de upload. Isso pode levar tempo...")
            response_upload = insert_request.execute() # Executa a requisição HTTP real
            logging.info("Requisição de upload executada.")

            # Verifica a resposta do upload
            video_id = response_upload.get('id')
            if video_id:
                logging.info(f"Upload completo. Vídeo ID: {video_id}")
                # O link retornado pode ser adaptado
                logging.info(f"Link do vídeo (pode não estar ativo imediatamente): http://youtube.com/watch?v={video_id}")
            else:
                 logging.error("ERRO: Requisição de upload executada, mas a resposta não contém um ID de vídeo.", exc_info=True)
                 # Considere sair com erro aqui se o upload não retornar um ID
                 # sys.exit(1)


        except FileNotFoundError:
            # Captura o erro se o arquivo de vídeo não for encontrado para a MediaFileUpload
            logging.error(f"ERRO: Arquivo de vídeo final NÃO encontrado em {video_file_path} para upload.", exc_info=True)
            sys.exit(1) # Sai com erro se o arquivo de vídeo não existe
        except Exception as e:
            # Captura outros erros durante o processo de upload
            logging.error(f"ERRO: Falha durante o upload do vídeo: {e}", exc_info=True)
            sys.exit(1) # Sai com erro em caso de falha no upload

        logging.info("--- Etapa concluída: Upload do vídeo para o YouTube ---")


        # --- FIM DOS SEUS PASSOS DE AUTOMAÇÃO ---


    except Exception as e:
        # Este bloco captura erros inesperados que ocorram em qualquer lugar
        # dentro do bloco try principal, após a autenticação.
        logging.error(f"ERRO INESPERADO no script principal (fora das etapas conhecidas): {e}", exc_info=True) # Imprime o traceback completo
        sys.exit(1) # Garante que o workflow falhe se ocorrer um erro inesperado

    logging.info("--- Script de automação finalizado com sucesso ---")


# Configuração do parser de argumentos (manter)
# Isso permite que o script receba o nome do canal como argumento do workflow
if __name__ == "__main__":
    # Adiciona um log para indicar o início da execução principal do script
    logging.info("Script main.py iniciado via __main__.")
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    # O argumento --channel "fizzquirk" é passado pelo main.yml
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    args = parser.parse_args()
    # Chama a função main passando o argumento do canal
    main(args.channel)
