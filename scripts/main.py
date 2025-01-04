import google.generativeai as genai

# Configuração da API Gemini
def configurar_gemini(api_key):
    try:
        genai.configure(api_key=api_key)
        print("Configuração da API Gemini concluída.")
    except Exception as e:
        print(f"Erro na configuração da API Gemini: {e}")
        raise

# Gerar curiosidades usando o método correto
def gerar_curiosidades(api_key, quantidade):
    configurar_gemini(api_key)
    curiosidades = []
    try:
        for _ in range(quantidade):
            resposta = genai.responder(
                model="models/chat-bison-001",  # Modelo válido, ajuste se necessário
                prompt="Escreva uma curiosidade interessante e única.",
                temperature=0.7,
            )
            if resposta and "candidates" in resposta:
                curiosidades.append(resposta["candidates"][0]["output"])
            else:
                curiosidades.append("Nenhuma curiosidade gerada.")
    except AttributeError as e:
        print(f"Erro de atributo: {e}")
        raise
    except Exception as e:
        print(f"Erro geral ao gerar curiosidades: {e}")
        raise
    return curiosidades

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerar curiosidades para vídeo.")
    parser.add_argument("--gemini-api", required=True, help="Chave da API Gemini")
    parser.add_argument("--quantidade", type=int, default=5, help="Número de curiosidades a gerar")

    args = parser.parse_args()

    try:
        curiosidades = gerar_curiosidades(args.gemini_api, args.quantidade)
        if not curiosidades:
            print("Nenhuma curiosidade gerada.")
            exit(1)

        for curiosidade in curiosidades:
            print(f"Curiosidade: {curiosidade}")

    except Exception as e:
        print(f"Erro crítico: {e}")
        exit(1)
