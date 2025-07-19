from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import requests
from typing import List, Dict, Optional, Any, Union
import json
from datetime import datetime
import time
import random

# Importações para Google Sheets
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title="API Fila de Corretores", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Corretor(BaseModel):
    nome: str
    email: str
    telefone: str
    posicao_fila: int

class NotificacaoStatus(BaseModel):
    corretor_nome: str
    telefone: str
    sucesso: bool
    erro: Optional[str] = None
    status_code: Optional[int] = None

class FilaResponse(BaseModel):
    corretor_atual: Corretor
    proximos_corretores: List[Corretor]
    timestamp: str
    fila_alterada: bool
    notificacoes_whatsapp: List[NotificacaoStatus] = []

# Configurações (usar variáveis de ambiente na produção)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "{}")

# Cache para controle de mudanças
cache_hash = None
cache_fila = []
cache_corretores_anteriores = []  # Para detectar mudanças específicas

# Variável para armazenar posição da fila em memória (fallback)
memoria_fila_position = 0

def detectar_mudancas_planilha(corretores_atuais: List[Corretor]):
    """
    Detecta mudanças específicas na planilha (adições e remoções)
    Retorna informações sobre as mudanças detectadas
    """
    global cache_corretores_anteriores
    
    if not cache_corretores_anteriores:
        # Primeira execução
        cache_corretores_anteriores = corretores_atuais.copy()
        return {
            "houve_mudanca": True,
            "primeira_execucao": True,
            "adicionados": [],
            "removidos": [],
            "total_anterior": 0,
            "total_atual": len(corretores_atuais)
        }
    
    # Cria sets para comparação mais eficiente
    nomes_anteriores = {c.nome for c in cache_corretores_anteriores}
    nomes_atuais = {c.nome for c in corretores_atuais}
    
    # Detecta adições e remoções
    adicionados = list(nomes_atuais - nomes_anteriores)
    removidos = list(nomes_anteriores - nomes_atuais)
    
    houve_mudanca = len(adicionados) > 0 or len(removidos) > 0
    
    if houve_mudanca:
        # Atualiza o cache
        cache_corretores_anteriores = corretores_atuais.copy()
    
    return {
        "houve_mudanca": houve_mudanca,
        "primeira_execucao": False,
        "adicionados": adicionados,
        "removidos": removidos,
        "total_anterior": len(cache_corretores_anteriores) if not houve_mudanca else len(cache_corretores_anteriores) - len(adicionados) + len(removidos),
        "total_atual": len(corretores_atuais)
    }

def ajustar_posicao_fila_por_mudancas(mudancas: dict, posicao_atual: int, corretores_atuais: List[Corretor]):
    """
    Ajusta a posição da fila baseado nas mudanças detectadas
    """
    global memoria_fila_position
    
    if mudancas["primeira_execucao"]:
        print("Primeira execução - iniciando fila na posição 0")
        return 0
    
    if not mudancas["houve_mudanca"]:
        return posicao_atual
    
    print(f"Mudanças detectadas:")
    print(f"  - Adicionados: {mudancas['adicionados']}")
    print(f"  - Removidos: {mudancas['removidos']}")
    print(f"  - Total anterior: {mudancas['total_anterior']}")
    print(f"  - Total atual: {mudancas['total_atual']}")
    
    nova_posicao = posicao_atual
    
    # Se houve remoções, precisa ajustar a posição
    if mudancas["removidos"]:
        # Encontra a posição original dos corretores removidos
        for nome_removido in mudancas["removidos"]:
            # Encontra onde estava o corretor removido baseado no cache anterior
            posicao_removido = None
            for i, corretor in enumerate(cache_corretores_anteriores):
                if corretor.nome == nome_removido:
                    posicao_removido = i
                    break
            
            if posicao_removido is not None:
                print(f"  - Corretor '{nome_removido}' estava na posição {posicao_removido}")
                print(f"  - Posição atual antes do ajuste: {nova_posicao}")
                
                # Se o corretor removido estava antes da posição atual
                if posicao_removido < nova_posicao:
                    nova_posicao -= 1
                    print(f"    -> Ajustando posição: {nova_posicao + 1} → {nova_posicao}")
                # Se o corretor removido era exatamente o atual
                elif posicao_removido == nova_posicao:
                    # Mantém a posição, mas pode precisar ajustar se passou do limite
                    print(f"    -> Corretor atual foi removido, verificando limites")
    
    # Garante que a posição não seja negativa nem maior que o número de corretores
    if nova_posicao < 0:
        print(f"  - Posição negativa detectada, ajustando para 0")
        nova_posicao = 0
    elif nova_posicao >= len(corretores_atuais):
        nova_posicao = len(corretores_atuais) - 1 if len(corretores_atuais) > 0 else 0
        print(f"  - Posição maior que total, ajustando para {nova_posicao}")
    
    # Para adições: novos corretores entram automaticamente no final da fila
    # (não precisamos ajustar a posição atual)
    if mudancas["adicionados"]:
        print(f"  - Novos corretores adicionados no final da fila: {mudancas['adicionados']}")
    
    print(f"Posição da fila ajustada: {posicao_atual} → {nova_posicao}")
    return nova_posicao

