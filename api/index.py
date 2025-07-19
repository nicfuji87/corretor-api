# API Endpoint para Vercel
import sys
import os

# Adiciona o diretório pai ao path para importar main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Exporta a aplicação para a Vercel
handler = app 