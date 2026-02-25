#!/bin/bash
# Script para executar a aplicação Streamlit - Vava Doces
echo "=========================================="
echo "🍰 Iniciando Vava Doces Application"
echo "=========================================="
echo ""
# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ ERRO: app.py não encontrado!"
    echo "💡 Por favor, execute este script no diretório raiz do projeto."
    exit 1
fi
# Verificar se o arquivo .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  AVISO: Arquivo .env não encontrado!"
    echo "   A aplicação pode não funcionar corretamente sem as variáveis de ambiente."
    echo ""
fi
# Verificar se streamlit está instalado
if ! command -v streamlit &> /dev/null; then
    echo "❌ ERRO: Streamlit não está instalado!"
    echo "💡 Instale com: uv pip install streamlit"
    exit 1
fi
# Verificar se gspread está instalado
if ! python -c "import gspread" 2>/dev/null; then
    echo "❌ ERRO: gspread não está instalado!"
    echo "💡 Instale com: uv pip install gspread"
    exit 1
fi
# Verificar se python-dotenv está instalado
if ! python -c "import dotenv" 2>/dev/null; then
    echo "❌ ERRO: python-dotenv não está instalado!"
    echo "💡 Instale com: uv pip install python-dotenv"
    exit 1
fi
echo "✅ Todas as dependências foram verificadas"
echo ""
# Carregar variáveis de ambiente
export $(cat .env | grep -v '#' | xargs)
# Exibir informações de conexão
echo "📋 Configurações:"
echo "   - Google Sheet ID: ${GOOGLE_SHEET_ID:0:20}..."
echo "   - Credenciais: ${GOOGLE_APPLICATION_CREDENTIALS}"
echo ""
# Iniciar a aplicação Streamlit
echo "🚀 Iniciando servidor Streamlit..."
echo "📍 A aplicação estará disponível em: http://localhost:8501"
echo ""
echo "💡 Pressione Ctrl+C para parar o servidor"
echo ""
streamlit run app.py