def is_google_sheets_configured():
    """Verifica se o Google Sheets está configurado corretamente"""
    return (SPREADSHEET_ID and SPREADSHEET_ID != "placeholder_sheet_id" and 
            GOOGLE_CREDENTIALS_JSON and GOOGLE_CREDENTIALS_JSON != "{}" and 
            GOOGLE_CREDENTIALS_JSON != '{"type":"service_account","project_id":"placeholder"}')

def get_google_sheets_client():
    """Inicializa cliente do Google Sheets"""
    if not is_google_sheets_configured():
        raise Exception("Google Sheets não configurado")
    
    try:
        # Carrega credenciais do JSON (variável de ambiente)
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao conectar Google Sheets: {str(e)}")

def get_corretores_from_sheets():
    """Busca lista de corretores da planilha do Google Sheets"""
    if not is_google_sheets_configured():
        raise HTTPException(status_code=500, detail="Google Sheets não está configurado. Verifique as variáveis de ambiente.")
    
    try:
        client = get_google_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Pega todos os dados (assumindo header na primeira linha)
        records = sheet.get_all_records()
        
        if not records:
            raise HTTPException(status_code=404, detail="Nenhum corretor encontrado na planilha")
        
        corretores = []
        for i, record in enumerate(records):
            # Converte valores para string para garantir que .strip() funcione
            nome = str(record.get('nome', ''))
            email = str(record.get('email', ''))
            telefone = str(record.get('telefone', ''))
            
            corretor = Corretor(
                nome=nome.strip(),
                email=email.strip(),
                telefone=telefone.strip(),
                posicao_fila=i + 1
            )
            corretores.append(corretor)
        
        return corretores
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler planilha: {str(e)}")

def calculate_sheet_hash(corretores: List[Corretor]) -> str:
    """Calcula hash da lista de corretores para detectar mudanças"""
    corretor_strings = [f"{c.nome}|{c.email}|{c.telefone}" for c in corretores]
    combined_string = "".join(sorted(corretor_strings))
    return hashlib.md5(combined_string.encode()).hexdigest()

def get_fila_position_from_sheets():
    """Busca a posição atual da fila armazenada na planilha ou memória"""
    global memoria_fila_position
    
    if not is_google_sheets_configured():
        print(f"Google Sheets não configurado, usando posição em memória: {memoria_fila_position}")
        return memoria_fila_position
    
    try:
        client = get_google_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verifica se existe uma aba 'Config' para armazenar a posição da fila
        try:
            config_sheet = sheet.worksheet('Config')
            position = config_sheet.acell('A2').value
            
            if position is not None and str(position).strip():
                resultado = int(position)
                print(f"Posição da fila lida do Google Sheets: {resultado}")
                
                # Só atualiza a memória se a posição do Google Sheets for diferente de 0
                # ou se a memória ainda estiver em 0 (primeira execução)
                if resultado != 0 or memoria_fila_position == 0:
                    memoria_fila_position = resultado
                    return resultado
                else:
                    print(f"Google Sheets retornou 0, mantendo posição em memória: {memoria_fila_position}")
                    return memoria_fila_position
            else:
                print(f"Posição vazia no Google Sheets, usando memória: {memoria_fila_position}")
                return memoria_fila_position
                
        except Exception as e:
            print(f"Erro ao acessar aba Config: {str(e)}")
            # Se não existe, cria a aba Config com a posição atual da memória
            try:
                config_sheet = sheet.add_worksheet(title='Config', rows=10, cols=2)
                config_sheet.update('A1', 'fila_position')
                config_sheet.update('A2', str(memoria_fila_position))
                print(f"Aba Config criada no Google Sheets com posição: {memoria_fila_position}")
            except Exception as create_error:
                print(f"Erro ao criar aba Config: {str(create_error)}")
            
            return memoria_fila_position
            
    except Exception as e:
        print(f"Erro ao conectar ao Google Sheets: {str(e)}")
        print(f"Usando posição em memória: {memoria_fila_position}")
        return memoria_fila_position

