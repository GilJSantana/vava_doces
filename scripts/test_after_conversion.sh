#!/bin/bash
# Script para testar conexão Google Sheets após conversão

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🧪 TESTE DE CONEXÃO - Google Sheets"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📋 Executando testes em sequência..."
echo ""

# Teste 1: Tipo de documento
echo "1️⃣  Verificando tipo de documento..."
python3 test_document_type.py > /tmp/test1.log 2>&1

if grep -q "Este é um Google Sheets válido" /tmp/test1.log; then
    echo -e "${GREEN}✅ SUCESSO: É um Google Sheets nativo!${NC}"
else
    echo -e "${RED}❌ FALHOU: Ainda não é Google Sheets nativo${NC}"
    echo ""
    echo "   Ações necessárias:"
    echo "   1. Converta o arquivo para Google Sheets"
    echo "   2. Compartilhe com a Service Account"
    echo "   3. Execute este script novamente"
    exit 1
fi

echo ""

# Teste 2: Conexão com gspread
echo "2️⃣  Testando conexão com gspread..."
python3 test_connection_diagnostic.py > /tmp/test2.log 2>&1

if grep -q "Planilha acessada com sucesso" /tmp/test2.log; then
    echo -e "${GREEN}✅ SUCESSO: Conectado com Google Sheets!${NC}"
    echo ""

    # Mostrar abas
    echo "📊 Abas encontradas:"
    grep "'^   " /tmp/test2.log | head -5

    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo -e "${GREEN}🎉 TUDO OK! Google Sheets está configurado corretamente!${NC}"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "Próximas ações:"
    echo "  1. Execute: ./run_app.sh"
    echo "  2. Abra: http://localhost:8501"
    echo "  3. Sua aplicação estará pronta!"
    echo ""
else
    echo -e "${RED}❌ FALHOU: Problema ao conectar${NC}"
    echo ""
    echo "Log de erro:"
    grep "ERRO\|error" /tmp/test2.log | head -3
    echo ""
    echo "Verifique:"
    echo "  1. Converteu o arquivo para Google Sheets?"
    echo "  2. Compartilhou com a Service Account?"
    echo "  3. O novo ID está no .env?"
    exit 1
fi

