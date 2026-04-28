# 🎯 Guia Rápido - Vava Doces Streamlit

## 🚀 Como Executar a Aplicação

### Pré-requisitos
```bash
# Sincronizar dependências a partir do pyproject.toml
uv sync

# Alternativa: executar sem ativar o ambiente manualmente
uv run pytest -q
```

### Executar a Aplicação
```bash
# Método 1: Usando o script
./run_app.sh

# Método 2: Direto com Streamlit
uv run streamlit run app.py

# Método 3: Com porta específica
uv run streamlit run app.py --server.port 8501
```

A aplicação estará disponível em: `http://localhost:8501`

---

## 📊 Páginas Disponíveis

### 1. 📊 Dashboard
- **Descrição**: Visão executiva da rentabilidade
- **Funcionalidades**:
  - KPIs de faturamento, lucro e margem
  - Matriz de rentabilidade
  - Alertas de auditoria para custos ausentes ou inconsistentes

### 2. 💰 Custos de Produção
- **Descrição**: Cockpit de custos por produto e receita
- **Funcionalidades**:
  - Visualização do custo unitário de produção
  - Detalhamento por ingrediente
  - Apoio à auditoria da ficha técnica

### 3. 💹 Faturamento (Auditoria)
- **Descrição**: Visão analítica e auditável das vendas processadas
- **Funcionalidades**:
  - Inspeção de vendas da camada Gold
  - Filtros e apoio ao troubleshooting
  - Conferência dos dados materializados pelo pipeline

---

## 🎨 Identidade Visual

A aplicação usa as cores da Vava Doces:
- **Verde Escuro**: #0F3B2E
- **Verde**: #145D44
- **Dourado**: #C9A23A
- **Creme**: #F6F1E6

**Fonte**: Playfair Display

**Logo**: assets/logo.png (com bordas arredondadas)

---

## 📁 Estrutura de Arquivos

```
Vava_doces/
├── app.py                          # Entrada principal Streamlit
├── .streamlit/
│   └── secrets.toml.example        # Exemplo de configuração para local/Cloud
├── scripts/
│   ├── medallion_pipeline.py       # Pipeline RAW -> SILVER -> GOLD
│   └── diagnostics/                # Diagnósticos manuais
├── src/
│   ├── domain/
│   ├── infrastructure/
│   └── presentation/
│       ├── navigation.py
│       └── pages/
│           ├── dashboard.py
│           ├── production_costs.py
│           └── sales_shared.py
├── data/
│   ├── raw/
│   └── processed/
├── tests/
│   ├── test_app_dispatcher.py
│   ├── test_dashboard_costs.py
│   ├── test_google_sheets_adapter.py
│   ├── test_integration.py
│   └── test_profitability_pipeline.py
├── assets/
│   └── logo.png
├── pyproject.toml
└── README.md
```

> Observação: a estrutura acima foi resumida para destacar os pontos principais do fluxo atual.

---

## 🧪 Testes

### Executar Testes
```bash
# Todos os testes
uv run pytest -q

# Teste específico
uv run pytest -q tests/test_google_sheets_adapter.py

# Com cobertura
uv run pytest --cov=src tests/
```

### Testes Disponíveis
- ✅ Suite oficial em `tests/`
- ✅ Diagnosticos manuais em `scripts/diagnostics/`
- ✅ Testes de dashboard e rentabilidade
- ✅ Testes de adaptadores Google
- ✅ Testes de integração do pipeline

---

## 🔐 Configuração de Credenciais

### Streamlit Secrets (recomendado)
Crie o arquivo `.streamlit/secrets.toml` a partir do exemplo:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Preencha pelo menos:

```toml
OAUTH2_CLIENT_ID = "..."
OAUTH2_CLIENT_SECRET = "..."
OAUTH2_REDIRECT_URI = "http://localhost:8501"
GOOGLE_DRIVE_FOLDER_ID = "..."
GOOGLE_SHEET_ID = "..."

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

### `.env` (legado opcional)
O `.env` ainda pode ser útil em alguns diagnósticos manuais, mas o fluxo principal da aplicação usa `st.secrets`.

### Verificar Conexão
```bash
python scripts/diagnostics/test_connection.py
```

---

## 📊 Fontes de Dados

- **Google Drive**: origem persistente dos ativos `.parquet` da camada Gold
- **Google Sheets**: apoio a ingestão e planilhas operacionais/manuais
- **Camada Gold**: base principal consumida pelas páginas executivas

> A interface Streamlit atual não expõe mais as antigas 7 páginas operacionais; ela foi reduzida para 3 páginas executivas.

---

## 🐛 Troubleshooting

### Problema: Imagem do logo não carrega
**Solução**: Verifique se `assets/logo.png` existe e é uma imagem válida

### Problema: Erro de conexão com Google Sheets
**Solução**: Execute `python scripts/diagnostics/test_connection.py` para diagnosticar

### Problema: Dados não aparecem
**Solução**: Verifique se `.streamlit/secrets.toml` foi configurado, se o acesso ao Google Drive está válido e se o pipeline conseguiu materializar os arquivos Gold

### Problema: Porta já está em uso
**Solução**: Use `uv run streamlit run app.py --server.port 8503`

---

## 📝 Notas Importantes

- A aplicação pode usar Google OAuth2, Google Drive e Google Sheets no mesmo fluxo
- O armazenamento analítico principal está na camada Gold materializada em `.parquet`
- `st.secrets` é a forma recomendada de configurar credenciais em local e no Streamlit Cloud
- Os diagnósticos manuais foram movidos para `scripts/diagnostics/`

---

**Última atualização**: 28 de Abril de 2026
**Status**: ✅ Alinhado ao fluxo atual

