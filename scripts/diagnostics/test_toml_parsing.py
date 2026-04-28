#!/usr/bin/env python3
"""
Teste de validação de parsing do arquivo secrets.toml
Verifica se a estrutura está correta para `st.secrets["gcp_service_account"]`
"""

import sys
from pathlib import Path
import toml

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Ler e fazer parse do arquivo TOML
secrets_path = _PROJECT_ROOT / ".streamlit" / "secrets.toml"

print("=" * 70)
print("VALIDAÇÃO DO ARQUIVO SECRETS.TOML")
print("=" * 70)

try:
    with open(secrets_path, "r") as f:
        secrets = toml.load(f)

    print(f"\n✓ Arquivo lido com sucesso: {secrets_path}\n")

    # Validar estrutura de topo
    print("Variáveis de topo:")
    for key in ["OAUTH2_CLIENT_ID", "OAUTH2_CLIENT_SECRET", "OAUTH2_REDIRECT_URI",
                "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
                "VAVA_SHEETS_CACHE_TTL", "VAVA_PERF_LOG", "VAVA_SALES_SOURCE"]:
        value = secrets.get(key)
        if value:
            print(f"  ✓ {key}: {str(value)[:50]}...")
        else:
            print(f"  ✗ {key}: FALTANDO")

    # Validar seção gcp_service_account
    print("\n" + "=" * 70)
    print("Seção [gcp_service_account]:")
    print("=" * 70)

    service_account = secrets.get("gcp_service_account")

    if not isinstance(service_account, dict):
        print(f"✗ ERRO: gcp_service_account não é um dicionário!")
        print(f"  Tipo encontrado: {type(service_account)}")
        sys.exit(1)

    print(f"✓ gcp_service_account é um dicionário válido\n")

    # Campos obrigatórios
    required_fields = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
        "universe_domain"
    ]

    print("Campos presentes:")
    all_present = True
    for field in required_fields:
        value = service_account.get(field)
        if value:
            if field == "private_key":
                print(f"  ✓ {field}: {len(str(value))} caracteres (chave privada RSA)")
            else:
                display_val = str(value)[:60]
                print(f"  ✓ {field}: {display_val}")
        else:
            print(f"  ✗ {field}: FALTANDO OU VAZIO")
            all_present = False

    print("\n" + "=" * 70)
    if all_present:
        print("✓ SUCESSO: Arquivo TOML está corretamente estruturado!")
        print("  Todos os campos necessários estão presentes.")
        print("\nPróximo passo: Deploy para Streamlit Cloud")
        print("  Copie estes valores para as secrets do Streamlit Cloud:")
        print(f"  OAUTH2_CLIENT_ID: {secrets['OAUTH2_CLIENT_ID'][:40]}...")
        print(f"  OAUTH2_CLIENT_SECRET: {secrets['OAUTH2_CLIENT_SECRET'][:20]}...")
        print(f"  gcp_service_account: [dicionário com {len(service_account)} campos]")
    else:
        print("✗ ERRO: Alguns campos obrigatórios estão faltando")
        sys.exit(1)

    print("=" * 70)

except FileNotFoundError:
    print(f"\n✗ Arquivo não encontrado: {secrets_path}")
    sys.exit(1)
except toml.TomlDecodeError as e:
    print(f"\n✗ Erro ao fazer parse do TOML:")
    print(f"  {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Erro inesperado:")
    print(f"  {type(e).__name__}: {e}")
    sys.exit(1)

