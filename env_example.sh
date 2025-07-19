# Google Sheets Configuration (OBRIGATÓRIO)
# ID da planilha do Google Sheets (parte da URL)
# Exemplo: https://docs.google.com/spreadsheets/d/ESTE_VALOR_AQUI/edit
SPREADSHEET_ID=sua_planilha_id_aqui

# JSON de credenciais da conta de serviço do Google (copie todo o conteúdo do arquivo JSON)
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"seu-projeto","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\nSUA_CHAVE_PRIVADA_AQUI\n-----END PRIVATE KEY-----\n","client_email":"email@seu-projeto.iam.gserviceaccount.com","client_id":"123456","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/email%40seu-projeto.iam.gserviceaccount.com","universe_domain":"googleapis.com"}

# Evolution API Configuration (para notificações WhatsApp)
EVOLUTION_API_URL=https://sua-evolution-api.com/api
EVOLUTION_API_KEY=sua_evolution_api_key_aqui

# Configuração de ambiente
DEBUG=False
PORT=8000
HOST=127.0.0.1