# Diagnosticos manuais

Scripts nesta pasta sao utilitarios manuais e **nao** fazem parte da suite oficial do `pytest`.

## Arquivos

- `test_connection.py` — checagem manual de credenciais/ID de planilha
- `test_connection_diagnostic.py` — diagnostico manual de acesso ao Google Sheets
- `test_document_type.py` — valida manualmente o tipo de documento no Google Drive
- `test_streamlit_load.py` — smoke check legado de carregamento do `app.py`
- `test_toml_parsing.py` — valida parsing local de `.streamlit/secrets.toml`

## Uso

Execute sempre a partir da raiz do projeto:

```bash
python scripts/diagnostics/test_connection.py
python scripts/diagnostics/test_connection_diagnostic.py
python scripts/diagnostics/test_document_type.py
python scripts/diagnostics/test_streamlit_load.py
python scripts/diagnostics/test_toml_parsing.py
```

