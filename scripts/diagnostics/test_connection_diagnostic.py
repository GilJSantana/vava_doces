#!/usr/bin/env python3
"""
Script para diagnosticar e corrigir problemas de conexão com Google Sheets
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


def extract_sheet_id(url):
    """Extrair ID da planilha de uma URL"""
    # Padrão 1: URL completa
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    # Padrão 2: Apenas o ID
    if re.match(r'^[a-zA-Z0-9-_]+$', url):
        return url
    return None


def test_sheet_access():
    """Testar acesso à planilha e listar informações"""
    print("\n" + "="*70)
    print("🔍 DIAGNÓSTICO DE CONEXÃO - Google Sheets")
    print("="*70)

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_url = os.getenv("GOOGLE_SHEET_ID")

        print(f"\n📋 Configurações:")
        print(f"   Arquivo de credenciais: {cred_path}")
        print(f"   URL/ID da planilha: {sheet_url}")

        # Verificar arquivo de credenciais
        assert cred_path is not None, "GOOGLE_APPLICATION_CREDENTIALS não definido"
        if not Path(cred_path).exists():
            print(f"\n❌ ERRO: Arquivo de credenciais não encontrado!")
            assert False, "Arquivo de credenciais não encontrado"

        print(f"\n✅ Arquivo de credenciais encontrado")

        # Extrair ID
        sheet_id = extract_sheet_id(sheet_url)
        if not sheet_id:
            print(f"❌ ERRO: Não consegui extrair o ID da planilha da URL")
            print(f"   A URL deve conter: /spreadsheets/d/[ID]/")
            assert False, "Não foi possível extrair ID da planilha"

        print(f"✅ ID da planilha extraído: {sheet_id}")

        # Carregar credenciais
        print(f"\n🔑 Carregando credenciais...")
        credentials = Credentials.from_service_account_file(
            cred_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        print(f"✅ Credenciais carregadas")

        # Criar cliente
        print(f"\n🌐 Conectando ao Google Sheets API...")
        client = gspread.authorize(credentials)
        print(f"✅ Cliente autorizado")

        # Tentar diferentes formas de acesso
        print(f"\n📂 Tentando acessar a planilha...")

        try:
            # Tentativa 1: Abrir por ID
            spreadsheet = client.open_by_key(sheet_id)
            print(f"✅ Planilha acessada com sucesso!")
            print(f"   Título: {spreadsheet.title}")

            # Listar abas
            print(f"\n📊 Abas encontradas:")
            for i, sheet in enumerate(spreadsheet.worksheets(), 1):
                print(f"   {i}. '{sheet.title}'")
                # Mostrar primeiras 3 linhas
                try:
                    values = sheet.get_values(f'A1:C3')
                    if values:
                        print(f"      Dados (amostra):")
                        for row in values[:2]:
                            print(f"         {row}")
                except Exception as e:
                    print(f"      (Não consegui ler dados: {e})")

            return True

        except gspread.exceptions.APIError as e:
            error_msg = str(e)
            print(f"❌ ERRO ao acessar: {error_msg}")

            if "404" in error_msg or "not found" in error_msg:
                print(f"\n💡 Solução:")
                print(f"   - O ID da planilha pode estar incorreto")
                print(f"   - Verifique se a Service Account tem acesso à planilha")
                print(f"   - Você pode ter que compartilhar a planilha com o email da Service Account")
            elif "permission denied" in error_msg.lower():
                print(f"\n💡 Solução:")
                print(f"   - A Service Account não tem permissão de acesso")
                print(f"   - Compartilhe a planilha com o email da Service Account:")
                try:
                    creds_json = open(cred_path).read()
                    if '"client_email"' in creds_json:
                        import json
                        with open(cred_path) as f:
                            creds = json.load(f)
                        print(f"     {creds.get('client_email')}")
                except:
                    pass
            elif "not supported" in error_msg.lower():
                print(f"\n💡 Solução:")
                print(f"   - Este documento pode não ser uma planilha (ex: Google Doc, Presentation)")
                print(f"   - Verifique se a URL aponta para uma planilha (Google Sheets)")
                print(f"   - URL esperada padrão: https://docs.google.com/spreadsheets/d/..." )

            assert False, f"APIError ao acessar planilha: {error_msg}"

    except ImportError as e:
        print(f"❌ ERRO: Biblioteca não instalada: {e}")
        print(f"\n💡 Solução: Execute 'uv install' ou 'pip install gspread google-auth-oauthlib'")
        assert False, f"Biblioteca não instalada: {e}"
    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        assert False, f"Erro inesperado: {e}"


if __name__ == "__main__":
    success = False
    try:
        success = test_sheet_access()
    except AssertionError as e:
        print(f"AssertionError: {e}")
        success = False

    print("\n" + "="*70)
    if success:
        print("🎉 SUCESSO! Conexão com Google Sheets funcionando!")
    else:
        print("⚠️  Há problemas na conexão. Verifique as sugestões acima.")
    print("="*70 + "\n")
