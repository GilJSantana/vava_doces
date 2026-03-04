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

        print("\n📋 Configurações:")
        print(f"   Arquivo de credenciais: {cred_path}")
        print(f"   URL/ID da planilha: {sheet_url}")

        # Verificar arquivo de credenciais
        cred_exists = bool(cred_path) and Path(cred_path).exists()
        if not cred_exists:
            print("\n❌ ERRO: Arquivo de credenciais não encontrado!")
        assert cred_exists, "Arquivo de credenciais não encontrado"

        print("\n✅ Arquivo de credenciais encontrado")

        # Extrair ID
        sheet_id = extract_sheet_id(sheet_url)
        if not sheet_id:
            print("❌ ERRO: Não consegui extrair o ID da planilha da URL")
            print("   A URL deve conter: /spreadsheets/d/[ID]/")
        assert sheet_id, "Não consegui extrair o ID da planilha"

        print(f"✅ ID da planilha extraído: {sheet_id}")

        # Carregar credenciais
        print("\n🔑 Carregando credenciais...")
        credentials = Credentials.from_service_account_file(
            cred_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        print("✅ Credenciais carregadas")

        # Criar cliente
        print("\n🌐 Conectando ao Google Sheets API...")
        client = gspread.authorize(credentials)
        print("✅ Cliente autorizado")

        # Tentar diferentes formas de acesso
        print("\n📂 Tentando acessar a planilha...")

        try:
            # Tentativa 1: Abrir por ID
            spreadsheet = client.open_by_key(sheet_id)
            print("✅ Planilha acessada com sucesso!")
            print(f"   Título: {spreadsheet.title}")

            # Listar abas
            print("\n📊 Abas encontradas:")
            for i, sheet in enumerate(spreadsheet.worksheets(), 1):
                print(f"   {i}. '{sheet.title}'")
                # Mostrar primeiras 3 linhas
                try:
                    values = sheet.get_values('A1:C3')
                    if values:
                        print("      Dados (amostra):")
                        for row in values[:2]:
                            print(f"         {row}")
                except Exception as e:
                    print(f"      (Não consegui ler dados: {e})")

        except gspread.exceptions.APIError as e:
            error_msg = str(e)
            print(f"❌ ERRO ao acessar: {error_msg}")

            if "404" in error_msg or "not found" in error_msg:
                print("\n💡 Solução:")
                print("   - O ID da planilha pode estar incorreto")
                print("   - Verifique se a Service Account tem acesso à planilha")
                print("   - Você pode ter que compartilhar a planilha com o email da Service Account")
            elif "permission denied" in error_msg.lower():
                print("\n💡 Solução:")
                print("   - A Service Account não tem permissão de acesso")
                print("   - Compartilhe a planilha com o email da Service Account:")
                try:
                    creds_json = open(cred_path).read()
                    if '"client_email"' in creds_json:
                        import json
                        with open(cred_path) as f:
                            creds = json.load(f)
                        print(f"     {creds.get('client_email')}")
                except Exception:
                    pass
            elif "not supported" in error_msg.lower():
                print("\n💡 Solução:")
                print("   - Este documento pode não ser uma planilha (ex: Google Doc, Presentation)")
                print("   - Verifique se a URL aponta para uma planilha (Google Sheets)")
                print("   - URL esperada padrão: https://docs.google.com/spreadsheets/d/...")

            assert False, "Falha ao acessar a planilha"

    except ImportError as e:
        print(f"❌ ERRO: Biblioteca não instalada: {e}")
        print("\n💡 Solução: Execute 'uv install' ou 'pip install gspread google-auth-oauthlib'")
        assert False, "Biblioteca não instalada"
    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        assert False, f"Erro inesperado: {type(e).__name__}"

if __name__ == "__main__":
    success = True
    try:
        test_sheet_access()
    except AssertionError:
        success = False

    print("\n" + "="*70)
    if success:
        print("🎉 SUCESSO! Conexão com Google Sheets funcionando!")
    else:
        print("⚠️  Há problemas na conexão. Verifique as sugestões acima.")
    print("="*70 + "\n")
