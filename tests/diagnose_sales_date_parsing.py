#!/usr/bin/env python3
"""
DIAGNÓSTICO COMPLETO: Bug de Parsing de Datas no módulo de Faturamento
=======================================================================

Objetivo: Identificar por que registros de janeiro estão sendo misparsed
          causando filtros incorretos.

Execução: python tests/diagnose_sales_date_parsing.py
"""

import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from src.domain.sales_analysis_service import SalesETLPipeline

def diagnose_date_parsing():
    """Executa diagnóstico completo do parsing de datas."""
    
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO COMPLETO: PARSING DE DATAS")
    print("="*80)
    
    # Carregar pipeline
    try:
        load_dotenv()
        pipeline = SalesETLPipeline.from_env()
        print("✅ Pipeline inicializado")
    except Exception as e:
        print(f"❌ Erro ao inicializar pipeline: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Extrair dados brutos (SEM transformação)
    try:
        extractor_sales = pipeline._sales_extractor
        raw_sales = extractor_sales.extract()
    except Exception as e:
        print(f"❌ Erro ao extrair dados de vendas: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if raw_sales.empty:
        print("❌ Nenhum arquivo de vendas encontrado")
        return
    
    print(f"\n📊 TOTAL DE REGISTROS CARREGADOS: {len(raw_sales)}")
    print(f"📁 COLUNAS: {list(raw_sales.columns)}")
    
    # ========================================================================
    # FASE 1: INSPEÇÃO DE DADOS BRUTOS
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 1: INSPEÇÃO DE DADOS BRUTOS")
    print("="*80)
    
    # Detectar coluna de data (pode ser 'data', 'data_da_venda', etc)
    data_col = None
    for col in ["data", "data_da_venda", "data_venda", "Date"]:
        if col in raw_sales.columns:
            data_col = col
            break
    
    if data_col is None:
        print("❌ Coluna de data não encontrada")
        print(f"   Colunas disponíveis: {list(raw_sales.columns)}")
        return
    
    print(f"✅ Usando coluna de data: '{data_col}'")
    raw_dates = raw_sales[data_col].astype(str).str.strip()
    
    print("\n📋 AMOSTRA DAS PRIMEIRAS 10 DATAS (formato bruto do arquivo):")
    for i, date_str in enumerate(raw_dates.head(10)):
        print(f"  {i+1:2d}. '{date_str}'")
    
    # Extrair mês direto da string (antes do primeiro '/')
    mes_string_raw = pd.to_numeric(raw_dates.str.split("/").str[0], errors="coerce")
    mes_counts = mes_string_raw.value_counts(dropna=False).sort_index()
    
    print("\n🔢 DISTRIBUIÇÃO DE MESES (extraído direto da string - primeiro token):")
    for mes, count in mes_counts.items():
        if pd.isna(mes):
            mes_name = "Inválido"
            mes_val = "N/A"
        else:
            mes_val = int(mes)
            mes_name = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho"}.get(mes_val, "Outro")
        print(f"  Mês {mes_val:>2} ({mes_name:>10}): {count:>6} registros")
    
    # ========================================================================
    # FASE 2: COMPARAÇÃO DE FORMATOS DE PARSING
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 2: COMPARAÇÃO DE FORMATOS DE PARSING")
    print("="*80)
    
    # Teste 1: Formato US (mm/dd/yyyy)
    parsed_us = pd.to_datetime(raw_dates, format="%m/%d/%Y", errors="coerce")
    count_us_valid = parsed_us.notna().sum()
    
    # Teste 2: Formato BR (dd/mm/yyyy)
    parsed_br = pd.to_datetime(raw_dates, format="%d/%m/%Y", errors="coerce")
    count_br_valid = parsed_br.notna().sum()
    
    # Teste 3: Parsing automático (sem format especificado)
    parsed_auto = pd.to_datetime(raw_dates, errors="coerce")
    count_auto_valid = parsed_auto.notna().sum()
    
    print(f"\n✅ Formato US   (mm/dd/yyyy): {count_us_valid:>5} datas válidas ({100*count_us_valid/len(raw_dates):>5.1f}%)")
    print(f"✅ Formato BR   (dd/mm/yyyy): {count_br_valid:>5} datas válidas ({100*count_br_valid/len(raw_dates):>5.1f}%)")
    print(f"✅ Parsing AUTO (inferido):   {count_auto_valid:>5} datas válidas ({100*count_auto_valid/len(raw_dates):>5.1f}%)")
    
    # ========================================================================
    # FASE 3: DISTRIBUIÇÃO MENSAL POR FORMATO
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 3: DISTRIBUIÇÃO MENSAL POR FORMATO")
    print("="*80)
    
    if count_us_valid > 0:
        mes_us = parsed_us.dt.month.value_counts(dropna=False).sort_index()
        print(f"\n📅 Meses identificados (Formato US mm/dd/yyyy):")
        for mes, count in mes_us.items():
            if pd.isna(mes):
                mes_name = "Inválido"
                mes_val = "N/A"
            else:
                mes_val = int(mes)
                mes_name = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho"}.get(mes_val, "Outro")
            print(f"  Mês {mes_val:>2} ({mes_name:>10}): {count:>6} registros")
    
    if count_auto_valid > 0:
        mes_auto = parsed_auto.dt.month.value_counts(dropna=False).sort_index()
        print(f"\n📅 Meses identificados (Parsing AUTO):")
        for mes, count in mes_auto.items():
            if pd.isna(mes):
                mes_name = "Inválido"
                mes_val = "N/A"
            else:
                mes_val = int(mes)
                mes_name = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho"}.get(mes_val, "Outro")
            print(f"  Mês {mes_val:>2} ({mes_name:>10}): {count:>6} registros")
    
    # ========================================================================
    # FASE 4: TESTE ISOLADO - JANEIRO E FEVEREIRO 2026
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 4: TESTE ISOLADO - JANEIRO E FEVEREIRO 2026")
    print("="*80)
    
    jan_us = ((parsed_us >= "2026-01-01") & (parsed_us <= "2026-01-31")).sum()
    jan_auto = ((parsed_auto >= "2026-01-01") & (parsed_auto <= "2026-01-31")).sum()
    
    fev_us = ((parsed_us >= "2026-02-01") & (parsed_us <= "2026-02-28")).sum()
    fev_auto = ((parsed_auto >= "2026-02-01") & (parsed_auto <= "2026-02-28")).sum()
    
    print(f"\n📆 Registros em JANEIRO 2026:")
    print(f"  Formato US   (mm/dd/yyyy): {jan_us:>6} registros")
    print(f"  Parsing AUTO (inferido):   {jan_auto:>6} registros")
    
    print(f"\n📆 Registros em FEVEREIRO 2026:")
    print(f"  Formato US   (mm/dd/yyyy): {fev_us:>6} registros")
    print(f"  Parsing AUTO (inferido):   {fev_auto:>6} registros")
    print(f"  Esperado (referência):     ~3348 registros")
    
    # Análise
    if fev_us == 0 and fev_auto > 100:
        print(f"\n❌ CRÍTICO: Parsing US retorna 0 registros em FEV, mas AUTO retorna {fev_auto}")
        print("   → Provavelmente o CSV está em formato DD/MM/YYYY, não MM/DD/YYYY")
    elif fev_us > 100:
        print(f"\n✅ OK: Formato US retorna {fev_us} registros em fevereiro")
    elif fev_auto > 100 and fev_us == 0:
        print(f"\n⚠️  PROBLEMA IDENTIFICADO: Parsing automático melhor que US")
        print(f"   Fevereiro AUTO: {fev_auto} | US: {fev_us}")
    else:
        print(f"\n⚠️  ATENÇÃO: Ambos formatos retornam poucos registros")
    
    # ========================================================================
    # FASE 5: AMOSTRA COM DATAS PARSEADAS
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 5: AMOSTRA - COMPARAÇÃO DE PARSING")
    print("="*80)
    
    sample_df = pd.DataFrame({
        "data_raw": raw_dates.head(15).values,
        "data_us": parsed_us.head(15).values,
        "data_auto": parsed_auto.head(15).values,
    })
    
    print("\n📋 Primeiras 15 datas com 3 interpretações:\n")
    for idx, row in sample_df.iterrows():
        print(f"{idx+1:2d}. Raw: '{row['data_raw']:12}' → US: {str(row['data_us'])[:10]:12} | AUTO: {str(row['data_auto'])[:10]:12}")
    
    # ========================================================================
    # FASE 6: EXECUTAR PIPELINE COMPLETO
    # ========================================================================
    print("\n" + "="*80)
    print("FASE 6: PIPELINE COMPLETO (ETL)")
    print("="*80)
    
    try:
        df_final = pipeline.run()
        print(f"\n✅ Pipeline executado com sucesso")
        print(f"   Total de registros: {len(df_final)}")
        
        if "data" in df_final.columns:
            valid_dates = df_final["data"].notna().sum()
            invalid_dates = df_final["data"].isna().sum()
            print(f"   Datas válidas: {valid_dates} ({100*valid_dates/len(df_final):.1f}%)")
            print(f"   Datas inválidas: {invalid_dates} ({100*invalid_dates/len(df_final):.1f}%)")
            
            # Distribuição mensal final
            if valid_dates > 0:
                mes_final = df_final["data"].dt.month.value_counts(dropna=False).sort_index()
                print(f"\n   Distribuição mensal (após pipeline):")
                for mes, count in mes_final.items():
                    if pd.isna(mes):
                        mes_name = "Inválido"
                        mes_val = "N/A"
                    else:
                        mes_val = int(mes)
                        mes_name = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho"}.get(mes_val, "Outro")
                    print(f"     Mês {mes_val:>2} ({mes_name:>10}): {count:>6} registros")
    
    except Exception as e:
        print(f"❌ Erro ao executar pipeline: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================================================
    # CONCLUSÕES E RECOMENDAÇÕES
    # ========================================================================
    print("\n" + "="*80)
    print("CONCLUSÕES E RECOMENDAÇÕES")
    print("="*80)
    
    if count_us_valid > count_auto_valid and count_us_valid > len(raw_sales) * 0.9:
        print("""
✅ CONCLUSÃO: Parsing US (mm/dd/yyyy) é correto e eficiente

RECOMENDAÇÃO: O código atual em sales_analysis_service.py está correto.
Se os filtros ainda estão falhando, o problema pode estar em:

1. Cache do Streamlit não sendo limpo entre execuções
2. Inconsistência nos dados do Google Drive (arquivos com formatos diferentes)
3. Lógica de filtro com implementação incorreta
""")
    elif count_auto_valid > count_us_valid:
        print(f"""
⚠️  CONCLUSÃO: Parsing automático retorna mais datas válidas ({count_auto_valid}) 
que US ({count_us_valid})

RECOMENDAÇÃO: Ajustar _parse_sales_date() em sales_analysis_service.py para usar
parsing automático ou detectar o verdadeiro formato.

AÇÃO: Refatorar função _parse_sales_date() para usar:
  df["data"] = pd.to_datetime(series, errors="coerce")
""")
    else:
        print("""
❌ PROBLEMA CRÍTICO: Nenhum formato está parseando corretamente

RECOMENDAÇÃO: 
1. Verificar o formato exato no CSV (pode ser YYYY-MM-DD ou outro)
2. Inspecionar alguns valores brutos da coluna 'data'
3. Ajustar o _parse_sales_date() com base no formato real
""")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    diagnose_date_parsing()


