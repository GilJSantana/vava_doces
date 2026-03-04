# 🚀 GUIA RÁPIDO - TESTAR O STREAMLIT REFATORADO

## 📋 Pré-requisitos

Certifique-se de que você tem:
- ✅ Arquivo `.env` com credenciais Google Sheets
- ✅ Abas refatoradas na planilha (Produtos, Receita, Matéria Prima)
- ✅ Ambiente virtual ativado

---

## 🔧 Instalação de Dependências

Se ainda não tiver instalado:

```bash
# No diretório do projeto
uv pip install streamlit
uv pip install pandas
uv pip install gspread
```

---

## ▶️ Executar Streamlit

```bash
# Na raiz do projeto
streamlit run app.py
```

Isso abrirá a aplicação em: `http://localhost:8501`

---

## 📊 Páginas Disponíveis

### 1. 📊 Dashboard
**O que mostra:**
- Total de Produtos
- Custo Total de Produção
- Custo Médio por Produto
- Custo Mínimo
- Gráfico de custos por produto
- Tabela detalhada

**Como usar:**
1. Abra a página Dashboard
2. Veja as métricas principais no topo
3. Analise o gráfico de custos
4. Verifique a tabela de detalhes

---

### 2. 💰 Custos de Produção
**O que mostra:**
- Detalhamento de custos por produto
- Ingredientes utilizados e quantidades
- Custo de cada ingrediente
- Resumo de todos os custos

**Como usar:**
1. Selecione um produto no dropdown
2. Veja o breakdown de ingredientes para aquele produto
3. Analise a tabela de custos consolidados
4. Download em CSV para análise externa

**Esperado:**
```
Produto: Caseirinho Sem...
├── Ingrediente 1: Quantidade X Unidade | Custo R$
├── Ingrediente 2: Quantidade Y Unidade | Custo R$
└── Total: R$ XXX,XX
```

---

### 3. 💹 Impacto no Faturamento
**O que mostra:**
- Preço de venda por produto
- Margem de lucro (%)
- Categoria de cada produto
- Gráficos de distribuição

**Como usar:**
1. Veja as métricas gerais (total de produtos, receita potencial, margem média)
2. Verifique a tabela de ranking
3. Analise os gráficos:
   - Produtos por Categoria
   - Distribuição de Margens
4. Download dos dados para análise

**Esperado:**
```
Produto A: Preço R$ 12,90 | Margem 90%
Produto B: Preço R$ 15,50 | Margem 85%
...
```

---

### 4. 🔍 Análise Detalhada
**O que mostra:**
- Custos por produto (tab 1)
- Análise de margens (tab 2 - em desenvolvimento)
- Relatórios (tab 3 - em desenvolvimento)

---

## 🧪 Testes Básicos

### Teste 1: Verificar Conexão
```
✓ Na sidebar deve aparecer: "✅ Conectado ao Google Sheets"
✗ Se aparecer erro: Verifique credenciais no .env
```

### Teste 2: Dados Carregando
```
✓ Dashboard deve mostrar métricas (não estar vazio)
✓ Custos de Produção deve ter dropdown com produtos
✓ Impacto no Faturamento deve ter tabela com dados
```

### Teste 3: Formatação
```
✓ Todos os valores em moeda devem estar como "R$ X.XXX,XX"
✓ Percentuais devem estar como "XX,X%"
✓ Datas devem estar formatadas (se houver)
```

### Teste 4: Download
```
✓ Todos os downloads devem funcionar
✓ Arquivo CSV deve ter dados válidos
✓ Abrir CSV em editor de texto ou Excel
```

---

## ⚠️ Possíveis Erros e Soluções

### Erro 1: "❌ Desconectado - Configure as credenciais"
```
Causa: Variáveis de ambiente não encontradas
Solução: Verifique se .env existe e tem:
  GOOGLE_APPLICATION_CREDENTIALS="./credencial/vava-doces-0667d5821bd5.json"
  GOOGLE_SHEET_ID="1KEzf8FcL21DMk_64t-B9gMQIxjEx3ZPS_XsY-jYNVNk"
```

### Erro 2: "⚠️ Nenhum dado de produtos disponível"
```
Causa: Aba Receita está vazia ou sem dados
Solução:
  - Verifique se a aba "Receita" tem dados
  - Verifique se há colunas com nomes esperados:
    * Nome do Produto
    * Nome do Ingrediente
    * Quantidade por Produto
    * Custo Unitário
```

### Erro 3: "❌ Erro ao processar dashboard"
```
Causa: Problema ao processar dados
Solução:
  - Verifique console (saída do Streamlit)
  - Procure mensagem de erro específica
  - Verifique se dados têm formato correto (números vs strings)
```

### Erro 4: "⚠️ Não foi possível encontrar coluna de nome de produto"
```
Causa: Coluna de nome não encontrada
Solução: Verifique nomes exatos nas abas:
  - Receita: "Nome do Produto"
  - Produtos: "Nome do Produto"
```

---

## 📱 Interface

### Cores
```
Fundo: Verde escuro (#0F3B2E)
Botões: Dourado (#C9A23A)
Texto: Creme (#F6F1E6)
Acentos: Verde (#145D44)
```

### Fonte
```
Playfair Display (títulos)
Sans-serif (corpo do texto)
```

---

## 💾 Cache

O Streamlit usa cache para melhor performance:
- Dados são carregados uma vez
- Cache é mantido em memória durante a sessão
- Para forçar atualização: tecle `C` na app ou `st.cache_clear()`

---

## 🔍 Debug

Se tiver problemas, abra o console do navegador (F12) e procure por:
- Errors (vermelho)
- Warnings (amarelo)
- Mensagens de log

Também verifique o console onde rodou `streamlit run app.py`

---

## 📊 Dados de Exemplo

Se ainda não preencheu a planilha, crie dados de teste:

### Receita (aba)
```
ID do Produto | Nome do Produto | ID do Ingrediente | Nome do Ingrediente | Quantidade por Produto | Unidade de Medida | Custo Unitário | Fornecedor | Notas
1 | Caseirinho | ING-001 | Açúcar | 200 | G | 0.50 | Fornecedor A |
```

### Matéria Prima (aba)
```
ID do Ingrediente | Nome do Ingrediente | Unidade de Medida | Custo Unitário
ING-001 | Açúcar | G | 0.50
ING-002 | Farinha | G | 0.30
```

### Produtos (aba)
```
ID | Nome do Produto | Categoria | Rendimento | Custo de Produção | Custo Total Unitário (R$) | Preço de Venda (R$) | Margem (%) | Margem Bruta (R$) | Ativo
1 | Caseirinho | Bolo | 3 | 20.37 | 6.79 | 12.90 | 90 | 6.11 | Sim
```

---

## ✅ Checklist Final

- [ ] Credenciais configuradas no .env
- [ ] Planilha com dados em todas as abas
- [ ] Colunas nomeadas corretamente (português)
- [ ] Streamlit instalado
- [ ] Ambiente virtual ativado
- [ ] Testes unitários passando (pytest)
- [ ] App abre sem erros
- [ ] Dashboard mostra dados
- [ ] Páginas carregam corretamente
- [ ] Downloads funcionam

---

## 🎓 Próximas Funcionalidades

Planejado para futuras versões:
- [ ] Filtros avançados por categoria
- [ ] Comparação de margens vs custos
- [ ] Gráficos de tendências
- [ ] Relatórios em PDF
- [ ] Dashboard compartilhável

---

_Guia Rápido - Streamlit Refatorado_
**Data:** 2026-03-04
**Status:** ✅ Pronto para testar

