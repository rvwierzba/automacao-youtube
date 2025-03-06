import os
import argparse
import logging
import json

logging.basicConfig(level=logging.INFO)

def main(channel):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_dir = os.path.join(base_dir, 'credentials')
    credential_file = 'canal1_client_secret.json.base64'

    credential_path = os.path.join(credentials_dir, credential_file)

    try:
        with open(credential_path, 'r') as f:
            # Lógica para processar o arquivo de credenciais
            logging.info(f"Arquivo de credenciais encontrado: {credential_path}")
            # ... resto do seu código ...
    except FileNotFoundError:
        logging.error(f"Arquivo de credenciais não encontrado em: {credential_path}")
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatiza o YouTube.")
    parser.add_argument("--channel", required=True, help="Nome do canal a ser automatizado.")
    args = parser.parse_args()
    main(args.channel)
