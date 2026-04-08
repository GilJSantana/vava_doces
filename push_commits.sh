#!/bin/bash
# Script de Push - Commits Deduplicação e Granularidade
# ======================================================
# Data: 8 de Abril de 2026
# Branch: develop
# Commits: 24 ahead of origin/develop

echo "=================================="
echo "📤 PUSH - Vava Doces Pipeline"
echo "=================================="
echo ""

# Mostrar commits que serão enviados
echo "📝 Commits a enviar:"
git log --oneline origin/develop..develop | head -12

echo ""
echo "📊 Estatísticas:"
echo "  - Commits a enviar: $(git rev-list --count origin/develop..develop)"
echo "  - Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "  - Status: $(git status --short | wc -l) arquivos pendentes"

echo ""
echo "=================================="
echo "🚀 Executando push..."
echo "=================================="
echo ""

# Executar push
git push origin develop

echo ""
echo "✅ Push concluído com sucesso!"
echo ""
echo "Próximos passos:"
echo "  1. Aguardar CI/CD pipeline"
echo "  2. Validar em ambiente de testes"
echo "  3. Fazer merge para main (se aprovado)"
echo ""
echo "Para consultar status:"
echo "  $ git log --oneline -n 5"
echo "  $ git status"