def update_fila_position_in_sheets(position: int):
    """Atualiza a posição da fila na planilha"""
    global memoria_fila_position
    
    # SEMPRE atualiza em memória primeiro
    memoria_fila_position = position
    print(f"Posição da fila atualizada em memória: {position}")
    
    if not is_google_sheets_configured():
        print("Google Sheets não configurado, usando apenas memória")
        return
    
    # Tenta atualizar no Google Sheets (mas não falha se der erro)
    try:
        client = get_google_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Tenta acessar a aba Config
        try:
            config_sheet = sheet.worksheet('Config')
        except:
            # Se a aba não existe, cria ela
            print("Aba Config não encontrada, criando...")
            config_sheet = sheet.add_worksheet(title='Config', rows=10, cols=2)
            config_sheet.update('A1', 'fila_position')
            print("Aba Config criada com sucesso")
        
        # Atualiza a posição usando o método correto
        config_sheet.update_acell('A2', str(position))
        print(f"✅ Posição da fila sincronizada com Google Sheets: {position}")
        
    except Exception as e:
        print(f"⚠️ Erro ao sincronizar com Google Sheets: {str(e)}")
        print("✅ Continuando com controle em memória (fila funcionará normalmente)")

def send_whatsapp_notifications(fila_corretores: List[Corretor], corretor_atual: Corretor) -> List[NotificacaoStatus]:
    """
    Envia notificações WhatsApp para todos os corretores sobre suas posições na fila
    com delay aleatório entre envios para evitar banimento da API
    """
    notificacoes_status = []
    
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("⚠️ Evolution API não configurada - notificações desabilitadas")
        return []
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    total_corretores = len(fila_corretores)
    
    for i, corretor in enumerate(fila_corretores):
        # Determina a mensagem baseada na posição
        if corretor.posicao_fila == 1:
            mensagem = f"""🎯 *AGORA É SUA VEZ!*

Olá {corretor.nome}! 

Você está em *1º lugar* na fila de atendimento! 📞

O próximo cliente será direcionado para você.

_Equipe Realiza Imóveis_ 🏡"""
        else:
            mensagem = f"""📋 *POSIÇÃO NA FILA ATUALIZADA*

Olá {corretor.nome}!

Sua posição atual: *{corretor.posicao_fila}º lugar* 

🎯 Corretor atual: {corretor_atual.nome}

_Equipe Realiza Imóveis_ 🏡"""
        
        # Payload da mensagem
        payload = {
            "number": corretor.telefone,
            "text": mensagem
        }
        
        try:
            print(f"📱 Enviando mensagem para {corretor.nome} (posição {corretor.posicao_fila})...")
            
            # Envia a mensagem
            response = requests.post(
                EVOLUTION_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ Mensagem enviada com sucesso para {corretor.nome}")
                notificacoes_status.append(NotificacaoStatus(
                    corretor_nome=corretor.nome,
                    telefone=corretor.telefone,
                    sucesso=True,
                    status_code=response.status_code
                ))
            else:
                error_msg = response.text
                print(f"❌ Erro ao enviar mensagem para {corretor.nome}: {error_msg}")
                notificacoes_status.append(NotificacaoStatus(
                    corretor_nome=corretor.nome,
                    telefone=corretor.telefone,
                    sucesso=False,
                    erro=error_msg,
                    status_code=response.status_code
                ))
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Erro ao enviar mensagem para {corretor.nome}: {error_msg}")
            notificacoes_status.append(NotificacaoStatus(
                corretor_nome=corretor.nome,
                telefone=corretor.telefone,
                sucesso=False,
                erro=error_msg
            ))
        
        # Delay aleatório entre envios (exceto no último)
        if i < total_corretores - 1:  # Não aplica delay no último envio
            delay = random.uniform(3, 8)  # Delay aleatório entre 3 e 8 segundos
            print(f"⏳ Aguardando {delay:.1f}s antes do próximo envio...")
            time.sleep(delay)
    
    return notificacoes_status

@app.get("/")
async def root():
    return {"message": "API Fila de Corretores - Funcionando"}

@app.get("/ping")
async def ping():
    """Endpoint para manter API viva - chamado a cada 14 minutos"""
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "message": "API mantida viva pelo ping automatico"
    }

