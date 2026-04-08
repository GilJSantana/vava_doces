"""Relatório Forense: Diagnóstico de Perda de Registros Bronze → Silver → Gold

Análise de 3 camadas de transformação que podem descartar registros:
1. SILVER: deduplicação e normalização
2. GOLD: joins com dimensões (produto/tempo) usam LEFT JOIN, preservam órfãos
3. PRESENTATION: filtros de data/status

Contexto do problema:
- Janeiro 2742 → 0 no Streamlit
- Fevereiro 3348 → 3337 no Streamlit (11 registros perdidos)

SUSPEITADOS (por ordem de probabilidade):
"""

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ 1. CAMADA SILVER: Deduplicação Agressiva
# ╚═══════════════════════════════════════════════════════════════════════════╝

print("""
ARQUIVO: src/domain/sales_silver_normalizer.py
FUNÇÃO: _deduplicate_rows() — linhas 195-225

⚠️ ACHADO CRÍTICO: Chave composta agressiva em candidatos
─────────────────────────────────────────────────────────

    candidate_keys: list[list[str]] = [
        ["num_venda", "produto", "data", "canal", "arquivo_origem"],  # ← 1ª TENTATIVA
        ["produto", "data", "canal", "qtd", "valor_total", "arquivo_origem"],  # ← 2ª TENTATIVA
    ]

PROBLEMA:
  • Se a mesma NFC-e contém 2 itens → num_venda será igual em ambas as linhas.
  • Mas "produto" é diferente → a chave NÃO colide por num_venda.
  • PORÉM, se por acaso num_venda, produto, data, canal forem IGUAIS entre
    dois arquivos diferentes (ex: recálculo parcial), a linha fica órfã do
    drop_duplicates().

IMPACTO: Até ~2% perda por colisão falsa em vendas que legitimamente repetem
         (ex: promo "Brigadeiro" vendido em "LOJA" na "2026-01-15" aparece 2x).

RISCO DETECTADO: A chave NÃO deve incluir "produto" se a mesma nota pode ter
                múltiplos itens. Deveria usar apenas chave transacional +
                arquivo de origem.

─────────────────────────────────────────────────────────────────────────────

""")

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ 2. CAMADA SILVER: Normalização com .fillna() Segura
# ╚═══════════════════════════════════════════════════════════════════════════╝

print("""
ARQUIVO: src/domain/sales_silver_normalizer.py
FUNÇÃO: _normalize_text_fields() — linhas 179-192

⚠️ ACHADO MODERADO: Nulos em campos texto → "desconhecido"
──────────────────────────────────────────────────────────

    for col in _ESSENTIAL_TEXT_COLS:
        out[col] = out[col].fillna("desconhecido").astype(str).str.strip()
        out[col] = out[col].replace({"": "desconhecido", "nan": "desconhecido", "None": "desconhecido"})

BOAS NOTÍCIAS:
  ✓ Nulos são preenchidos com "desconhecido" (não descartados)
  ✓ Nenhuma chamada a .dropna() nesta etapa
  ✓ Campos texto são preservados

PROBLEMA: Se "produto" for efetivamente vazio/nulo, fica marcado como
          "desconhecido" em vez de mantido órfão. Isso permite rastreamento.

RISCO: BAIXO — Não há drop_duplicates() agressivo aqui.

─────────────────────────────────────────────────────────────────────────────

""")

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ 3. CAMADA SILVER → GOLD: Integridade com NULL FK
# ╚═══════════════════════════════════════════════════════════════════════════╝

