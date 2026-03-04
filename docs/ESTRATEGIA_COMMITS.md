# 📋 ESTRATÉGIA DE COMMITS

## 🎯 Objetivo

Criar commits organizados, semânticos e fáceis de rastrear seguindo Conventional Commits e boas práticas Git.

---

## 📊 ANÁLISE DAS MUDANÇAS

### Categorias Identificadas:

1. **Refatoração de Estrutura** (refactor)
   - Reorganização de diretórios
   - Movimentação de arquivos
   - Criação de estrutura scripts/, data/

2. **Nova Funcionalidade** (feat)
   - ProductAnalysisService
   - Parse de moeda
   - Páginas novas no Streamlit

3. **Correções de Bugs** (fix)
   - Cache do Streamlit
   - Parsing de moeda
   - Análise Detalhada

4. **Atualização de Nomenclatura** (refactor)
   - Nomes de colunas em português
   - Atualização de referências no código

5. **Documentação** (docs)
   - Novos documentos
   - Atualização de README
   - Guias e tutoriais

---

## 🏗️ ESTRUTURA DE COMMITS PROPOSTA

### Formato Conventional Commits:
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types:
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `refactor`: Refatoração (sem mudança de comportamento)
- `docs`: Apenas documentação
- `style`: Formatação (sem mudança de lógica)
- `test`: Adição/modificação de testes
- `chore`: Mudanças em build, CI, etc

---

## 📝 COMMITS PLANEJADOS (11 commits)

### COMMIT 1: Reorganização da estrutura do projeto
```
Type: refactor(structure)
Arquivos:
  - Criar: scripts/, data/raw/, data/processed/
  - Mover: convert_to_sheets.py → scripts/
  - Mover: run_app.sh → scripts/
  - Mover: test_after_conversion.sh → scripts/
  - Mover: test_connection*.py → tests/
  - Mover: test_document_type.py → tests/
  - Mover: RECEITAS AWI.xlsx → data/raw/
  - Remover: test_streamlit_load.py
  - Criar: scripts/README.md
  - Criar: data/README.md
```

**Mensagem:**
```
refactor(structure): reorganizar estrutura de diretórios do projeto

Reorganizar arquivos seguindo boas práticas Python:
- Criar diretório scripts/ para utilitários
- Criar diretório data/raw/ para dados brutos
- Mover 3 scripts para scripts/
- Mover 3 testes para tests/
- Mover arquivo de dados para data/raw/
- Remover test_streamlit_load.py (vazio)
- Adicionar READMEs documentando estrutura

BREAKING CHANGE: Arquivos movidos de localização
```

---

### COMMIT 2: Padronizar nomenclatura das colunas em português
```
Type: refactor(sheets)
Arquivos:
  - docs/NOMENCLATURA_FINALIZADA.md
  - docs/ATUALIZACAO_CODIGO_NOMENCLATURA.md
  - docs/RELATORIO_FINAL_NOMENCLATURA.md
  - docs/REVISAO_NOMENCLATURA_FINAL.md
```

**Mensagem:**
```
refactor(sheets): padronizar nomenclatura de colunas em português

Padronizar nomes de colunas nas abas Google Sheets:
- Aba Receita: ID_Produto → ID do Produto
- Aba Receita: Medida → Unidade de Medida
- Aba Matéria Prima: ID_Ingrediente → ID do Ingrediente
- Aba Matéria Prima: Medida → Unidade de Medida

Decisão: Moeda não necessária (sempre R$)

Documentos criados sobre a padronização.
```

---

### COMMIT 3: Atualizar código para novos nomes de colunas
```
Type: refactor(services)
Arquivos:
  - src/domain/cost_analysis_service.py
```

**Mensagem:**
```
refactor(services): atualizar busca de colunas para nomes em português

Atualizar CostAnalysisService para priorizar nomes em português:
- Buscar "Nome do Produto" antes de "ProductName"
- Buscar "Quantidade por Produto" antes de "QtyPerProduct"
- Buscar "Custo Unitário" antes de "UnitCost"

Mantém compatibilidade com nomes antigos (backward compatible).
```

---

### COMMIT 4: Adicionar novo serviço de análise de produtos
```
Type: feat(services)
Arquivos:
  - src/domain/product_analysis_service.py
```

**Mensagem:**
```
feat(services): adicionar ProductAnalysisService para análise integrada

Criar novo serviço que integra dados de múltiplas abas:
- get_product_cost_summary(): resumo de custos por produto
- get_product_cost_breakdown(): detalhamento de ingredientes
- get_products_with_sales_impact(): dados comerciais
- calculate_total_cost_per_product(): custos totalizados
- get_ingredients_list(): lista de matéria prima

Integra dados de Receita + Matéria Prima + Produtos.
Implementa cache automático e busca case-insensitive.
```

---

### COMMIT 5: Refatorar Streamlit com novas páginas e análises
```
Type: feat(app)
Arquivos:
  - app.py
```

**Mensagem:**
```
feat(app): refatorar Streamlit com análises de custos e faturamento

Refatorar aplicação Streamlit com novas funcionalidades:
- Dashboard refatorado com métricas consolidadas
- Nova página: 💰 Custos de Produção (análise por ingrediente)
- Nova página: 💹 Impacto no Faturamento (receita + margens)
- Atualizar Análise Detalhada para usar ProductAnalysisService
- Menu de navegação atualizado

Integra ProductAnalysisService para dados consolidados.
```

---

### COMMIT 6: Corrigir erro de cache do Streamlit
```
Type: fix(app)
Arquivos:
  - app.py (get_product_service)
```

