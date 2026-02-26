# Guia de Setup da Aba "Ficha Técnica" (BOM - Bill of Materials)

## O que é a Ficha Técnica?

A aba **"Ficha Técnica"** (ou BOM - Bill of Materials) é a integração entre:
- **Cadastro Produtos** (lista de produtos/receitas)
- **Matéria Prima** (lista de ingredientes e preços)

Cada linha da Ficha Técnica descreve: _"O produto X contém Y unidades do ingrediente Z ao custo W"_

Exemplo:
- Bolo de Chocolate contém 0.1 kg de Chocolate em pó ao custo R$ 20,00/kg
- Bolo de Chocolate contém 0.2 kg de Açúcar ao custo R$ 5,00/kg

## Esquema da Aba

| Coluna | Tipo | Descrição | Obrigatório? |
|--------|------|-----------|------------|
| **ProductID** | Texto | ID único do produto (ex: P001) | ✅ Recomendado |
| **ProductName** | Texto | Nome do produto/receita | ✅ Sim |
| **IngredientID** | Texto | ID único do ingrediente (ex: I001) | ✅ Recomendado |
| **IngredientName** | Texto | Nome do ingrediente | ✅ Sim |
| **QtyPerProduct** | Número | Quantidade do ingrediente por unidade do produto | ✅ Sim |
| **QtyUnit** | Texto | Unidade de medida (kg, g, ml, L, un, etc) | ✅ Sim |
| **UnitCost** | Número | Custo unitário do ingrediente (por unidade da QtyUnit) | ✅ Sim |
| **UnitCurrency** | Texto | Moeda (ex: BRL, USD) | ⚪ Opcional |
| **Supplier** | Texto | Fornecedor do ingrediente | ⚪ Opcional |
| **Notes** | Texto | Observações/notas adicionais | ⚪ Opcional |
| **LastUpdated** | Data | Data da última atualização | ⚪ Opcional |

## Como Criar a Aba Automaticamente

### Opção 1: Usar o Script Python (Recomendado)

```bash
# 1. Certifique-se de estar no diretório do projeto
cd /home/gilunix/Documents/Projects/Vava_doces

# 2. Execute o script para criar a aba
python create_bom_sheet.py

# Saída esperada:
# 🔑 Conectando ao Google Sheets...
# 📂 Abrindo planilha com ID: 1H-kGx3eDUXPngRQIkLE6GadUD1chQdSM
# ✅ Aba 'Ficha Técnica' criada com sucesso!
# 📝 Adicionando headers...
# ✅ Aba 'Ficha Técnica' criada e formatada com sucesso!
```

### Opção 2: Criar Manualmente no Google Sheets

1. Acesse sua planilha no [Google Sheets](https://sheets.google.com)
2. Clique no **+** (adicionar aba) no canto inferior esquerdo
3. Nomeie como **"Ficha Técnica"**
4. Adicione os headers na primeira linha (copie/cole):
   ```
   ProductID | ProductName | IngredientID | IngredientName | QtyPerProduct | QtyUnit | UnitCost | UnitCurrency | Supplier | Notes | LastUpdated
   ```

## Como Popular com Dados de Exemplo

Após criar a aba, você pode popular automaticamente com exemplos:

```bash
python populate_bom_examples.py
```

Este script:
- Lê dados existentes de "Cadastro Produtos" e "Matéria Prima"
- Cria linhas de exemplo na Ficha Técnica
- Permite validar a integração antes de dados reais

Saída esperada:
```
🔑 Conectando ao Google Sheets...
📖 Lendo 'Cadastro Produtos'...
   ✅ 5 produtos lidos
📖 Lendo 'Matéria Prima'...
   ✅ 10 itens de matéria prima lidos
📝 Abrindo aba 'Ficha Técnica'...
📊 Preparando dados de exemplo...
📝 Adicionando 6 linhas de exemplo...
✅ População completa!
```

## Preenchendo Manualmente

Se preferir preencher manualmente, siga este exemplo:

### Exemplo: Bolo de Chocolate

| ProductID | ProductName | IngredientID | IngredientName | QtyPerProduct | QtyUnit | UnitCost | UnitCurrency | Supplier | Notes |
|-----------|-------------|------------|---|---|---|---|---|---|---|
| P001 | Bolo de Chocolate | I001 | Chocolate em pó | 0.1 | kg | 20.0 | BRL | FornecedorA | 50% cacau |
| P001 | Bolo de Chocolate | I002 | Açúcar | 0.2 | kg | 5.0 | BRL | FornecedorB | Cristal |
| P001 | Bolo de Chocolate | I003 | Ovo | 6 | un | 0.80 | BRL | FornecedorC | Tamanho M |

**Resultado esperado**: Custo total para produzir 1 Bolo de Chocolate = (0.1×20) + (0.2×5) + (6×0.80) = R$ 7.80

## Validando os Dados

Após preencher a Ficha Técnica, você pode validar os dados localmente:

```bash
# Python interativo (ou adicionar a um teste)
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.cost_analysis_service import CostAnalysisService

adapter = GoogleSheetsAdapter()
service = CostAnalysisService(adapter)

# Carregar BOM
bom_df = service.get_bom()
print(bom_df)  # Exibe as linhas da Ficha Técnica

# Calcular custos por receita
costs = service.calculate_costs_from_bom()
print(costs)  # {ProductName: Custo Total, ...}
```

## Boas Práticas

1. **Use IDs consistentes**: ProductID e IngredientID facilitam joins e evitam confusão com nomes duplicados.
2. **Mantenha unidade padronizada**: Se usar kg para um ingrediente, use kg para todos (ou documente conversões).
3. **Atualize preços regularmente**: Use a coluna `LastUpdated` para saber quando preço foi atualizado.
4. **Revise ingredientes ausentes**: Se um ingrediente não tiver preço, a linha será marcada como "custo 0" — revise e corrija.

## Estrutura Recomendada no Google Sheets

```
PLANILHA RAIZ
├── Cadastro Produtos        (lista master de produtos)
├── Matéria Prima            (lista master de ingredientes + preços)
├── Ficha Técnica            (relação produto×ingrediente×qtd)
├── Custos                   (derivado: custo por receita, auto-gerado)
├── Faturamento              (vendas/receita)
└── ... (outras abas)
```

## Próximos Passos

1. ✅ Criar aba "Ficha Técnica"
2. ✅ Popular com dados (manual ou script)
3. ⏳ Implementar método `calculate_costs_from_bom()` no `CostAnalysisService`
4. ⏳ Adicionar página Streamlit para exibir e gerenciar a Ficha Técnica
5. ⏳ Integrar cálculo de custos no Dashboard

---

**Dúvidas?** Consulte o README.md ou execute `python create_bom_sheet.py --help`

