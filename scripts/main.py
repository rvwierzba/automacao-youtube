# scripts/main.py

import argparse
import os
import tempfile
import subprocess
import google.generativeai as genai  # Importação correta
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
)
import requests  # Importado para buscar imagens no Pixabay


def gerar_curiosidades_gemini(api_key, quantidade=5):
    """
    Gera uma lista de curiosidades usando a API do Gemini.
    """
    try:
        genai.configure(api_key=api_key)
        print("Métodos disponíveis em google.generativeai após configuração:", dir(genai))  # Adiciona log
        prompt = f"Liste {quantidade} curiosidades interessantes e pouco conhecidas em português."
        response = genai.generate_text(
            model="text-bison-001",  # Utilize o modelo correto disponível para sua conta
            prompt=prompt,
            max_tokens=150,
            temperature=0.7,
        )
        curiosidades = response.text.strip().split('\n')
        # Limpar e formatar as curiosidades
        curiosidades = [c.strip('- ').strip() for c in curiosidades if c.strip()]
        return curiosidades
    except AttributeError as e:
        print(f"Erro ao gerar curiosidades com a API do Gemini: {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado ao gerar curiosidades com a API do Gemini: {e}")
        return []


# ... (restante do código permanece o mesmo)
