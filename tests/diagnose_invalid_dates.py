#!/usr/bin/env python3
"""
DIAGNÓSTICO PROFUNDO: Investigando os 1900 registros com datas inválidas
"""

import os
import pandas as pd
from dotenv import load_dotenv
from src.domain.sales_analysis_service import SalesETLPipeline, _parse_sales_date

def diagnose_invalid_dates():
    """Identifica por que 1900+ registros têm datas inválidas."""
    
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO PROFUNDO: Datas Inválidas")
    print("="*80)
    
    load_dotenv()
    pipeline = SalesETLPipeline.from_env()
    raw_sales = pipeline._sales_extractor.extract()
    
    if raw_sales.empty:
        print("❌ Sem dados")
        return
    
    # Encontrar coluna de data
    data_col = None
    for col in ["data", "data_da_venda", "data_venda", "Date"]:
        if col in raw_sales.columns:
            data_col = col
            break
    
    if not data_col:
        print("❌ Coluna de data não encontrada")
        return
    
    print(f"\n✅ Usando coluna: '{data_col}'")
    
    raw_dates = raw_sales[data_col].astype(str).str.strip()
    
    # Tentar parsing US
    parsed = pd.to_datetime(raw_dates, format="%m/%d/%Y", errors="coerce")
    
    # Agora aplicar a nova função com fallback BR
    from src.domain.sales_analysis_service import _parse_sales_date
    parsed_new = _parse_sales_date(raw_dates)
    
    # Encontrar inválidos
    invalid_mask = parsed.isna()
    invalid_dates = raw_dates[invalid_mask]
    
    print(f"\n📊 ESTATÍSTICAS:")
    print(f"   Total de registros: {len(raw_dates)}")
    print(f"   Datas válidas (US apenas): {(~invalid_mask).sum()}")
    print(f"   Datas inválidas (US apenas): {invalid_mask.sum()}")
    
    # Com a nova função
    invalid_mask_new = parsed_new.isna()
    print(f"\n   Após aplicar fallback BR:")
    print(f"   Datas válidas (US + BR): {(~invalid_mask_new).sum()}")
    print(f"   Datas inválidas (ainda): {invalid_mask_new.sum()}")
    
    # Amostra dos inválidos
    print(f"\n📋 AMOSTRA DE DATAS INVÁLIDAS (primeiras 20):")
    for i, date_str in enumerate(invalid_dates.head(20)):
        print(f"  {i+1:2d}. '{date_str}'")
    
    # Análise de padrões
    print(f"\n🔎 ANÁLISE DE PADRÕES NAS DATAS INVÁLIDAS:")
    
    # Contagem de linhas em branco
    blank_count = (raw_dates[invalid_mask] == "").sum()
    print(f"   Linhas em branco: {blank_count}")
    
    # Linhas com "nan"
    nan_count = (raw_dates[invalid_mask] == "nan").sum()
    print(f"   Valores 'nan': {nan_count}")
    
    # Linhas com "None"
    none_count = (raw_dates[invalid_mask] == "None").sum()
    print(f"   Valores 'None': {none_count}")
    
    # Outras datas inválidas (que têm valor mas não parseiam)
    other_invalid = invalid_dates[
        ~invalid_dates.isin(["", "nan", "None"])
    ]
    print(f"   Outras datas inválidas (com valor): {len(other_invalid)}")
    
    if len(other_invalid) > 0:
        print(f"\n   Exemplos de datas com valor mas inválidas (primeiras 10):")
        for i, date_str in enumerate(other_invalid.head(10)):
            print(f"      {i+1}. '{date_str}'")
    
    # Verificar se há padrão de fecha incorreta
    print(f"\n📌 VERIFICANDO PADRÕES DE FORMATAÇÃO:")
    
    # Tentar BR (dd/mm/yyyy)
    parsed_br = pd.to_datetime(raw_dates[invalid_mask], format="%d/%m/%Y", errors="coerce")
    valid_br = parsed_br.notna().sum()
    print(f"   Se forem dd/mm/yyyy: {valid_br} seriam válidas")
    
    # Tentar YYYY-MM-DD
    parsed_iso = pd.to_datetime(raw_dates[invalid_mask], format="%Y-%m-%d", errors="coerce")
    valid_iso = parsed_iso.notna().sum()
    print(f"   Se forem yyyy-mm-dd: {valid_iso} seriam válidas")
    
    # Tentar YYYY/MM/DD
    parsed_iso2 = pd.to_datetime(raw_dates[invalid_mask], format="%Y/%m/%d", errors="coerce")
    valid_iso2 = parsed_iso2.notna().sum()
    print(f"   Se forem yyyy/mm/dd: {valid_iso2} seriam válidas")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    diagnose_invalid_dates()



