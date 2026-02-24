# 🚀 Quick Start - Vava Doces

## ⚡ Início Rápido (5 minutos)

### 1. Clonar e Instalar
```bash
cd /home/gilunix/Documents/Projects/Vava_doces
uv install
```

### 2. Configurar Credenciais
```bash
cp .env.example .env
# Editar .env com:
# - GOOGLE_APPLICATION_CREDENTIALS: caminho do JSON
# - GOOGLE_SHEET_ID: ID da planilha
```

### 3. Executar a Aplicação
```bash
./run_app.sh
# Abrir: http://localhost:8501
```

---

## 📚 Documentação Completa

| Arquivo | Descrição |
|---------|-----------|
| `README.md` | 📖 Guia principal, arquitetura e boas práticas |
| `STREAMLIT_SETUP.md` | 🎨 Setup detalhado do Streamlit |
| `IMPLEMENTATION_SUMMARY.md` | 📊 Resumo técnico da implementação |
| `QUICK_START.md` | ⚡ Este arquivo |

---

## 🧪 Rodar Testes

```bash
# Todos os testes
uv run pytest -v

# Teste específico
uv run pytest -v tests/test_cost_analysis_service.py

# Com cobertura
uv run pytest --cov=src tests/
```

---

## 📁 Estrutura do Projeto

```
.
├── app.py                          # Aplicação Streamlit
├── run_app.sh                      # Script para executar
├── .env.example                    # Modelo de configuração
├── pytest.ini                      # Config do pytest
├── pyproject.toml                  # Dependências
│
├── src/                            # Código-fonte
│   ├── domain/
│   │   └── cost_analysis_service.py
│   ├── infrastructure/
│   │   └── google_sheets_adapter.py
│   └── ports/
│       └── data_source.py
│
├── tests/                          # Testes
│   ├── conftest.py
│   ├── test_cost_analysis_service.py
│   ├── test_google_sheets_adapter.py
│   ├── test_streamlit_app.py
│   └── test_integration.py
│
├── .streamlit/
│   └── config.toml                 # Config do tema
│
└── docs/                           # Documentação
    ├── README.md
    ├── STREAMLIT_SETUP.md
    ├── IMPLEMENTATION_SUMMARY.md
    └── QUICK_START.md
```

---

## 🎯 Principais Funcionalidades

### Dashboard 📊
- Visão geral de custos
- Métricas principais
- Gráficos interativos

### Custos 💰
- Tabela detalhada
- Filtros por receita
- Download em CSV

### Faturamento 📈
- Dados de vendas
- Estatísticas
- Exportação de dados

### Análise 🔍
- Custos por receita
- Análise de margens
- Relatórios customizados

---

## 🔧 Troubleshooting Rápido

### Erro: "Arquivo .env não encontrado"
```bash
cp .env.example .env
# Editar com suas credenciais
```

### Erro: "Failed to fetch from Google Sheets"
- Verificar ID da planilha
- Verificar permissões da Service Account
- Verificar arquivo JSON de credenciais

### Porta 8501 em uso
```bash
uv run streamlit run app.py --server.port 8502
```

### Reinstalar dependências
```bash
uv install --force
```

---

## 📞 Principais Comandos

```bash
# Desenvolvimento
uv install                          # Instalar dependências
uv run pytest -v                    # Rodar testes
./run_app.sh                        # Iniciar Streamlit

# Manutenção
git status                          # Status do repo
git log --oneline                   # Histórico
uv lock                             # Atualizar lock file

# Análise
uv run pytest --cov=src tests/      # Cobertura de testes
uv run pytest -v -k integration     # Testes de integração
```

---

## 🎓 Aprender Mais

### Arquitetura
Leia: `README.md` → Seção "Contratos, design e boas práticas"

### Streamlit
Leia: `STREAMLIT_SETUP.md` → Seção "Estrutura da Aplicação"

### Testes
Consulte: `tests/` → Todos os arquivos para exemplos

### Implementação
Leia: `IMPLEMENTATION_SUMMARY.md` → Seção completa

---

## 🚀 Próximos Passos

1. **Primeira execução**: `./run_app.sh`
2. **Explorar dados**: Navegar pelas abas do Dashboard
3. **Rodar testes**: `uv run pytest -v`
4. **Revisar código**: Consultar `src/`
5. **Estender**: Adicionar novas análises conforme necessário

---

## 📊 Status do Projeto

- ✅ Arquitetura implementada
- ✅ Testes (19 testes passando)
- ✅ Streamlit com 4 páginas
- ✅ Documentação completa
- ✅ 10 commits semânticos

**Pronto para desenvolvimento contínuo!**

---

**Última atualização**: 24/02/2026

