# 📊 Dados do Projeto

Este diretório contém os dados utilizados no projeto Vava Doces.

---

## 📁 Estrutura

```
data/
├── raw/              → Dados brutos (não processados)
└── processed/        → Dados processados
```

---

## 📂 raw/

**Descrição:** Dados brutos, originais, não modificados

**Conteúdo atual:**
- `RECEITAS AWI.xlsx` - Planilha original com receitas e ingredientes

**Regras:**
- ❌ **NÃO MODIFICAR** arquivos desta pasta
- ✅ Apenas leitura
- ✅ Fonte única de verdade
- ✅ Backup antes de qualquer operação

---

## 📂 processed/

**Descrição:** Dados após processamento/transformação

**Uso:**
- Dados limpos
- Dados transformados
- Dados agregados
- Exports temporários

**Regras:**
- ✅ Pode ser modificado
- ✅ Pode ser regerado a partir de raw/
- ⚠️ Não fazer commit se muito grande

---

## 🔄 Fluxo de Dados

```
raw/RECEITAS AWI.xlsx
    ↓
(Scripts de conversão)
    ↓
Google Sheets (online)
    ↓
(API Google Sheets)
    ↓
Streamlit (visualização)
```

---

## 📝 Notas

### Sobre `RECEITAS AWI.xlsx`:
- Formato: Excel 2007+ (.xlsx)
- Abas: Produtos, Receitas, Matéria Prima, etc
- Encoding: UTF-8
- Não fazer commit se contiver dados sensíveis

### GitIgnore:
- `data/processed/*` - Ignorado por padrão
- `data/raw/*` - Verificar se deve ser commitado

---

## 🛡️ Backup

Antes de qualquer operação destrutiva:
```bash
cp data/raw/RECEITAS\ AWI.xlsx data/raw/RECEITAS\ AWI.xlsx.backup
```

---

_Diretório de Dados - Vava Doces_

