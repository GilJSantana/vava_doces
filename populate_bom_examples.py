#!/usr/bin/env python3
"""
Script para popular a aba 'Ficha Técnica' com dados de exemplo.

Este script:
1. Conecta ao Google Sheets.
2. Lê dados de 'Cadastro Produtos' e 'Matéria Prima'.
3. Cria linhas de exemplo na aba 'Ficha Técnica' (algumas receitas com ingredientes).
4. Permite validar a integração antes de dados reais.

Execução:
  python populate_bom_examples.py

Pré-requisitos:
  - Aba 'Ficha Técnica' já criada (execute create_bom_sheet.py primeiro).
  - 'Cadastro Produtos' e 'Matéria Prima' preenchidos com dados.
  - Variável de ambiente GOOGLE_SHEET_ID definida.
"""

import os
import gspread
import pandas as pd
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração
CREDENTIAL_FILE = "./credencial/vava-doces-0667d5821bd5.json"
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Ficha Técnica"

def populate_bom_examples():
    """Popula a aba Ficha Técnica com exemplos."""
    try:
        print(f"🔑 Conectando ao Google Sheets...")
        client = gspread.service_account(filename=CREDENTIAL_FILE)
        spreadsheet = client.open_by_key(SHEET_ID)

        # Ler dados existentes
        print(f"📖 Lendo 'Cadastro Produtos'...")
        try:
            produtos_ws = spreadsheet.worksheet("Cadastro Produtos")
            produtos_data = produtos_ws.get_all_records()
            print(f"   ✅ {len(produtos_data)} produtos lidos")
        except Exception as e:
            print(f"   ⚠️  Erro ao ler 'Cadastro Produtos': {e}")
            produtos_data = []

        print(f"📖 Lendo 'Matéria Prima'...")
        try:
            materias_ws = spreadsheet.worksheet("Matéria Prima")
            materias_data = materias_ws.get_all_records()
            print(f"   ✅ {len(materias_data)} itens de matéria prima lidos")
        except Exception as e:
            print(f"   ⚠️  Erro ao ler 'Matéria Prima': {e}")
            materias_data = []

        # Abrir aba Ficha Técnica
        print(f"📝 Abrindo aba '{SHEET_NAME}'...")
        bom_ws = spreadsheet.worksheet(SHEET_NAME)

        # Limpar dados existentes (exceto header)
        # Nota: worksheet.clear() remove tudo; queremos manter header
        print(f"🧹 Limpando dados antigos (mantendo header)...")
        all_values = bom_ws.get_all_values()
        if len(all_values) > 1:
            bom_ws.delete_rows(2, len(all_values))  # Deletar de linha 2 até o final

        # Preparar exemplos (dados de teste)
        print(f"📊 Preparando dados de exemplo...")
        examples = []

        # Se houver produtos e matérias, criar relações de exemplo
        if produtos_data and materias_data:
            # Exemplo 1: Primeiro produto com primeiros 2 ingredientes
            if len(produtos_data) > 0 and len(materias_data) >= 2:
                product = produtos_data[0]
                product_name = product.get("Produto") or product.get("Nome") or "Produto 1"
                product_id = product.get("ProductID") or product.get("ID") or "P001"

                # Ingrediente 1
                mat1 = materias_data[0]
                ing1_name = mat1.get("Ingrediente") or mat1.get("Nome") or "Ingrediente 1"
                ing1_id = mat1.get("IngredientID") or mat1.get("ID") or "I001"
                ing1_price = mat1.get("Preço") or mat1.get("Price") or 10.0

                examples.append([
                    product_id,
                    product_name,
                    ing1_id,
                    ing1_name,
                    0.1,  # QtyPerProduct
                    "kg",  # QtyUnit
                    ing1_price,
                    "BRL",
                    "",  # Supplier
                    "Exemplo de integração",
                    "2026-02-26"
                ])

                # Ingrediente 2
                if len(materias_data) > 1:
                    mat2 = materias_data[1]
                    ing2_name = mat2.get("Ingrediente") or mat2.get("Nome") or "Ingrediente 2"
                    ing2_id = mat2.get("IngredientID") or mat2.get("ID") or "I002"
                    ing2_price = mat2.get("Preço") or mat2.get("Price") or 5.0

                    examples.append([
                        product_id,
                        product_name,
                        ing2_id,
                        ing2_name,
                        0.2,
                        "kg",
                        ing2_price,
                        "BRL",
                        "",
                        "Exemplo de integração",
                        "2026-02-26"
                    ])
        else:
            # Dados de exemplo genéricos (se não houver produtos/materias)
            examples = [
                ["P001", "Bolo de Chocolate", "I001", "Chocolate em pó", 0.1, "kg", 20.0, "BRL", "FornA", "Exemplo", "2026-02-26"],
                ["P001", "Bolo de Chocolate", "I002", "Açúcar", 0.2, "kg", 5.0, "BRL", "FornB", "Exemplo", "2026-02-26"],
                ["P002", "Brigadeiro", "I001", "Chocolate em pó", 0.3, "kg", 20.0, "BRL", "FornA", "Exemplo", "2026-02-26"],
                ["P002", "Brigadeiro", "I003", "Leite Condensado", 0.4, "un", 3.5, "BRL", "FornC", "Exemplo", "2026-02-26"],
            ]

        # Adicionar exemplos à aba
        if examples:
            print(f"📝 Adicionando {len(examples)} linhas de exemplo...")
            bom_ws.append_rows(examples)
            print(f"   ✅ {len(examples)} linhas adicionadas!")
        else:
            print(f"   ⚠️  Nenhum exemplo para adicionar")

        print(f"\n✅ População completa!")
        print(f"\n💡 Próximos passos:")
        print(f"   1. Acesse a planilha no Google Sheets")
        print(f"   2. Revise a aba '{SHEET_NAME}'")
        print(f"   3. Ajuste os dados conforme necessário")
        print(f"   4. Execute: python -c \"from src.domain.cost_analysis_service import CostAnalysisService; ...\" para testar")

    except Exception as e:
        print(f"❌ ERRO: {e}")

if __name__ == "__main__":
    if not SHEET_ID:
        print("❌ ERRO: GOOGLE_SHEET_ID não configurado.")
        exit(1)

    populate_bom_examples()

