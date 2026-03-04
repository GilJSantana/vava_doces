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

