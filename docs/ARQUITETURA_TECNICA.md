# Arquitetura Tecnica

## Visao Geral

A solucao segue padrao de Engenharia de Dados com separacao entre ingestao, tratamento e consumo analitico.

Fluxo principal:
1. ingestao de fontes operacionais (Drive e Sheets);
2. normalizacao e validacao em pipeline Medallion;
3. publicacao de tabelas Gold para o app Streamlit.

## Stack Principal

- **Python**: orquestracao de pipeline e regras de negocio.
- **Streamlit**: camada de apresentacao executiva.
- **Pandas**: limpeza, joins, agregacoes e transformacoes tabulares.
- **Plotly**: visualizacoes interativas para analise de rentabilidade.

## Fontes de Dados

- Arquivos de vendas em CSV/XLSX sincronizados do Google Drive.
- Abas operacionais do Google Sheets (produtos, receitas e materia-prima).

## Arquitetura Medallion

### Bronze
- Persistencia do dado bruto.
- Rastreabilidade de origem por arquivo.

### Silver
- Padronizacao de headers e tipos.
- Parsing robusto de datas e valores monetarios.
- Deduplicacao tecnica sem perda de granularidade legitima.

### Gold
- Modelagem para consumo analitico (fato, dimensoes e agregados).
- Tabela de rentabilidade com colunas auditaveis para margem e markup.

## Regras de Limpeza e Confiabilidade

As regras abaixo evitam leituras falsas de lucratividade:

- **Normalizacao textual**: remove variacoes de acento/espaco para reduzir falha de join.
- **Conversao monetaria robusta**: trata formatos BRL mistos para evitar erro de parse.
- **Parsing de data por origem**: reduz ambiguidade entre formatos US e BR.
- **Tratamento de NoneType/NaN**:
  - custo ausente nao e convertido em lucro artificial;
  - margem e markup sao invalidados quando custo e nulo ou zero;
  - itens com dados faltantes permanecem auditaveis no front-end.
- **Semantica de ausencia vs zero**: diferencia dado faltante de valor legitimo igual a zero.

## Resultado Arquitetural

Com esse desenho, o app entrega:
- visao executiva confiavel de rentabilidade;
- trilha auditavel para correcoes de dados;
- base tecnica estavel para evolucao incremental do produto.

