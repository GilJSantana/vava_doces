#!/usr/bin/env python3
"""
Script para testar conexão com Google Sheets da Vava Doces
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_credentials_file():
    """Teste 1: Verificar se o arquivo de credenciais existe"""
    print("\n" + "="*60)
    print("TESTE 1: Arquivo de Credenciais")
    print("="*60)

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"📍 Caminho esperado: {cred_path}")

    if Path(cred_path).exists():
        print(f"✅ SUCESSO: Arquivo de credenciais encontrado!")
        return True
    else:
        print(f"❌ ERRO: Arquivo de credenciais NÃO encontrado")
        print(f"\n💡 Solução:")
        print(f"   1. Crie o diretório: mkdir -p credencial")
        print(f"   2. Copie seu arquivo JSON para: {cred_path}")
        return False

def test_sheet_id():
    """Teste 2: Verificar ID da planilha"""
    print("\n" + "="*60)
    print("TESTE 2: ID da Planilha")
    print("="*60)

    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    print(f"📍 Valor configurado: {sheet_id}")

    if sheet_id and len(sheet_id.strip()) > 20:  # IDs do Google Sheets geralmente tem esse tamanho
        print(f"✅ SUCESSO: Sheet ID parece válido")
        return True
    else:
        print(f"❌ ERRO: Sheet ID inválido ou não configurado")
        return False

def test_google_sheets_connection():
    """Teste 3: Conectar com Google Sheets"""
    print("\n" + "="*60)
    print("TESTE 3: Conexão com Google Sheets")
    print("="*60)

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not Path(cred_path).exists():
        print(f"⏭️  PULADO: Arquivo de credenciais não encontrado")
        return False

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        print("📦 Importando bibliotecas...")
        print("   ✅ gspread")
        print("   ✅ google.oauth2")

        # Carregar credenciais
        print(f"\n🔑 Carregando credenciais de: {cred_path}")
        credentials = Credentials.from_service_account_file(
            cred_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        print("✅ Credenciais carregadas com sucesso")

        # Criar cliente
        print("\n🌐 Conectando ao Google Sheets...")
        client = gspread.authorize(credentials)
        print("✅ Cliente autorizado com sucesso")

        # Tentar abrir a planilha
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        # Extrair ID da URL se necessário
        if "spreadsheets/d/" in sheet_id:
            sheet_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]

        print(f"\n📂 Abrindo planilha com ID: {sheet_id}")
        spreadsheet = client.open_by_key(sheet_id)
        print(f"✅ Planilha aberta: {spreadsheet.title}")

        # Listar abas
        print(f"\n📊 Abas encontradas:")
        for i, sheet in enumerate(spreadsheet.worksheets(), 1):
            print(f"   {i}. {sheet.title} ({sheet.row_count}x{sheet.col_count} células)")

        return True

    except FileNotFoundError as e:
        print(f"❌ ERRO: Arquivo de credenciais não encontrado: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        return False

def main():
    """Executar todos os testes"""
    print("\n" + "="*60)
    print("🔍 TESTE DE CONEXÃO - Vava Doces Google Sheets")
    print("="*60)

    results = []

    # Teste 1
    results.append(("Arquivo de Credenciais", test_credentials_file()))

    # Teste 2
    results.append(("ID da Planilha", test_sheet_id()))

    # Teste 3
    results.append(("Conexão Google Sheets", test_google_sheets_connection()))

    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{name:.<40} {status}")

    print(f"\n🎯 Total: {passed}/{total} testes passaram")

    if passed == total:
        print("\n🎉 SUCESSO! Sua conexão com Google Sheets está funcionando!")
        return 0
    elif passed == total - 1 and not results[2][1]:
        print("\n⚠️  Arquivo de credenciais ainda não foi adicionado.")
        print("   Así que a conexão Google Sheets não pôde ser testada.")
        print("   Execute este teste novamente após adicionar o arquivo.")
        return 1
    else:
        print("\n❌ Há problemas que precisam ser corrigidos.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

