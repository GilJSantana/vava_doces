#!/usr/bin/env python3
"""
Script para converter planilha Excel para Google Sheets nativo
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def convert_to_native_sheets():
    """Converter arquivo Excel para Google Sheets nativo"""
    print("\n" + "="*70)
    print("🔄 CONVERTER EXCEL PARA GOOGLE SHEETS NATIVO")
    print("="*70)

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
        import urllib3
        import json

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID").strip()

        print(f"\n📋 Informações:")
        print(f"   ID: {sheet_id}")
        print(f"   Nome: Controle-de-Vendas-Doceria.xlsx")
        print(f"   Tipo: Excel (importado)")

        # Carregar credenciais
        credentials = Credentials.from_service_account_file(
            cred_path,
            scopes=[
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
        )

        request = Request()
        credentials.refresh(request)

        print(f"\n🔧 Soluções:")
        print(f"\n   Opção 1: Converter via Google Drive (Recomendado)")
        print(f"   -" * 35)
        print(f"   1. Abra o arquivo no Google Drive")
        print(f"   2. Clique com botão direito → \"Abrir com\" → \"Google Sheets\"")
        print(f"   3. Confirme a conversão")
        print(f"   4. Agora é um arquivo nativo de Google Sheets")

        print(f"\n   Opção 2: Recrie a planilha no Google Sheets")
        print(f"   -" * 35)
        print(f"   1. Vá para https://sheets.google.com")
        print(f"   2. Crie uma nova planilha")
        print(f"   3. Importe os dados do Excel")
        print(f"   4. Copie o novo ID para o .env")

        print(f"\n   Opção 3: Compartilhe e tente novamente")
        print(f"   -" * 35)
        print(f"   1. Certifique-se que compartilhou a planilha")
        print(f"   2. Service Account: vava-doces@...iam.gserviceaccount.com")
        print(f"   3. Permissão: Visualizador")

        return False

    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    convert_to_native_sheets()

    print("\n" + "="*70)
    print("💡 EXPLICAÇÃO:")
    print("="*70)
    print("""
O arquivo que você tem é um EXCEL importado para o Google Drive,
não um Google Sheets nativo.

gspread trabalha com Google Sheets nativos, não com Excel.

RECOMENDAÇÃO:
   → Converta para Google Sheets nativo (Opção 1 acima)
   → Depois teste novamente
    """)
    print("="*70 + "\n")

