## IMPLEMENTACAO SEGURANCA - OAUTH2 + DRIVE PERMISSION CHECK
## Atualizado para a arquitetura atual
## Status: ✅ ALINHADO AO FLUXO EM PRODUCAO

---

### 1. AUTENTICACAO (IDENTIDADE)

**Arquivo:** `src/infrastructure/google_oauth2_adapter.py`
**Classe:** `GoogleOAuth2Adapter`

#### Fluxo OAuth2
1. Le `OAUTH2_CLIENT_ID`, `OAUTH2_CLIENT_SECRET` e `OAUTH2_REDIRECT_URI` de `st.secrets`
2. Gera a URL de login com encoding compativel com OAuth2
3. Troca o codigo por token com `exchange_code_for_token()`
4. Extrai o email do usuario com `get_user_email_from_token()`
5. Armazena a identidade em `st.session_state`

#### Garantias do fluxo
- sanitizacao de `client_id`, `client_secret` e `redirect_uri`
- `redirect_uri` canonica lida de `st.secrets`
- login compatibilizado com ambiente Streamlit Cloud

---

### 2. AUTORIZACAO (PORTEIRO DO DRIVE)

**Arquivo:** `src/infrastructure/google_oauth2_adapter.py`
**Classe:** `GoogleDrivePermissionChecker`

#### Fluxo de verificacao
1. Le a Service Account em `st.secrets["gcp_service_account"]`
2. Faz cast explicito para `dict` antes de usar `google-auth`
3. Constrói o cliente Drive API v3
4. Lista permissoes do arquivo/pasta com `pageSize=100`
5. Procura o email do usuario de forma case-insensitive
6. Valida se o papel e `owner`, `writer` ou `reader`

#### Observacoes importantes
- nao depende mais de `SERVICE_ACCOUNT_FILE`
- falha de forma clara quando `gcp_service_account` esta ausente ou invalido
- usa `GOOGLE_DRIVE_FOLDER_ID` como identificador canonico do recurso protegido

---

### 3. CONTROLE DE FLUXO NA UI

**Arquivo:** `app.py`
**Arquivo:** `src/presentation/auth_page.py`

#### Sequencia de execucao
1. inicializa estado de autenticacao
2. verifica OAuth2
3. verifica permissao no Drive
4. somente entao executa `initialize_data_pipeline()` e libera as paginas executivas

#### Paginas liberadas apos autorizacao
- `📊 Dashboard`
- `💰 Custos de Produção`
- `💹 Faturamento (Auditoria)`

---

### 4. CONFIGURACAO NECESSARIA

**Arquivo:** `.streamlit/secrets.toml.example`

```toml
OAUTH2_CLIENT_ID = "YOUR_CLIENT_ID.apps.googleusercontent.com"
OAUTH2_CLIENT_SECRET = "YOUR_CLIENT_SECRET"
OAUTH2_REDIRECT_URI = "http://localhost:8501"
GOOGLE_DRIVE_FOLDER_ID = "YOUR_DRIVE_FOLDER_ID"
GOOGLE_SHEET_ID = "YOUR_GOOGLE_SHEET_ID"

[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
client_email = "YOUR_SERVICE_ACCOUNT_EMAIL"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

---

### 5. RELACAO COM A NOVA ARQUITETURA DE DADOS

- a seguranca continua sendo um gate anterior ao carregamento dos dados;
- apos autorizacao, o app pode sincronizar dados operacionais e materializar a Gold layer;
- as paginas executivas consomem os `.parquet` persistidos no Google Drive.

---

### 6. VALIDACAO OPERACIONAL

Fluxo esperado:

```bash
uv run streamlit run app.py
```

- o botao de login deve aparecer para usuarios nao autenticados;
- apos login, a permissao do Drive deve ser validada;
- se autorizado, a aplicacao carrega pipeline + paginas executivas.

---

### 7. LOGS E DEPURACAO

Os logs priorizam rastreabilidade sem expor segredos:

- sucesso/erro no token exchange OAuth2;
- inicio da verificacao de permissao no Drive;
- ausencia ou invalidade de `gcp_service_account`;
- usuario autorizado ou negado.

---

**Status Atual:** documento alinhado ao uso de `st.secrets`, `gcp_service_account` e `GOOGLE_DRIVE_FOLDER_ID`.
