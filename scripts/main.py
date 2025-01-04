import google.generativeai as palm

# Configurar a API Gemini
def configurar_gemini(api_key):
    palm.configure(api_key=api_key)

# Gerar curiosidades
def gerar_curiosidades(api_key, quantidade):
    configurar_gemini(api_key)
    curiosidades = []
    try:
        # Obter o primeiro modelo disponível
        modelos = palm.list_models()
        if not modelos:
            raise ValueError("Nenhum modelo disponível para geração de texto.")
        modelo = modelos[0].name  # Selecionar o primeiro modelo

        for i in range(quantidade):
            resposta = palm.generate_text(model=modelo, prompt="Escreva uma curiosidade interessante e única.")
            curiosidades.append(resposta.result if resposta else "Nenhuma curiosidade gerada.")
    except Exception as e:
        print(f"Erro ao gerar curiosidades: {e}")
    return curiosidades

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar vídeo com curiosidades.")
    parser.add_argument("--gemini-api", required=True, help="Chave da API Gemini")
    parser.add_argument("--youtube-channel", required=True, help="ID do canal no YouTube")
    parser.add_argument("--pixabay-api", required=True, help="Chave da API Pixabay")
    parser.add_argument("--quantidade", type=int, default=5, help="Número de curiosidades a gerar")
    
    args = parser.parse_args()

    # Geração de curiosidades
    curiosidades = gerar_curiosidades(args.gemini_api, args.quantidade)
    if not curiosidades:
        print("Nenhuma curiosidade única foi gerada.")
        exit(1)

    # Exibir as curiosidades geradas
    for curiosidade in curiosidades:
        print(curiosidade)
