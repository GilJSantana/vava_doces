# 📊 Análise da Estrutura de Abas da Planilha

## 🎯 Contexto

Você está analisando as abas da planilha para reorganizá-las de forma mais semântica e lógica. Atualmente temos três abas principais que precisam ser entendidas:

- **Receitas** - Contém informações sobre produtos
- **Matéria Prima** - Contém ingredientes e custos unitários
- **Uma terceira aba** - Que deveria fazer a integração entre Receitas e Matéria Prima

---

## 📄 Abas Atuais e Suas Estruturas

### 1️⃣ ABA: "Receitas"

**Objetivo atual:** Armazena informações de produtos finalizados

**Colunas (10 no total):**
1. ID - Identificador único do produto (ex: PROD-001)
2. Nome do Produto - Nome descritivo (ex: Caseirinho Sem...)
3. Categoria - Tipo de produto (ex: Bolo, Doce)
4. Rendimento - Quantidade produzida por lote
5. Custo de Produção - Custo total do lote
6. Custo Total Unitário (R$) - Custo por unidade
7. Preço de Venda (R$) - Preço praticado
8. Margem (%) - Margem de lucro em percentual
9. Margem Bruta (R$) - Lucro bruto por unidade
10. Ativo - Status do produto

**Dados de exemplo:**
```
| ID        | Nome do Produto         | Categoria | Rendimento | Custo Unitário |
|-----------|-------------------------|-----------|------------|----------------|
| PROD-001  | Caseirinho Sem...       | Bolo      | 3          | R$ 6,79        |
| PROD-002  | Copo Gelado Maracujá    | Doce      | 8          | R$ 7,31        |
| PROD-003  | Copo Gelado Limão       | Doce      | 8          | (vazio)        |
```

**Observação:** Alguns produtos têm custos de produção vazios, o que sugere que os dados ainda estão em processo de preenchimento.

---

### 2️⃣ ABA: "Matéria Prima"

**Objetivo:** Armazena ingredientes e seus custos unitários

**Colunas (4 no total):**
1. ID_Ingrediente - Identificador único (ex: ING-001)
2. Ingredientes - Nome do ingrediente
3. Unidade - Unidade de medida (G, ML, KG, etc)
4. Custo Unitário - Preço unitário do ingrediente

**Dados de exemplo:**
```
| ID_Ingrediente | Ingredientes      | Unidade | Custo Unitário |
|----------------|-------------------|---------|----------------|
| ING-001        | Açúcar            | G       | (vazio)        |
| ING-002        | Açúcar Mascado    | G       | (vazio)        |
| ING-003        | Água              | ML      | (vazio)        |
```

**Observação:** Os custos unitários também estão vazios, indicando dados incompletos.

---

### 3️⃣ ABA FALTANTE: "Cadastro Produtos" / "Produtos"

**Status:** Não existe na planilha atual

**Propósito sugerido:** Fazer a integração/join entre as duas abas acima

---

## 🤔 Sua Proposta de Refatoração

Você sugeriu renomear as abas para melhorar a semântica:

| Status Atual | → | Proposta |
|-------------|---|----------|
| "Receitas" | → | "Produtos" |
| (faltante) | → | "Receitas" |

### Lógica da Proposta

**POR QUE faz sentido?**

A palavra "Receita" em português pode significar:
1. **Um detalhamento** de como fazer algo (ex: receita de bolo = modo de fazer)
2. **Um registro de ganhos** (ex: receita de vendas = ganhos obtidos)

**Na sua planilha:**
- A aba atual **"Receitas"** contém **informações de PRODUTOS finalizados** (com preço, margem, etc)
- A aba faltante **"Receitas"** deveria conter **como FAZER cada produto** (ingredientes, quantidades, modo de fazer)

**Portanto, a reorganização ficaria assim:**

