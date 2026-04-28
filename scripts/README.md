# 📜 Scripts Utilitários

Este diretório contém scripts auxiliares para o projeto Vava Doces.

---

## 📋 Scripts Disponíveis

### 🚀 `run_app.sh`
**Descrição:** Script para executar a aplicação Streamlit

**Uso:**
```bash
./scripts/run_app.sh
```

**O que faz:**
- Ativa o ambiente virtual
- Carrega variáveis de ambiente
- Executa o Streamlit

---

### 🔄 `convert_to_sheets.py`
**Descrição:** Converte arquivo Excel para Google Sheets

**Uso:**
```bash
python scripts/convert_to_sheets.py
```

**O que faz:**
- Lê arquivo XLSX local
- Converte para formato Google Sheets
- Faz upload para Google Drive

---

### 🧪 `test_after_conversion.sh`
**Descrição:** Testa conversão de dados

**Uso:**
```bash
./scripts/test_after_conversion.sh
```

**O que faz:**
- Valida dados convertidos
- Verifica integridade
- Gera relatório

> Os diagnosticos manuais usados por este script foram centralizados em `scripts/diagnostics/`.

---

### 🔬 `diagnostics/`
**Descrição:** Scripts manuais legados para diagnostico local e validacoes pontuais

**Uso:**
```bash
python scripts/diagnostics/test_connection.py
python scripts/diagnostics/test_connection_diagnostic.py
python scripts/diagnostics/test_document_type.py
python scripts/diagnostics/test_streamlit_load.py
python scripts/diagnostics/test_toml_parsing.py
```

---

### 🔎 `bronze_ingestion_diagnostic.py`
**Descrição:** Diagnóstico da ingestão Bronze para CSVs de faturamento (local/Google Drive)

**Uso (local):**
```bash
python scripts/bronze_ingestion_diagnostic.py \
  --csv-dir data/raw \
  --bronze-path data/processed/silver/sales_silver.parquet
```

**Uso (Google Drive):**
```bash
python scripts/bronze_ingestion_diagnostic.py \
  --drive-folder-id "$DRIVE_FOLDER_ID" \
  --credential-file "$GOOGLE_APPLICATION_CREDENTIALS" \
  --bronze-path data/processed/silver/sales_silver.parquet
```

**O que verifica:**
- Lista CSVs de faturamento
- Compara linhas físicas x parseadas x linhas na Bronze
- Detecta suspeitas de encoding/delimitador
- Compara parsing de datas `DD/MM/YYYY` vs `MM/DD/YYYY`

---

## ⚙️ Configuração

Certifique-se de que:
- `.env` está configurado com credenciais
- Ambiente virtual está ativado
- Dependências estão instaladas

---

## 📝 Notas

- Scripts com `.sh` precisam de permissão de execução: `chmod +x script.sh`
- Scripts Python devem ser executados com Python 3.8+
- Sempre execute da raiz do projeto

---

_Scripts Utilitários - Vava Doces_
