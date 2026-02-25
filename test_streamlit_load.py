#!/usr/bin/env python3
"""
Teste para validar que o app.py carrega sem erros de sintaxe
"""

import sys
import ast

def test_syntax():
    """Verifica se o arquivo Python tem sintaxe válida"""
    try:
        with open("app.py", "r") as f:
            code = f.read()
        ast.parse(code)
        print("✅ Sintaxe do app.py está válida")
        return True
    except SyntaxError as e:
        print(f"❌ Erro de sintaxe em app.py: {e}")
        return False

def test_imports():
    """Tenta importar o módulo"""
    try:
        import app
        print("✅ Módulo app.py importado com sucesso")
        return True
    except ImportError as e:
        print(f"⚠️  Erro de importação (esperado sem streamlit): {e}")
        return True
    except Exception as e:
        print(f"❌ Erro ao importar app.py: {e}")
        return False

def test_functions_exist():
    """Verifica se as funções esperadas existem"""
    with open("app.py", "r") as f:
        code = f.read()

    expected_functions = [
        "get_adapter",
        "get_service",
        "format_currency",
        "load_data_from_sheet",
        "show_dashboard",
        "show_produtos",
        "show_materia_prima",
        "show_vendas_diarias",
        "show_resumo_diario",
        "show_analise_categoria",
        "show_analise_detalhada",
        "main"
    ]

    missing = []
    for func in expected_functions:
        if f"def {func}" not in code:
            missing.append(func)

    if missing:
        print(f"⚠️  Funções não encontradas: {', '.join(missing)}")
        return False
    else:
        print(f"✅ Todas as funções esperadas foram encontradas ({len(expected_functions)})")
        return True

if __name__ == "__main__":
    print("="*60)
    print("🧪 TESTE DE CARREGAMENTO - app.py")
    print("="*60)

    results = [
        ("Sintaxe", test_syntax()),
        ("Funções", test_functions_exist()),
        ("Imports", test_imports()),
    ]

    print("\n" + "="*60)
    print("📊 RESUMO")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    print(f"\nTotal: {passed}/{total} testes passaram")

    sys.exit(0 if passed == total else 1)

