# 🔍 REVISÃO DE NOMENCLATURA - ESTADO ATUAL

## 📊 Análise do Estado Atual da Planilha

A planilha já foi **parcialmente refatorada**! Veja o que foi feito:

---

## ✅ ABA "Produtos" - STATUS: PERFEITO

```
[1]  ID
[2]  Nome do Produto
[3]  Categoria
[4]  Rendimento
[5]  Custo de Produção
[6]  Custo Total Unitário (R$)
[7]  Preço de Venda (R$)
[8]  Margem (%)
[9]  Margem Bruta (R$)
[10] Ativo
```

**Status:** ✅ **100% em português** - Nenhuma alteração necessária

---

## 🟡 ABA "Receita" - STATUS: QUASE PERFEITA

```
Atual                           | Sugestão/Status
─────────────────────────────────────────────────────────────────
[1]  ID_Produto                 | ✅ OK (ou "ID do Produto"?)
[2]  Produto                    | ✅ OK (ou "Nome do Produto"?)
[3]  ID_Ingrediente             | ✅ OK (ou "ID do Ingrediente"?)
[4]  Ingrediente                | ✅ OK (ou "Nome do Ingrediente"?)
[5]  Quantidade por Produto     | ✅ PERFEITO
[6]  Medida                     | ⚠️ VERIFICAR (é "Unidade de Medida"?)
[7]  Custo Unitário             | ✅ OK (mas faltou moeda)
[8]  Fornecedor                 | ✅ OK
[9]  Notas                      | ✅ OK
[10] Última Atualização         | ✅ OK
```

**Observações:**
- Coluna [6] "Medida" é inconsistente com "Unidade de medida" em outras abas
- Falta coluna "Moeda" (estava na versão anterior com 11 colunas)
- Nomes em ID_Produto vs Produto - considerar "ID do Produto" e "Nome do Produto"?

---

## 🟡 ABA "Matéria Prima" - STATUS: QUASE PERFEITA

```
Atual                           | Sugestão/Status
─────────────────────────────────────────────────────────────────
[1]  ID_Ingrediente             | ✅ OK (ou "ID do Ingrediente"?)
[2]  Ingredientes               | ✅ OK (ou "Nome do Ingrediente"?)
[3]  Medida                     | ⚠️ REDUNDANTE COM PRÓXIMA?
[4]  Custo Unitário             | ✅ OK
```

**Problemas Identificados:**
1. Coluna [3] "Medida" - é a mesma coisa que "Unidade"?
2. **Falta coluna "Unidade"** - Onde está a unidade de medida?
3. Falta coluna "Moeda" - Qual a moeda do custo unitário?

---

## ✅ ABA "Medidas" - STATUS: PERFEITO

```
[1] Unidade de medida
```

**Status:** ✅ **Correto**

---

## 🎯 QUESTÕES PARA REVISÃO

### Pergunta 1: Consistência de Nomes
Qual padrão você prefere para chaves estrangeiras?

**Opção A:** `ID_Produto`, `ID_Ingrediente` (atual)
```
Conciso, mas mistura _com espaço
```

**Opção B:** `ID do Produto`, `ID do Ingrediente` (mais descritivo)
```
Mais claro, totalmente em português
```

**Recomendação:** Opção B (mais profissional e claro)

---

### Pergunta 2: "Medida" vs "Unidade"
Na aba "Matéria Prima" há uma coluna chamada "Medida". O que ela contém?

**Opções:**
- A) É a mesma coisa que "Unidade" → REMOVER uma delas
- B) "Medida" = descrição (ex: "200 gramas") e "Unidade" = apenas unidade (ex: "G") → Ambas necessárias
- C) Você adicionou "Medida" por engano → REMOVER

**Recomendação:** Padronizar para apenas "Unidade de Medida"

---

### Pergunta 3: Coluna "Moeda" Desapareceu?
Na análise anterior, a aba "Receita" tinha 11 colunas incluindo "UnitCurrency".

Agora tem apenas 10 colunas. Isso foi intencional?

Se sim:
- ✅ Podemos assumir que a moeda é sempre R$

Se não:
- ❌ Precisa adicionar coluna "Moeda" de volta

---

### Pergunta 4: Nomenclatura Simples vs Descritiva
Para chaves, qual padrão:

**Atual:** `ID_Produto`, `Produto`
```
Conciso mas pode confundir
```

**Proposto:** `ID do Produto`, `Nome do Produto`
```
Deixa claro que [2] é o NOME e [1] é o ID
```

**Recomendação:** Opção Proposta (melhor UX)

---

## 📋 PROPOSTA DE AJUSTES FINAIS

### Se você concordar, aqui está o resultado esperado:

#### **ABA "Receita" - Versão Final**
```
[1]  ID do Produto
[2]  Nome do Produto
[3]  ID do Ingrediente
[4]  Nome do Ingrediente
[5]  Quantidade por Produto
[6]  Unidade de Medida          ← (renomear "Medida")
[7]  Custo Unitário
[8]  Moeda                       ← (adicionar se necessário)
[9]  Fornecedor
[10] Notas
[11] Última Atualização
```

#### **ABA "Matéria Prima" - Versão Final**
```
[1] ID do Ingrediente
[2] Nome do Ingrediente
[3] Unidade de Medida            ← (renomear "Medida" E adicionar "Unidade")
[4] Custo Unitário
[5] Moeda                        ← (adicionar se necessário)
```

---

## ✨ Resumo das Alterações Propostas

| ABA | Coluna Atual | Coluna Proposta | Ação |
|-----|--------------|-----------------|------|
| **Receita** | ID_Produto | ID do Produto | Renomear |
| **Receita** | Produto | Nome do Produto | Renomear |
| **Receita** | ID_Ingrediente | ID do Ingrediente | Renomear |
| **Receita** | Ingrediente | Nome do Ingrediente | Renomear |
| **Receita** | Medida | Unidade de Medida | Renomear |
| **Receita** | (falta) | Moeda | Adicionar? |
| **Matéria Prima** | ID_Ingrediente | ID do Ingrediente | Renomear |
| **Matéria Prima** | Ingredientes | Nome do Ingrediente | Renomear |
| **Matéria Prima** | Medida | Unidade de Medida | Renomear |
| **Matéria Prima** | (falta) | Moeda | Adicionar? |

---

## 🤔 O que você pensa?

Qual é sua resposta para as 4 perguntas acima?

1. **Nomes com "do"?** (ID do Produto vs ID_Produto)
2. **"Medida" redundante?** (remover ou manter?)
3. **Coluna "Moeda"?** (adicionar de volta ou removida mesmo?)
4. **Nomenclatura descritiva?** (Nome do Produto vs Produto)

---

_Documento de revisão - Aguardando feedback do usuário_
_Data: 2026-03-04_

