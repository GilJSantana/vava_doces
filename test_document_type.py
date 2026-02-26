#!/usr/bin/env python3
"""
Script avançado para diagnosticar o tipo de documento Google
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def inspect_document():
    """Inspecionar qual tipo de documento é"""
    print("\n" + "="*70)
    print("🔬 INSPEÇÃO AVANÇADA DE DOCUMENTO GOOGLE")
    print("="*70)

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
        import google.auth.transport.urllib3
        import urllib3

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID").strip()

        print(f"\n📍 ID do Documento: {sheet_id}")

        # Carregar credenciais
        credentials = Credentials.from_service_account_file(
            cred_path,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )

        # Autenticar
        request = Request()
        credentials.refresh(request)

        # Chamar Google Drive API para inspecionar
        print("\n🔍 Consultando Google Drive API...")

        http = urllib3.PoolManager()
        headers = {'Authorization': f'Bearer {credentials.token}'}

        url = f"https://www.googleapis.com/drive/v3/files/{sheet_id}?fields=name,mimeType,createdTime"

        response = http.request('GET', url, headers=headers)

        if response.status == 200:
            data = json.loads(response.data.decode('utf-8'))

            print(f"\n✅ Documento encontrado!")
            print(f"   Nome: {data.get('name')}")
            print(f"   Tipo MIME: {data.get('mimeType')}")
            print(f"   Criado em: {data.get('createdTime')}")

            mime_type = data.get('mimeType', '')

            # Analisar tipo
            print(f"\n📊 Análise do Tipo:")

            if 'spreadsheet' in mime_type:
                print(f"   ✅ É uma PLANILHA (Google Sheets)")
                print(f"   Tipo: {mime_type}")
                assert True
            elif 'document' in mime_type:
                print(f"   ❌ É um DOCUMENTO (Google Docs) - NÃO é Sheets!")
                print(f"   Tipo: {mime_type}")
                print(f"\n💡 Solução: Use o ID de uma Planilha, não de um Documento")
                assert False, "Documento não é uma planilha"
            elif 'presentation' in mime_type:
                print(f"   ❌ É uma APRESENTAÇÃO (Google Slides) - NÃO é Sheets!")
                print(f"   Tipo: {mime_type}")
                print(f"\n💡 Solução: Use o ID de uma Planilha, não de uma Apresentação")
                assert False, "Documento é uma apresentação, não uma planilha"
            else:
                print(f"   ❓ Tipo desconhecido: {mime_type}")
                assert False, "Tipo desconhecido"

        elif response.status == 404:
            print(f"\n❌ ERRO 404: Documento não encontrado!")
            print(f"   O ID pode estar errado ou o documento foi deletado")
            assert False, "Documento não encontrado (404)"

        elif response.status == 403:
            print(f"\n❌ ERRO 403: Permissão negada!")
            print(f"   A Service Account não tem acesso a este documento")
            print(f"\n💡 Solução:")
            print(f"   1. Compartilhe o documento com o email da Service Account:")

            with open(cred_path) as f:
                creds = json.load(f)
            email = creds.get('client_email')
            print(f"      {email}")
            print(f"   2. Dê permissão de Visualizador (Reader)")
            assert False, "Permissão negada (403)"

        else:
            print(f"\n❌ ERRO HTTP {response.status}")
            print(f"   Resposta: {response.data.decode('utf-8')}")
            assert False, f"HTTP {response.status}"

    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        assert False, f"Erro inesperado: {e}"


if __name__ == "__main__":
    success = True
    try:
        inspect_document()
    except AssertionError as e:
        print(f"AssertionError: {e}")
        success = False

    print("\n" + "="*70)
    if success:
        print("🎉 Este é um Google Sheets válido!")
    else:
        print("⚠️  Este NÃO é um Google Sheets válido.")
        print("\n💡 Para encontrar o ID correto:")
        print("   1. Abra https://sheets.google.com")
        print("   2. Crie ou abra uma Planilha")
        print("   3. A URL será: https://docs.google.com/spreadsheets/d/[ID]/")
        print("   4. Copie o [ID] e coloque no .env")
    print("="*70 + "\n")
