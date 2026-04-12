<div align="center">
  <img src="assets/logo.png" alt="Vava Doces Logo" width="200" height="200" style="border-radius: 20px;">
</div>

# Vavá Doces Data App

Aplicação de Business Intelligence e Engenharia de Dados para transformar planilhas operacionais em decisões de rentabilidade.

## Visão Executiva

A Vavá Doces tinha um problema clássico de pequenas operações: havia volume de vendas, mas pouca visibilidade sobre **quanto cada produto realmente contribuía para o lucro**.

Este projeto resolve essa lacuna com um app de dados que:
- integra dados de Google Drive e Google Sheets;
- padroniza e valida os dados em pipeline Medallion;
- publica análises executivas em Streamlit para decisão rápida.

## Problema que o App Resolve

O app foi desenhado para responder à pergunta central:

**"Quais produtos geram lucro de verdade, quais sustentam caixa e quais estão destruindo margem?"**

Sem essa visibilidade, ajustes de preço, compra de insumos e priorização comercial tendem a ser feitos por percepção. Com o app, as decisões passam a ser baseadas em fatos auditáveis.

## Arquitetura de Dados (Medallion)

### Bronze
- Ingestão dos arquivos brutos (CSV/XLSX) e exportações auxiliares de planilhas.
- Preservação do dado original para rastreabilidade.

### Silver
- Normalização de colunas, datas, valores monetários e chaves de produto.
- Deduplicação técnica controlada (sem colapsar itens legítimos de pedidos).
- Tratamento de inconsistências para reduzir ruído analítico.

### Gold
- Tabelas analíticas para consumo da aplicação:
  - fato e dimensões (`fato_vendas`, `dim_produto`, `dim_tempo`);
  - agregados de vendas;
  - custos de produção (`custos_producao_agregado`, `receitas_detalhadas`);
  - rentabilidade (`gold_rentabilidade`).
- Preservação de linhagem de `NaN` para evitar falsos positivos de margem.

## Integração com Google Sheets

A integração com Google Sheets é parte do fluxo oficial:
- leitura de abas operacionais para atualização de custos e receitas;
- exportação/consumo de dados para alimentar o pipeline;
- atualização rápida via sidebar no Streamlit.

Isso permite manter o processo aderente à operação real do negócio, sem exigir mudança abrupta de ferramenta da equipe.

## App Streamlit (MVP em Produção)

O cockpit executivo possui três páginas:
1. `📊 Dashboard` — rentabilidade, matriz estratégica e Pareto de receita.
2. `💰 Custos de Produção` — auditoria de custos e pendências por ingrediente.
3. `💹 Faturamento (Auditoria)` — exploração detalhada das vendas com filtros e exportação.

## Guia de Uso de Negócio (Resumo)

### Matriz de Rentabilidade
A matriz cruza:
- eixo X: volume vendido;
- eixo Y: margem percentual.

Quadrantes e plano de ação:
- **Estrelas**: alto volume e alta margem. Proteger disponibilidade e manter destaque comercial.
- **Vacas Leiteiras**: alto volume e baixa margem. Otimizar custos e revisar preço/tamanho.
- **Dilemas**: baixo volume e alta margem. Testar campanhas e canais para ganhar escala.
- **Problemas**: baixo volume e baixa margem. Reprecificar, reformular ou descontinuar.

### Tabela de Decisão e Alertas
- **Vermelho**: margem negativa (produto em perda).
- **Oliva**: custo/margem ausente (`NaN`), item precisa de auditoria antes de decisão.

Leitura recomendada:
1. tratar primeiro linhas vermelhas;
2. resolver pendências oliva (dados faltantes);
3. priorizar ganhos por quadrante.

## Stack Técnica

- **Python**: orquestração e regras de negócio.
- **Streamlit**: interface executiva.
- **Pandas**: transformação e modelagem tabular.
- **Plotly**: visualizações analíticas interativas.

## Regras de Limpeza e Qualidade de Dados

Princípios aplicados para evitar diagnósticos errados:
- conversão robusta de moeda e datas com fallback controlado;
- padronização de chaves textuais para reduzir mismatches;
- tratamento explícito de `None`/`NaN` em custos;
- invalidação de margem/markup quando custo está ausente ou zero;
- diferenciação entre dado ausente e valor real zero.

Essas regras evitam **falsos positivos de lucratividade** e preservam confiabilidade analítica.

## Execução Local

```bash
uv sync
uv run pytest -q
uv run streamlit run app.py
```

## Documentação Complementar

- `docs/GUIA_USUARIO_NEGOCIO.md`
- `docs/ARQUITETURA_TECNICA.md`
