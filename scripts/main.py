import google.generativeai as genai

# Configurar a API Gemini
def configurar_gemini(api_key):
    genai.configure(api_key=api_key)

# Função para gerar curiosidades
def gerar_curiosidades(api_key, quantidade):
    configurar_gemini(api_key)
    curiosidades = []
    try:
        for _ in range(quantidade):
            resposta = genai.responder(
                model="models/text-bison-001",  # Substitua pelo modelo correto se necessário
                prompt="Escreva uma curiosidade interessante e única.",
                temperature=0.7
            )
            if resposta and resposta.get("candidates"):
                curiosidades.append(resposta["candidates"][0]["output"])
            else:
                curiosidades.append("Nenhuma curiosidade gerada.")
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

    curiosidades = gerar_curiosidades(args.gemini_api, args.quantidade)
    if not curiosidades:
        print("Nenhuma curiosidade única foi gerada.")
        exit(1)

    for curiosidade in curiosidades:
        print(curiosidade)
