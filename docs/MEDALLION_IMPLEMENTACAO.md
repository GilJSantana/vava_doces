# Medallion no Vava Doces (Guia Curto)

Este projeto usa um fluxo simples de dados:

`raw -> silver -> gold -> dashboard`

## 1) Responsabilidade de cada camada

### Raw
- **Objetivo:** entrada bruta dos dados (sem padronizacao completa).
- **Fontes:** arquivos em `data/raw/` (`.csv`, `.xlsx`, `.xls`) e, quando aplicavel, Google APIs.

### Silver
- **Objetivo:** padronizar e preparar os registros para analise.
- **Inclui:** normalizacao de colunas, tipos, datas, numericos, canal/produto, deduplicacao e rastreabilidade.

### Gold
- **Objetivo:** entregar tabelas analiticas prontas para consumo.
- **Inclui:** dimensoes, fato e agregados para reduzir calculo no front-end.

### Dashboard
- **Objetivo:** visualizar dados prontos da Gold com minimo de regra de negocio na interface.

## 2) Arquivos principais

- Pipeline principal: `scripts/medallion_pipeline.py`
- Runner Silver: `scripts/run_silver_normalization.py`
- Runner Gold: `scripts/run_gold_from_silver.py`
- Normalizacao Silver: `src/domain/sales_silver_normalizer.py`
- Adapter Gold (leitura parquet): `src/infrastructure/gold_adapter.py`
- Portas de dados: `src/ports/data_source.py`
- Dashboard (entrada): `app.py`
- Paginas de visualizacao: `src/presentation/pages/`

## 3) Ordem de execucao

1. Gerar Silver a partir do Raw.
2. Gerar Gold a partir da Silver.
3. Validar testes principais.
4. Subir dashboard.

Comandos:

```bash
cd /home/gilunix/Documents/Projects/Vava_doces
python scripts/run_silver_normalization.py
python scripts/run_gold_from_silver.py
pytest -q tests/test_medallion_pipeline.py tests/test_gold_adapter.py
streamlit run app.py
```

## 4) Entradas e saidas

### Entradas
- `data/raw/*.csv`
- `data/raw/*.xlsx`
- `data/raw/*.xls`

### Saida Silver
- `data/processed/silver/sales_silver.parquet` (pipeline principal)
- `data/processed/silver/sales_silver_normalized.parquet` (runner silver dedicado)

### Saidas Gold
- `data/processed/gold/dim_produto.parquet`
- `data/processed/gold/dim_tempo.parquet`
- `data/processed/gold/dim_canal.parquet`
- `data/processed/gold/fato_vendas.parquet`
- `data/processed/gold/agg_vendas_dia.parquet`
- `data/processed/gold/agg_vendas_canal.parquet`
- `data/processed/gold/agg_vendas_produto.parquet`
- `data/processed/gold/agg_vendas_tempo.parquet`

## 5) Como validar que funcionou

Checklist rapido:
- Arquivos parquet da Silver e Gold foram gerados.
- `pytest` dos testes medallion e adapter passou.
- Logs com prefixo `[DQ]` sem erros criticos.
- Dashboard abre e exibe metricas/graficos sem falha de carga.

## 6) Principais pontos de manutencao

- **Contrato de colunas:** manter consistencia entre Silver e Gold.
- **Regras de qualidade:** revisar validacoes `[DQ]` quando houver nova fonte/coluna.
- **Nomes de arquivos Gold:** manter estaveis para nao quebrar consumo no dashboard.
- **Evolucao de metricas:** preferir calcular no Gold (fato/agregados), nao na interface.
- **Mudancas incrementais:** alterar em pequenos passos e cobrir com testes existentes.

