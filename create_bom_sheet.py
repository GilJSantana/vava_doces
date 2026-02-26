#!/usr/bin/env python3
"""
Script para criar a aba 'Ficha Técnica' no Google Sheets da Vava Doces.

Este script:
1. Conecta ao Google Sheets usando credenciais de service account.
2. Cria a aba 'Ficha Técnica' se não existir.
3. Adiciona as colunas necessárias (headers).
4. Formata a aba (cores, largura de colunas, etc).

Execução:
  python create_bom_sheet.py

Pré-requisitos:
  - Arquivo de credenciais em ./credencial/vava-doces-*.json
  - Variável de ambiente GOOGLE_SHEET_ID definida ou presente em .env
"""

import os
import gspread
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração
CREDENTIAL_FILE = "./credencial/vava-doces-0667d5821bd5.json"
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Ficha Técnica"

# Colunas da aba (headers)
HEADERS = [
    "ProductID",
    "ProductName",
    "IngredientID",
    "IngredientName",
    "QtyPerProduct",
    "QtyUnit",
    "UnitCost",
    "UnitCurrency",
    "Supplier",
    "Notes",
    "LastUpdated"
]

def create_bom_sheet():
    """Cria a aba Ficha Técnica no Google Sheets."""
    try:
        print(f"🔑 Conectando ao Google Sheets usando credenciais: {CREDENTIAL_FILE}")
        client = gspread.service_account(filename=CREDENTIAL_FILE)

        print(f"📂 Abrindo planilha com ID: {SHEET_ID}")
        spreadsheet = client.open_by_key(SHEET_ID)

        # Verificar se a aba já existe
        try:
            worksheet = spreadsheet.worksheet(SHEET_NAME)
            print(f"⚠️  Aba '{SHEET_NAME}' já existe. Pulando criação.")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"✅ Aba '{SHEET_NAME}' não encontrada. Criando...")
            worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
            print(f"✅ Aba '{SHEET_NAME}' criada com sucesso!")

        # Adicionar headers
        print(f"📝 Adicionando headers: {HEADERS}")
        worksheet.append_row(HEADERS)

        # Formatar a aba (opcional: cores, congelamento, etc)
        print(f"🎨 Formatando aba...")
        # Congelar primeira linha (headers)
        worksheet.freeze_rows(1)

        # Ajustar largura de colunas (algumas colunas são mais largas)
        worksheet.batch_update([
            {
                'updateDimensionProperties': {
                    'range': {'sheetId': worksheet.id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1},
                    'properties': {'pixelSize': 100},
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {'sheetId': worksheet.id, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 2},
                    'properties': {'pixelSize': 200},
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {'sheetId': worksheet.id, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': 4},
                    'properties': {'pixelSize': 200},
                    'fields': 'pixelSize'
                }
            }
        ])

        print(f"✅ Aba '{SHEET_NAME}' criada e formatada com sucesso!")
        print(f"\n📊 Estrutura da aba:")
        print(f"  Headers: {', '.join(HEADERS)}")
        print(f"  Total de colunas: {len(HEADERS)}")
        print(f"  Linhas disponíveis: 1000")
        print(f"\n💡 Próximo passo: preencha a aba manualmente ou use o script populate_bom_examples.py")

        return worksheet

    except FileNotFoundError:
        print(f"❌ ERRO: Arquivo de credenciais não encontrado: {CREDENTIAL_FILE}")
        print(f"   Certifique-se de ter o arquivo JSON no diretório correto.")
        return None
    except Exception as e:
        print(f"❌ ERRO ao criar aba: {e}")
        return None

if __name__ == "__main__":
    if not SHEET_ID:
        print("❌ ERRO: GOOGLE_SHEET_ID não configurado. Defina a variável de ambiente ou adicione ao .env")
        exit(1)

    create_bom_sheet()