@app.get("/health")
async def health_check():
    env_status = {
        "SPREADSHEET_ID": bool(SPREADSHEET_ID and SPREADSHEET_ID != "placeholder_sheet_id"),
        "EVOLUTION_API_URL": bool(EVOLUTION_API_URL and EVOLUTION_API_URL != "https://placeholder-api.com/api"),
        "EVOLUTION_API_KEY": bool(EVOLUTION_API_KEY and EVOLUTION_API_KEY != "placeholder_key"),
        "GOOGLE_CREDENTIALS_JSON": bool(GOOGLE_CREDENTIALS_JSON and GOOGLE_CREDENTIALS_JSON != '{"type":"service_account","project_id":"placeholder"}'),
        "google_sheets_configurado": is_google_sheets_configured()
    }
    
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(), 
        "environment": env_status,
        "posicao_fila_atual": get_fila_position_from_sheets()
    }

@app.post("/proximo-corretor", response_model=FilaResponse)
async def get_proximo_corretor(enviar_notificacoes: bool = False):
    """
    Retorna o próximo corretor da fila e avança a fila.
    O corretor atual vai para o final da fila e os outros avançam.
    Lida automaticamente com adições/remoções de corretores na planilha.
    
    Args:
        enviar_notificacoes: Se True, envia notificações WhatsApp (default: False)
    """
    global cache_hash, cache_fila
    
    try:
        # Busca corretores atuais da planilha
        corretores_atual = get_corretores_from_sheets()
        
        if not corretores_atual:
            raise HTTPException(status_code=404, detail="Nenhum corretor encontrado na planilha")
        
        # Detecta mudanças específicas na planilha
        mudancas = detectar_mudancas_planilha(corretores_atual)
        
        # Busca posição atual da fila
        fila_position = get_fila_position_from_sheets()
        
        # Ajusta posição baseado nas mudanças detectadas
        if mudancas["houve_mudanca"]:
            nova_posicao = ajustar_posicao_fila_por_mudancas(mudancas, fila_position, corretores_atual)
            if nova_posicao != fila_position:
                update_fila_position_in_sheets(nova_posicao)
                fila_position = nova_posicao
        
        # Organiza a fila: corretor atual + próximos
        total_corretores = len(corretores_atual)
        
        # Corretor atual é o da posição atual
        corretor_atual = corretores_atual[fila_position]
        corretor_atual.posicao_fila = 1
        
        # Organiza os próximos corretores
        proximos_corretores = []
        for i in range(1, total_corretores):
            index = (fila_position + i) % total_corretores
            corretor = corretores_atual[index]
            corretor.posicao_fila = i + 1
            proximos_corretores.append(corretor)
        
        # AVANÇA A FILA: próxima posição
        nova_posicao = (fila_position + 1) % total_corretores
        update_fila_position_in_sheets(nova_posicao)
        
        print(f"Corretor atual: {corretor_atual.nome}")
        print(f"Fila avançou de posição {fila_position} para {nova_posicao}")
        
        if mudancas["houve_mudanca"]:
            print("📋 Mudanças na equipe detectadas e fila ajustada automaticamente!")
        
        # Envia notificações via WhatsApp apenas se solicitado
        notificacoes_status = []
        if enviar_notificacoes:
            print("📱 Enviando notificações WhatsApp...")
            fila_completa = [corretor_atual] + proximos_corretores
            notificacoes_status = send_whatsapp_notifications(fila_completa, corretor_atual)
        else:
            print("📱 Notificações WhatsApp não solicitadas (use parâmetro enviar_notificacoes=true ou endpoint /enviar-notificacoes)")
        
        return FilaResponse(
            corretor_atual=corretor_atual,
            proximos_corretores=proximos_corretores,
            timestamp=datetime.now().isoformat(),
            fila_alterada=mudancas["houve_mudanca"],
            notificacoes_whatsapp=notificacoes_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.post("/enviar-notificacoes")
async def enviar_notificacoes_fila():
    """
    Envia notificações WhatsApp para todos os corretores sobre suas posições na fila atual.
    Este endpoint pode ser chamado separadamente para melhor performance.
    """
    try:
        # Busca corretores atuais da planilha
        corretores_atual = get_corretores_from_sheets()
        
        if not corretores_atual:
            raise HTTPException(status_code=404, detail="Nenhum corretor encontrado na planilha")
        
        # Busca posição atual da fila
        fila_position = get_fila_position_from_sheets()
        
        # Organiza a fila: corretor atual + próximos
        total_corretores = len(corretores_atual)
        
        # Corretor atual é o da posição atual
        corretor_atual = corretores_atual[fila_position]
        corretor_atual.posicao_fila = 1
        
        # Organiza os próximos corretores
        fila_completa = [corretor_atual]
        for i in range(1, total_corretores):
            index = (fila_position + i) % total_corretores
            corretor = corretores_atual[index]
            corretor.posicao_fila = i + 1
            fila_completa.append(corretor)
        
        print(f"📱 Enviando notificações WhatsApp para {len(fila_completa)} corretores...")
        print(f"🎯 Corretor atual: {corretor_atual.nome}")
        
        # Envia notificações via WhatsApp
        notificacoes_status = send_whatsapp_notifications(fila_completa, corretor_atual)
        
        # Calcula estatísticas
        sucessos = sum(1 for n in notificacoes_status if n.sucesso)
        falhas = len(notificacoes_status) - sucessos
        
        return {
            "message": f"Notificações processadas para {len(fila_completa)} corretores",
            "corretor_atual": corretor_atual.nome,
            "estatisticas": {
                "total_envios": len(notificacoes_status),
                "sucessos": sucessos,
                "falhas": falhas,
                "taxa_sucesso": round((sucessos / len(notificacoes_status)) * 100, 1) if notificacoes_status else 0
            },
            "notificacoes_detalhadas": notificacoes_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/fila-atual", response_model=FilaResponse)
async def get_fila_atual():
    """
    Retorna a fila atual SEM avançar.
    Detecta e ajusta automaticamente mudanças na planilha.
    """
    try:
        # Busca corretores atuais da planilha
        corretores_atual = get_corretores_from_sheets()
        
        if not corretores_atual:
            raise HTTPException(status_code=404, detail="Nenhum corretor encontrado na planilha")
        
        # Detecta mudanças específicas na planilha
        mudancas = detectar_mudancas_planilha(corretores_atual)
        
        # Busca posição atual da fila
        fila_position = get_fila_position_from_sheets()
        
        # Ajusta posição baseado nas mudanças detectadas
        if mudancas["houve_mudanca"]:
            nova_posicao = ajustar_posicao_fila_por_mudancas(mudancas, fila_position, corretores_atual)
            if nova_posicao != fila_position:
                update_fila_position_in_sheets(nova_posicao)
                fila_position = nova_posicao
                print("📋 Mudanças na equipe detectadas e fila ajustada automaticamente!")
        
        # Organiza a fila: corretor atual + próximos
        total_corretores = len(corretores_atual)
        
        # Corretor atual é o da posição atual
        corretor_atual = corretores_atual[fila_position]
        corretor_atual.posicao_fila = 1
        
        # Organiza os próximos corretores
        proximos_corretores = []
        for i in range(1, total_corretores):
            index = (fila_position + i) % total_corretores
            corretor = corretores_atual[index]
            corretor.posicao_fila = i + 1
            proximos_corretores.append(corretor)
        
        return FilaResponse(
            corretor_atual=corretor_atual,
            proximos_corretores=proximos_corretores,
            timestamp=datetime.now().isoformat(),
            fila_alterada=mudancas["houve_mudanca"],
            notificacoes_whatsapp=[]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.post("/reset-fila")
async def reset_fila():
    """
    Reseta a fila para o primeiro corretor
    """
    try:
        update_fila_position_in_sheets(0)
        return {"message": "Fila resetada com sucesso", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao resetar fila: {str(e)}")

@app.get("/sync-google-sheets")
async def sync_google_sheets():
    """
    Força sincronização da posição da fila com Google Sheets
    """
    global memoria_fila_position
    
    if not is_google_sheets_configured():
        return {"message": "Google Sheets não configurado", "posicao_memoria": memoria_fila_position}
    
    try:
        client = get_google_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            config_sheet = sheet.worksheet('Config')
            position = config_sheet.acell('A2').value
            posicao_sheets = int(position) if position else 0
            
            return {
                "message": "Sincronização realizada",
                "posicao_google_sheets": posicao_sheets,
                "posicao_memoria": memoria_fila_position,
                "diferenca": abs(posicao_sheets - memoria_fila_position)
            }
        except:
            config_sheet = sheet.add_worksheet(title='Config', rows=10, cols=2)
            config_sheet.update('A1', 'fila_position')
            config_sheet.update('A2', str(memoria_fila_position))
            
            return {
                "message": "Aba Config criada e sincronizada",
                "posicao_inicial": memoria_fila_position
            }
            
    except Exception as e:
        return {"error": f"Erro na sincronização: {str(e)}"}

@app.get("/status-notificacoes")
async def status_notificacoes():
    """
    Retorna informações sobre o status das notificações WhatsApp
    """
    config_status = {
        "evolution_api_configurada": bool(EVOLUTION_API_URL and EVOLUTION_API_KEY and EVOLUTION_API_URL != "https://placeholder-api.com/api"),
        "evolution_api_url": EVOLUTION_API_URL if EVOLUTION_API_URL != "https://placeholder-api.com/api" else "Não configurada",
        "api_key_configurada": bool(EVOLUTION_API_KEY and EVOLUTION_API_KEY != "placeholder_key")
    }
    
    if config_status["evolution_api_configurada"]:
        status = "✅ Evolution API configurada - Notificações disponíveis"
        detalhes = "Use os endpoints específicos para enviar notificações WhatsApp"
    else:
        status = "⚠️ Evolution API não configurada - Notificações indisponíveis"
        detalhes = "Configure as variáveis EVOLUTION_API_URL e EVOLUTION_API_KEY para ativar as notificações"
    
    return {
        "status": status,
        "detalhes": detalhes,
        "configuracao": config_status,
        "arquitetura": {
            "separacao_responsabilidades": "✅ Endpoints separados para melhor performance",
            "descricao": "Fila e notificações são independentes para permitir execução paralela"
        },
        "endpoints": {
            "gerenciar_fila": {
                "endpoint": "POST /proximo-corretor",
                "funcao": "Avança fila rapidamente (sem notificações por padrão)",
                "parametro_opcional": "?enviar_notificacoes=true para incluir notificações",
                "performance": "🚀 Rápido - apenas gerencia posições"
            },
            "enviar_notificacoes": {
                "endpoint": "POST /enviar-notificacoes", 
                "funcao": "Envia notificações WhatsApp para fila atual",
                "performance": "📱 Independente - pode ser executado em paralelo",
                "retorno": "Estatísticas detalhadas + status individual"
            },
            "consultar_fila": {
                "endpoint": "GET /fila-atual",
                "funcao": "Consulta fila sem alterações ou notificações",
                "performance": "⚡ Muito rápido - apenas consulta"
            }
        },
        "recomendacoes": {
            "n8n_performance": "Chame /proximo-corretor e /enviar-notificacoes em paralelo",
            "uso_otimo": "Use /proximo-corretor para velocidade, /enviar-notificacoes quando necessário",
            "monitoramento": "Use /enviar-notificacoes para obter estatísticas detalhadas"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

# Export for Vercel
handler = app 