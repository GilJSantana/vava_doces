"""Script para baixar dados de demonstração do Google Drive para data/raw/

Uso:
    python scripts/download_demo_data.py
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Adicionar raiz do projeto ao path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load env vars
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_RAW_DIR = _PROJECT_ROOT / "data" / "raw"


def download_demo_files():
    """Tenta baixar arquivos de vendas do Google Drive para data/raw/."""
    from src.domain.sales_analysis_service import sync_drive_files_to_raw_from_env

    _RAW_DIR.mkdir(parents=True, exist_ok=True)

    try:
        cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        folder_id = os.getenv("DRIVE_FOLDER_ID")

        if not cred_file or not folder_id:
            print("❌ Variáveis de ambiente não configuradas.")
            print("   Configure GOOGLE_APPLICATION_CREDENTIALS e DRIVE_FOLDER_ID no .env")
            return False

        if not Path(cred_file).exists():
            print(f"❌ Arquivo de credenciais não encontrado: {cred_file}")
            return False

        print(f"📥 Sincronizando dados do Google Drive folder {folder_id}...")
        synced = sync_drive_files_to_raw_from_env(_RAW_DIR)

        if synced > 0:
            print(f"✅ Sincronizados {synced} arquivo(s)")
            files = list(_RAW_DIR.glob("*.csv")) + list(_RAW_DIR.glob("*.xlsx"))
            for f in files:
                print(f"   - {f.name}")
            return True
        else:
            print("⚠️  Nenhum arquivo foi sincronizado")
            return False

    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
        return False


def create_demo_data():
    """Cria dados de demonstração local em data/raw/."""
    import pandas as pd

    _RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("📝 Criando dados de demonstração...")

    # Criar arquivo de vendas de exemplo
    demo_sales = pd.DataFrame([
        {
            "Número da venda": 1001,
            "Data da venda": "2/1/2026",
            "Cliente": "João da Silva",
            "Nome do produto/serviço": "Brigadeiro Tradicional",
            "Quantidade de itens": 2,
            "Valor unitário": "5,00",
            "Valor Total": "10,00",
        },
        {
            "Número da venda": 1001,
            "Data da venda": "2/1/2026",
            "Cliente": "João da Silva",
            "Nome do produto/serviço": "Coxinha de Frango",
            "Quantidade de itens": 3,
            "Valor unitário": "3,50",
            "Valor Total": "10,50",
        },
        {
            "Número da venda": 1002,
            "Data da venda": "2/2/2026",
            "Cliente": "Maria Santos",
            "Nome do produto/serviço": "Bolo de Chocolate",
            "Quantidade de itens": 1,
            "Valor unitário": "25,00",
            "Valor Total": "25,00",
        },
    ])

    sales_file = _RAW_DIR / "vendas_demo_2026_02.csv"
    demo_sales.to_csv(sales_file, index=False, encoding="utf-8")
    print(f"✅ Arquivo de demonstração criado: {sales_file.name}")

    return True


def main():
    """Função principal."""
    print("🍰 Vava Doces - Download de Dados de Demonstração")
    print("=" * 50)

    # Primeiro, tentar baixar do Google Drive
    print("\n1️⃣  Tentando sincronizar do Google Drive...")
    if download_demo_files():
        print("✅ Pronto! Agora você pode executar: streamlit run app.py")
        return

    # Se falhar, criar dados de demonstração
    print("\n2️⃣  Criando dados locais de demonstração...")
    if create_demo_data():
        print("✅ Pronto! Agora você pode executar: streamlit run app.py")
        return

    print("❌ Não foi possível criar dados de demonstração")


if __name__ == "__main__":
    main()


