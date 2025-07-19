# 🏡 Corretor Queue API

API FastAPI para gerenciamento de fila de corretores de imóveis integrada com Google Sheets e notificações WhatsApp via Evolution API.

## 📋 Funcionalidades

- **🔄 Fila Circular**: Sistema de fila rotativa para corretores
- **📊 Google Sheets**: Integração completa com planilha do Google
- **📱 WhatsApp**: Notificações automáticas via Evolution API
- **🔍 Detecção Automática**: Identifica mudanças na planilha (adições/remoções)
- **⚡ Performance**: Endpoints separados para máxima velocidade
- **🛡️ Proteção**: Delay aleatório para evitar banimento da API

## 🚀 Endpoints

### 📋 Gerenciamento de Fila

- **`POST /proximo-corretor`** - Avança fila (rápido, sem notificações)
- **`POST /proximo-corretor?enviar_notificacoes=true`** - Avança fila com notificações
- **`GET /fila-atual`** - Consulta fila atual (apenas leitura)
- **`POST /reset-fila`** - Reinicia fila na posição 0

### 📱 Notificações

- **`POST /enviar-notificacoes`** - Envia notificações WhatsApp com estatísticas
- **`GET /status-notificacoes`** - Status da configuração Evolution API

### 🔧 Utilitários

- **`GET /sync-google-sheets`** - Sincroniza posição com Google Sheets

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` baseado no `env_example.sh`:

```bash
# Google Sheets
export GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account",...}'
export GOOGLE_SHEETS_SPREADSHEET_ID="seu_spreadsheet_id"

# Evolution API (WhatsApp)
export EVOLUTION_API_URL="https://sua-api.com/message/sendText/instancia"
export EVOLUTION_API_KEY="sua_api_key"
```

### 2. Estrutura do Google Sheets

#### Aba "Corretores":
| Nome | Email | Telefone |
|------|-------|----------|
| João Silva | joao@email.com | 5511999999999 |
| Maria Santos | maria@email.com | 5511888888888 |

#### Aba "Config":
| Chave | Valor |
|-------|-------|
| fila_position | 0 |

### 3. Instalação

```bash
# Clone o repositório
git clone https://github.com/nicfuji87/corretor-api.git
cd corretor-api

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate   # Windows

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp env_example.sh .env
# Edite .env com suas credenciais

# Execute
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🎯 Como Usar

### Cenário 1: Máxima Performance (Recomendado)
```javascript
// Chama endpoints em paralelo
Promise.all([
  fetch('POST /proximo-corretor'),           // Avança fila rapidamente
  fetch('POST /enviar-notificacoes')         // Envia notificações
])
```

### Cenário 2: Tudo em Um
```javascript
// Tradicional - tudo junto
fetch('POST /proximo-corretor?enviar_notificacoes=true')
```

### Cenário 3: Apenas Consulta
```javascript
// Só consulta, não altera nada
fetch('GET /fila-atual')
```

## 📊 Exemplo de Resposta

### Fila Atual
```json
{
  "corretor_atual": {
    "nome": "João Silva",
    "email": "joao@email.com", 
    "telefone": "5511999999999",
    "posicao_fila": 1
  },
  "proximos_corretores": [
    {
      "nome": "Maria Santos",
      "email": "maria@email.com",
      "telefone": "5511888888888", 
      "posicao_fila": 2
    }
  ],
  "timestamp": "2024-01-15T10:30:00",
  "fila_alterada": false,
  "notificacoes_whatsapp": []
}
```

### Estatísticas de Notificações
```json
{
  "message": "Notificações processadas para 8 corretores",
  "corretor_atual": "João Silva",
  "estatisticas": {
    "total_envios": 8,
    "sucessos": 8,
    "falhas": 0,
    "taxa_sucesso": 100.0
  },
  "notificacoes_detalhadas": [
    {
      "corretor_nome": "João Silva",
      "telefone": "5511999999999",
      "sucesso": true,
      "status_code": 201
    }
  ]
}
```

## 🛡️ Recursos de Segurança

- **Delay Aleatório**: 3-8 segundos entre envios WhatsApp
- **Fallback**: Continua funcionando mesmo se Google Sheets falhar
- **Logs Detalhados**: Monitora todos os envios e erros
- **Validação**: Verifica integridade dos dados

## 🔧 Detecção Automática de Mudanças

A API detecta automaticamente:
- ✅ **Novos corretores** → Adicionados ao final da fila
- ✅ **Corretores removidos** → Fila se ajusta automaticamente
- ✅ **Alterações de dados** → Sincroniza automaticamente

## 📱 Integração N8N

Perfeito para automação com n8n:

```javascript
// Webhook recebe lead
// → Chama POST /proximo-corretor  
// → Envia lead para corretor atual
// → Opcionalmente chama POST /enviar-notificacoes
```

## 🌐 Deploy

### Vercel ⭐ (Recomendado)
Arquivo `vercel.json` incluído para deploy automático.
✅ Dependências otimizadas para < 250MB
✅ Deploy automático via GitHub

### Outras Plataformas
- Heroku
- Railway
- DigitalOcean
- AWS Lambda

## 📄 Licença

MIT License - Livre para uso comercial e pessoal.

## 🆘 Suporte

Para dúvidas ou suporte:
- Email: fujimoto.nicolas@gmail.com
- GitHub Issues: [Issues](https://github.com/nicfuji87/corretor-api/issues)

---

**🚀 Desenvolvido com FastAPI + Google Sheets + Evolution API** 