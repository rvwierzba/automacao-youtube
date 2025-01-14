import argparse
import requests
import logging
import sys

def main():
    parser = argparse.ArgumentParser(description="Automação YouTube")
    parser.add_argument('--gemini-api', required=True, help='Chave da API Gemini')
    parser.add_argument('--youtube-channel', required=True, help='ID do Canal YouTube')
    parser.add_argument('--pixabay-api', required=True, help='Chave da API Pixabay')
    parser.add_argument('--quantidade', type=int, default=20, help='Quantidade de vídeos por execução')

    args = parser.parse_args()

    # Configuração do logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Iniciando automação com as seguintes configurações:")
    logging.info(f"Gemini API Key: {'***'}")
    logging.info(f"YouTube Channel ID: {'***'}")
    logging.info(f"Pixabay API Key: {'***'}")
    logging.info(f"Quantidade de vídeos: {args.quantidade}")
    logging.info("Termo de busca: nature")

    # Validação do parâmetro quantidade
    if args.quantidade < 3 or args.quantidade > 200:
        logging.error(f"Erro: 'quantidade' deve estar entre 3 e 200. Valor fornecido: {args.quantidade}")
        sys.exit(1)

    try:
        response = requests.get('https://pixabay.com/api/', params={
            'key': args.pixabay_api,
            'per_page': args.quantidade,
            'safesearch': True,
            'q': 'nature'
        })
        response.raise_for_status()
        data = response.json()
        # Processar os dados conforme necessário
        logging.info(f"Recebido {len(data.get('hits', []))} resultados da API do Pixabay.")
        
        # Exemplo de processamento: listar URLs das imagens
        for hit in data.get('hits', []):
            image_url = hit.get('webformatURL')
            logging.info(f"Imagem encontrada: {image_url}")
        
        # Aqui você pode adicionar a lógica para criar vídeos, upload no YouTube, etc.
        
    except requests.exceptions.HTTPError as err:
        logging.error(f"Erro durante a execução: {err}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Erro inesperado: {e}")
        sys.exit(1)

    # Continue com o restante do script, como interação com YouTube, etc.

if __name__ == "__main__":
    main()
