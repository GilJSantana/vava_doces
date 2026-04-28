# 🍰 Vava Doces - Guia Rápido de Inicialização

## ⚠️ Problema: "Pipeline sem dados de entrada em data/raw/"

Se você vê esta mensagem ao tentar executar o Streamlit, significa que não há dados em `data/raw/`. Siga um dos passos abaixo:

## ✅ Opção 1: Configurar `st.secrets` e sincronizar do Google Drive (Recomendado)

1. **Verifique o arquivo `.streamlit/secrets.toml`:**
   ```bash
   cat .streamlit/secrets.toml
   ```
   Procure por:
   - `GOOGLE_DRIVE_FOLDER_ID`
   - `GOOGLE_SHEET_ID`
   - `[gcp_service_account]`

2. **Verifique se a Service Account foi configurada:**
   ```bash
   python scripts/diagnostics/test_toml_parsing.py
   ```

3. **Execute o script de download:**
   ```bash
   uv run python scripts/download_demo_data.py
   ```

   Este script vai:
   - ✅ Tentar sincronizar arquivos do Google Drive
   - ❌ Se falhar, criar dados de demonstração local

4. **Verifique se os arquivos foram baixados:**
   ```bash
   ls -la data/raw/
   ```
   Deve haver pelo menos um arquivo `.csv` ou `.xlsx`

5. **Inicie o Streamlit:**
   ```bash
   uv run streamlit run app.py
   ```

## ✅ Opção 2: Criar Dados de Demonstração (Rápido)

Se o Google Drive não está configurado:

```bash
uv run python scripts/download_demo_data.py
```

Isso criará um arquivo `vendas_demo_2026_02.csv` em `data/raw/`

## ✅ Opção 3: Adicionar Arquivos Manualmente

1. Coloque seus arquivos CSV/XLSX em `data/raw/`:
   ```bash
   cp seus_dados.xlsx data/raw/
   ```

2. Os arquivos devem ter as colunas:
   - `Número da venda`
   - `Data da venda`
   - `Nome do produto/serviço`
   - `Quantidade de itens`
   - `Valor Total`
   - E outras colunas de vendas/faturamento

3. Inicie o app:
   ```bash
   uv run streamlit run app.py
   ```

## 🔍 Diagnosticar o Problema

**Verificar `st.secrets`:**
```bash
python scripts/diagnostics/test_toml_parsing.py
```

**Verificar diagnósticos de conexão:**
```bash
python scripts/diagnostics/test_connection.py
```

**Verificar dados locais:**
```bash
find data/raw/ -type f \( -name "*.csv" -o -name "*.xlsx" \)
```

## 📋 Estrutura de Arquivos Esperada

```
Vava_doces/
├── .streamlit/
│   └── secrets.toml               ← Configure aqui!
├── data/
│   ├── raw/                    ← Adicione aqui!
│   │   ├── vendas_2026_01.csv
│   │   └── vendas_2026_02.xlsx
│   └── processed/
│       ├── silver/
│       └── gold/
├── scripts/
│   ├── medallion_pipeline.py
│   └── diagnostics/
└── app.py
```

## 🚀 Próximos Passos

Depois de ter dados em `data/raw/`:

```bash
# 1. Inicie o app
uv run streamlit run app.py

# 2. A app automaticamente vai:
#    - Sincronizar dados do Google Drive (se disponível)
#    - Executar pipeline Medallion (RAW → SILVER → GOLD)
#    - Mostrar dashboards com análises

# 3. Ou execute o pipeline manualmente:
uv run python scripts/medallion_pipeline.py --validate
```

## ❓ FAQ

**P: "Ainda recebo o erro mesmo após adicionar arquivos"**
R: Limpe o cache do Streamlit:
```bash
streamlit cache clear
```

**P: "Como obtenho o DRIVE_FOLDER_ID?"**
R: Na URL do Google Drive:
```
https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}
```

**P: "Como consigo o JSON de credenciais?"**
R: Gere a Service Account no Google Cloud Console e copie os campos para `[gcp_service_account]` em `.streamlit/secrets.toml`.

---

**Tudo funcionando?** 🎉 Acesse `http://localhost:8501` no seu navegador!

