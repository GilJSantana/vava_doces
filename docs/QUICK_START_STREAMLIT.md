# 🎯 Guia Rápido - Vava Doces Streamlit

## 🚀 Como Executar a Aplicação

### Pré-requisitos
```bash
# Instalar dependências
uv pip install -r requirements.txt

# Ou manualmente
uv pip install streamlit pandas gspread google-oauth2
```

### Executar a Aplicação
```bash
# Método 1: Usando o script
bash run_app.sh

# Método 2: Direto com Streamlit
streamlit run app.py

# Método 3: Com porta específica
streamlit run app.py --server.port 8501
```

A aplicação estará disponível em: `http://localhost:8502`

---

## 📊 Páginas Disponíveis

### 1. 📊 Dashboard
- **Descrição**: Visão geral do sistema com métricas principais
- **Métricas**: Total de Produtos, Total de Vendas, Valor Total, Categorias
- **Gráficos**: Distribuição por categoria, Últimos registros

### 2. 📦 Cadastro de Produtos
- **Descrição**: Gestão completa de produtos
- **Funcionalidades**: 
  - Visualização de todos os produtos
  - Filtro por categoria
  - Estatísticas (Total, Categorias, Preço Médio)
  - Download em CSV

### 3. 🥘 Matéria Prima
- **Descrição**: Gestão de matérias-primas
- **Funcionalidades**:
  - Lista completa de itens
  - Estatísticas de unidades e preços
  - Download em CSV

### 4. 💳 Vendas Diárias
- **Descrição**: Registro e análise de vendas diárias
- **Funcionalidades**:
  - Métricas de vendas (total, valor, média)
  - Gráfico temporal de vendas
  - Download em CSV

### 5. 📈 Resumo Diário
- **Descrição**: Resumos consolidados diários
- **Funcionalidades**:
  - Visualização de resumos
  - Download em CSV

### 6. 📊 Análise por Categoria
- **Descrição**: Análise categórica dos produtos
- **Funcionalidades**:
  - Análise por categoria
  - Download em CSV

### 7. 🔍 Análise Detalhada
- **Descrição**: Análises avançadas
- **Funcionalidades**:
  - Custos por receita
  - Análise de margens
  - Relatórios personalizados

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
├── app.py                          # Aplicação principal Streamlit
├── src/
│   ├── domain/
│   │   └── cost_analysis_service.py
│   ├── infrastructure/
│   │   └── google_sheets_adapter.py
│   └── ports/
│       └── data_source.py
├── tests/
│   ├── test_cost_analysis_service.py
│   ├── test_google_sheets_adapter.py
│   ├── test_integration.py
│   └── test_streamlit_app.py
├── assets/
│   └── logo.png
├── credencial/
│   └── vava-doces-0667d5821bd5.json
└── README.md
```

---

## 🧪 Testes

### Executar Testes
```bash
# Todos os testes
pytest

# Teste específico
pytest tests/test_google_sheets_adapter.py -v

# Com cobertura
pytest --cov=src tests/
```

### Testes Disponíveis
- ✅ Test Connection (test_connection.py)
- ✅ Test Streamlit Load (test_streamlit_load.py)
- ✅ Test Cost Analysis Service
- ✅ Test Google Sheets Adapter
- ✅ Test Integration

---

## 🔐 Configuração de Credenciais

### Variáveis de Ambiente
```bash
# .env file
GOOGLE_APPLICATION_CREDENTIALS=./credencial/vava-doces-0667d5821bd5.json
GOOGLE_SHEET_ID=1KEzf8FcL21DMk_64t-B9gMQIxjEx3ZPS_XsY-jYNVNk
```

### Verificar Conexão
```bash
python test_connection.py
```

---

## 📊 Abas do Google Sheets

A aplicação trabalha com as seguintes abas:

1. **Cadastro Produtos** - Catálogo de produtos
2. **Matéria Prima** - Inventário de matérias-primas
3. **Vendas Diárias** - Registro de vendas
4. **Resumo Diário** - Consolidado diário
5. **Análise por Categoria** - Análises categóricas
6. **Ficha Técnica Exemplo** - Template de fichas técnicas

---

## 🐛 Troubleshooting

### Problema: Imagem do logo não carrega
**Solução**: Verifique se `assets/logo.png` existe e é uma imagem válida

### Problema: Erro de conexão com Google Sheets
**Solução**: Execute `python test_connection.py` para diagnosticar

### Problema: Dados não aparecem
**Solução**: Verifique se as abas da planilha têm os nomes exatos

### Problema: Port já está em uso
**Solução**: Use `streamlit run app.py --server.port 8503`

---

## 📝 Notas Importantes

- A aplicação requer conexão com a internet para acessar Google Sheets
- Certifique-se de que o arquivo de credenciais está no local correto
- Os nomes das abas do Google Sheets devem ser exatos
- O cache de dados é armazenado em memória (sem persistência)

---

**Última atualização**: 25 de Fevereiro de 2026
**Status**: ✅ Operacional

