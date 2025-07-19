# API Endpoint para Vercel
import sys
import os

# Add parent directory to path to import main.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# This is the entry point for Vercel 