```
┌─────────────────────────────────────────────────────┐
│                 "MATÉRIA PRIMA"                     │
│                                                     │
│ Ingredientes básicos com custos unitários           │
│ (Açúcar, Farinha, Leite, etc)                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ (usa)
                   ↓
┌─────────────────────────────────────────────────────┐
│                "RECEITAS"                           │
│                                                     │
│ Como fazer cada produto                             │
│ (Ingredientes necessários, quantidades, modo fazer)│
│ ID: PROD-001, PROD-002, etc                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ (integra/join)
                   ↓
┌─────────────────────────────────────────────────────┐
│                "PRODUTOS"                           │
│                                                     │
│ Cadastro de produtos finalizados                    │
│ (Preço, Margem, Lucro, Status)                     │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Questões para Análise

Antes de implementar, considere:

### 1. **Qual será a chave de junção?**
   - A aba "Receitas" usa `ID` ou `ProductID` para identificar o produto?
   - A aba "Matéria Prima" usa qual ID para ingredientes?
   - Como a aba "Produtos" vai conectar a um ingrediente de "Matéria Prima"?

**Sugestão observada:**
```
ABA Receitas:        ID = PROD-001
ABA Matéria Prima:   ID_Ingrediente = ING-001
ABA Produtos (nova):
   - ProductID → referencia PROD-001 de Receitas
   - IngredienteID → referencia ING-001 de Matéria Prima
```

### 2. **Quantidades e proporções**
   - Como você vai armazenar que "PROD-001 precisa de 100g de Açúcar (ING-001)"?
   - Isso vai numa coluna da aba "Receitas" ou numa aba separada de "Receita-Ingredientes"?

**Exemplo de estrutura esperada para "Receitas":**
```
| ProductID | IngredienteID | QuantidadeNecessaria | Unidade |
|-----------|---------------|----------------------|---------|
| PROD-001  | ING-001       | 200                  | G       |
| PROD-001  | ING-002       | 100                  | G       |
| PROD-002  | ING-003       | 500                  | ML      |
```

### 3. **Dados de produto finalizado**
   - A aba "Produtos" vai conter apenas informações de preço, margem e lucro?
   - Ou vai consolidar também informações de categoria e rendimento?

**Exemplo esperado:**
```
| ProductID | ProductName        | Category | Price | Margin% | GrossMargin |
|-----------|-------------------|----------|-------|---------|-------------|
| PROD-001  | Caseirinho Sem... | Bolo    | 12,90 | 90      | 12,11       |
```

---

## ✅ Próximos Passos Sugeridos

1. **Confirmar a semântica:** Todos concordam que essa organização faz sentido?
2. **Detalhar a aba "Receitas":** Como exatamente ela vai conectar Produtos a Matéria Prima?
3. **Criar a nova aba "Produtos":** Com as colunas de cadastro final
4. **Implementar as fórmulas:** Para calcular custo total baseado em ingredientes
5. **Validar dados:** Garantir que os custos unitários em "Matéria Prima" estejam preenchidos

---

## 🎨 Diagrama ER Proposto

```
┌──────────────────────┐
│   Matéria Prima      │
├──────────────────────┤
│ ID_Ingrediente (PK)  │
│ Ingredientes         │
│ Unidade              │
│ Custo Unitário       │
└──────────────────────┘
         ↑
         │ Referencia (ING-001, ING-002...)
         │
    ┌────┴───────────────────┐
    │                        │
┌───┴──────────────────────┐ │
│   Receitas               │ │
├──────────────────────────┤ │
│ ProductID (FK,PK)        │ │
│ IngredienteID (FK,PK)    │─┘
│ QuantidadeNecessaria     │
│ Unidade                  │
└──────────────────────────┘
         ↑
         │ Referencia (PROD-001, PROD-002...)
         │
┌────────┴──────────────────┐
│     Produtos             │
├──────────────────────────┤
│ ProductID (PK)           │
│ ProductName              │
│ Categoria                │
│ PreçoVenda               │
│ Margem (%)               │
│ MargemBruta (R$)         │
│ Ativo                    │
└──────────────────────────┘
```

---

## 📝 Notas Importantes

- ⚠️ **Dados incompletos:** Tanto "Receitas" quanto "Matéria Prima" têm campos vazios que precisam ser preenchidos
- 💡 **Semântica clara:** A reorganização proposta deixa claro o fluxo: Ingrediente → Receita → Produto
- 🔄 **Rastreabilidade:** Com essa estrutura, você consegue rastrear quanto cada ingrediente contribui para o custo final
- 📊 **Relatórios:** Fica fácil gerar relatórios de margem e lucro por produto

---

_Documento de análise - Nenhuma implementação foi feita ainda_
_Data: 2026-03-04_

