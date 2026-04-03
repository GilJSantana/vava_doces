#!/usr/bin/env python3
"""
TESTE DE VALIDAÇÃO: Filtro de datas funciona corretamente
"""

import os
import pandas as pd
from datetime import date
from dotenv import load_dotenv
from src.domain.sales_analysis_service import SalesETLPipeline

def test_date_filtering():
    """Testa se os filtros de data funcionam corretamente."""
    
    print("\n" + "="*80)
    print("🧪 TESTE: Filtro de Datas")
    print("="*80)
    
    load_dotenv()
    pipeline = SalesETLPipeline.from_env()
    df = pipeline.run()
    
    print(f"\n📊 Total de registros: {len(df)}")
    print(f"   Datas válidas: {df['data'].notna().sum()}")
    
    # Teste 1: Janeiro
    jan_df = df[
        (df['data'] >= pd.Timestamp('2026-01-01')) &
        (df['data'] <= pd.Timestamp('2026-01-31'))
    ]
    print(f"\n✅ JANEIRO 2026: {len(jan_df)} registros")
    assert len(jan_df) > 0, "Nenhum registro em janeiro"

    # Teste 2: Fevereiro
    fev_df = df[
        (df['data'] >= pd.Timestamp('2026-02-01')) &
        (df['data'] <= pd.Timestamp('2026-02-28'))
    ]
    print(f"✅ FEVEREIRO 2026: {len(fev_df)} registros")
    assert len(fev_df) > 0, "Nenhum registro em fevereiro"

    # Teste 3: Ambos meses
    ambos = df[
        (df['data'] >= pd.Timestamp('2026-01-01')) &
        (df['data'] <= pd.Timestamp('2026-02-28'))
    ]
    print(f"✅ JANEIRO + FEVEREIRO: {len(ambos)} registros")
    assert len(ambos) == (len(jan_df) + len(fev_df)), "Soma inconsistente"
    
    # Teste 4: Período inválido (março e além)
    mar_plus = df[
        (df['data'] >= pd.Timestamp('2026-03-01')) &
        (df['data'] <= pd.Timestamp('2026-12-31'))
    ]
    print(f"✅ MARÇO~DEZEMBRO 2026: {len(mar_plus)} registros")
    
    # Teste 5: Total (excluding rows with invalid/NaT dates)
    valid_df = df[df['data'].notna()]
    total_2026 = valid_df[valid_df['data'].dt.year == 2026]
    print(f"✅ TOTAL 2026: {len(total_2026)} registros (de {len(valid_df)} datas válidas)")
    assert len(total_2026) == len(valid_df), "Todos os registros com data válida devem ser de 2026"

    print(f"\n🎉 TODOS OS TESTES PASSARAM!")
    print(f"\n📈 RESUMO:")
    print(f"   Janeiro:     {len(jan_df):>6} registros")
    print(f"   Fevereiro:   {len(fev_df):>6} registros")
    print(f"   Outros:      {len(mar_plus):>6} registros")
    print(f"   {'─'*35}")
    print(f"   Total:       {len(df):>6} registros")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    test_date_filtering()