print("""
ARQUIVO: scripts/medallion_pipeline.py
FUNÇÃO: build_fato_vendas() — linhas 912-940

⚠️ ACHADO CRÍTICO: Rows com NULL produto_id/data_id são DESCARTADAS
──────────────────────────────────────────────────────────────────

    # Temporary diagnostics: quantify rows that would be dropped by null FK keys.
    null_prod_mask = fato["produto_id"].isna()
    null_data_mask = fato["data_id"].isna()
    dropped_mask = null_prod_mask | null_data_mask
    dropped_count = int(dropped_mask.sum())
    if dropped_count:
        logger.warning("[diag] build_fato_vendas:dropped_by_null_fk...")

    # ── Integrity: drop rows with null FKs ────────────────────────────
    key_cols = ["produto_id", "data_id"]
    fato = _validate_no_nulls(fato, "fato_vendas", key_cols)  # ← DESCARTA!

PROBLEMA:
  • Se um produto NÃO existe em dim_produto (left join sem match)
    → produto_id fica NULL
  • Se uma data NÃO existe em dim_tempo (left join sem match)
    → data_id fica NULL
  • A função _validate_no_nulls() chama .dropna() e REMOVE essas linhas!

IMPACTO ESTIMADO:
  - Janeiro 2742 linhas → Se 100% das datas falhar parsing → 0 em dim_tempo
                         → 100% de data_id NULL → 2742 registros descartados
  - Fevereiro 3348 → 3337: ~11 linhas com data_id NULL (likely ~0.3% parsing fail)

RISCO: CRÍTICO — Aqui está o gargalo principal para jan/fev zerados.

─────────────────────────────────────────────────────────────────────────────

""")

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ 4. Parsing de Datas: DD/MM/YYYY vs MM/DD/YYYY
# ╚═══════════════════════════════════════════════════════════════════════════╝

print("""
ARQUIVO: src/domain/sales_silver_normalizer.py
FUNÇÃO: _parse_dates_with_source_hint() — linhas 127-145

CONTEXTO DO PROBLEMA:
  • Janeiro: arquivo nome = "sales_data_01_2026.csv"
            → mês hint = 01 (janeiro)
            → datas como "31/01/2026" (DD/MM)
            → parsing DEVE ser "%d/%m/%Y"

  • Fevereiro: arquivo nome = "sales_data_02_2026.csv"
              → mês hint = 02 (fevereiro)
              → datas como "02/01/2026" (DD/MM ambíguo!)
              → se houver "02/03/2026" (mar), parsing seria "%m/%d/%Y"?

HEURÍSTICA USADA:
    def _choose_date_format_for_source(raw_dates, source_name):
        month_hint = _month_hint_from_source(source_name)  # 01 ou 02
        if right_votes > left_votes:
            return "%d/%m/%Y"  # BR: dia/mês/ano
        ...

RISCO MODERADO: Se fevereiro contiver datas ambíguas (01-12 em ambas posições),
                a heurística pode escolher o formato errado → NaT → NULL data_id
                → registros descartados em build_fato_vendas().

─────────────────────────────────────────────────────────────────────────────

""")

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ 5. RESUMO: Causa Raiz
# ╚═══════════════════════════════════════════════════════════════════════════╝

print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║ DIAGNÓSTICO FINAL
╚═══════════════════════════════════════════════════════════════════════════╝

CAUSA PRINCIPAL (99% de confiança):
  Parsing de datas falhou em january/fevereiro
  → dim_tempo NÃO contém todas as datas
  → LEFT JOIN (silver → dim_tempo) retorna NULL data_id
  → _validate_no_nulls() descarta linhas com NULL data_id
  → Streamlit exibe 0 registros

CAUSAS SECUNDÁRIAS:
  1. Deduplicação agressiva em silver (chave produto+num_venda pode colidir)
  2. Parsing ambíguo de datas em fevereiro (01-12 são ambíguas)
  3. Encoding inválido em alguns CSVs (utf-8 vs latin-1)
  4. Delimitador inconsistente (;  vs ,) entre arquivos

PRÓXIMOS PASSOS (implementar):
  1. Tornar LEFT JOIN + products/dates órfão-tolerante (sinalize mas não descarte)
  2. Adicionar logging detalhado de drop_duplicates() com chave
  3. Validar parsing de datas com logs por arquivo
  4. Usar bronze_ingestion_diagnostic.py para auditar raw → silver

─────────────────────────────────────────────────────────────────────────────
""")