**Mensagem:**
```
fix(app): corrigir UnhashableParamError no cache do Streamlit

Adicionar underscore antes do parâmetro adapter para evitar
tentativa de hash de objeto não-hashable:
- get_product_service(_adapter) em vez de get_product_service(adapter)

Resolve: UnhashableParamError ao carregar aplicação
```

---

### COMMIT 7: Adicionar função de parsing de moeda brasileira
```
Type: feat(app)
Arquivos:
  - app.py (parse_currency)
```

**Mensagem:**
```
feat(app): adicionar função parse_currency para moeda brasileira

Criar função parse_currency() que converte strings de moeda
para float, tratando formato brasileiro:
- Remove "R$" e espaços
- Trata ponto como separador de milhares
- Trata vírgula como separador decimal
- Retorna None em caso de erro

Resolve conversão de "R$ 1.234,56" → 1234.56
```

---

### COMMIT 8: Corrigir parsing de moeda na página de faturamento
```
Type: fix(app)
Arquivos:
  - app.py (show_revenue_impact)
```

**Mensagem:**
```
fix(app): corrigir erro de conversão de moeda no faturamento

Usar parse_currency() em vez de astype(float) para converter
valores de moeda no formato brasileiro:
- Cálculo de receita total
- Cálculo de margem média
- Formatação de tabela
- Gráfico de distribuição de margens

Resolve: "could not convert string to float: 'R$ 12,90'"
```

---

### COMMIT 9: Corrigir aba de origem na análise detalhada
```
Type: fix(app)
Arquivos:
  - app.py (show_analise_detalhada)
```

**Mensagem:**
```
fix(app): corrigir aba de origem na Análise Detalhada

Alterar cálculo de custos para usar aba Receita em vez de Produtos:
- Usar product_service.calculate_total_cost_per_product()
- Adicionar product_service como parâmetro da função

A aba Produtos não contém colunas de ingredientes necessárias
para cálculo. A aba Receita contém os dados corretos.

Resolve: "Sheet is missing required columns for product cost calculation"
```

---

### COMMIT 10: Adicionar documentação completa da refatoração
```
Type: docs
Arquivos:
  - docs/REFATORACAO_STREAMLIT.md
  - docs/GUIA_TESTE_STREAMLIT.md
  - docs/RESUMO_EXECUTIVO_REFATORACAO.md
  - docs/ANALISE_ESTRUTURA_PROJETO.md
  - docs/REORGANIZACAO_CONCLUIDA.md
  - docs/ANALISE_ESTRUTURA_ABAS.md
```

**Mensagem:**
```
docs: adicionar documentação completa da refatoração

Criar documentação detalhada sobre:
- Refatoração do Streamlit (relatório técnico)
- Guia de testes e troubleshooting
- Resumo executivo do projeto
- Análise de estrutura do projeto
- Análise das abas Google Sheets
- Conclusão da reorganização

Total: 6 novos documentos
```

---

### COMMIT 11: Adicionar documentação das correções de bugs
```
Type: docs
Arquivos:
  - docs/CORRECAO_ERRO_STREAMLIT.md
  - docs/VERIFICACAO_FINAL_CORRECAO.md
  - docs/CORRECAO_PARSING_MOEDA.md
  - docs/CORRECAO_ANALISE_DETALHADA.md
  - docs/TODAS_CORRECOES_CONSOLIDADO.md
```

**Mensagem:**
```
docs: adicionar documentação das correções de bugs

Documentar todas as correções de bugs realizadas:
- Correção de cache do Streamlit
- Verificação final da correção
- Correção de parsing de moeda
- Correção da análise detalhada
- Resumo consolidado de todas correções

Total: 5 documentos técnicos
```

---

## 🎯 ORDEM DE EXECUÇÃO

```
1. refactor(structure)       → Reorganização base
2. refactor(sheets)          → Padronização de dados
3. refactor(services)        → Atualização de código existente
4. feat(services)            → Nova funcionalidade (ProductAnalysisService)
5. feat(app)                 → Refatoração major do Streamlit
6. fix(app) - cache          → Correção crítica #1
7. feat(app) - parse         → Nova função auxiliar
8. fix(app) - moeda          → Correção crítica #2
9. fix(app) - análise        → Correção crítica #3
10. docs - refatoração       → Documentação da refatoração
11. docs - correções         → Documentação das correções
```

---

## ✅ BENEFÍCIOS DESTA ESTRATÉGIA

### 1. Commits Atômicos
- Cada commit faz UMA coisa
- Fácil de reverter se necessário
- Histórico limpo e legível

### 2. Conventional Commits
- Formato padronizado
- Fácil de gerar CHANGELOG
- Semver automático possível

### 3. Rastreabilidade
- Cada mudança tem contexto
- Fácil entender o "porquê"
- Facilita code review

### 4. Organização por Escopo
- `structure`: Estrutura de diretórios
- `sheets`: Mudanças em planilhas
- `services`: Lógica de negócio
- `app`: Aplicação Streamlit
- `docs`: Documentação

---

## 🚀 EXECUÇÃO

Commits serão criados na ordem especificada, garantindo:
- ✅ Histórico linear e lógico
- ✅ Cada commit compila e funciona
- ✅ Mensagens descritivas e padronizadas
- ✅ Fácil navegação no histórico

---

_Estratégia de Commits - Vava Doces_
**Data:** 2026-03-04
**Total de commits:** 11
**Padrão:** Conventional Commits

