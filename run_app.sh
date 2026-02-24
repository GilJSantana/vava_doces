#!/bin/bash

# Script para executar a aplicação Streamlit

set -e

echo "🚀 Iniciando Vava Doces - Streamlit App"
echo "========================================"

# Verificar se .env existe
if [ ! -f .env ]; then
    echo "⚠️  Arquivo .env não encontrado!"
    echo "📋 Copie o arquivo .env.example para .env e configure suas credenciais:"
    echo "   cp .env.example .env"
    echo ""
    exit 1
fi

echo "✅ Arquivo .env encontrado"
echo ""

# Verificar se está usando uv
if command -v uv &> /dev/null; then
    echo "📦 Usando gerenciador de pacotes: uv"
    echo "🎯 Executando: uv run streamlit run app.py"
    uv run streamlit run app.py
else
    echo "📦 uv não encontrado, tentando python direto..."
    streamlit run app.py
fi

