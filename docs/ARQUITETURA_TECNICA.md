# Arquitetura Tecnica

## Visao Geral

A arquitetura atual combina autenticacao OAuth2, persistencia analitica em Google Drive e consumo executivo via Streamlit.

Fluxo principal:
1. autenticacao do usuario via Google OAuth2;
2. autorizacao por permissao no Google Drive;
3. sincronizacao/ingestao de dados operacionais quando necessario;
4. materializacao do pipeline Medallion em ativos Gold;
5. leitura dos `.parquet` diretamente do Google Drive em memoria;
6. publicacao de 3 paginas executivas no Streamlit.

## Stack Principal

- **Python**: orquestracao de pipeline, adaptadores e regras de negocio.
- **Streamlit**: camada de apresentacao e caching.
- **Pandas**: limpeza, joins, agregacoes e transformacoes tabulares.
- **Plotly**: visualizacoes interativas de rentabilidade.
- **Google Drive API**: persistencia principal dos ativos Gold em `.parquet`.
- **Google Sheets API**: apoio a planilhas operacionais e abas manuais.

## Componentes Centrais

- `app.py`
  - inicializa autenticacao/autorizacao;
  - executa `initialize_data_pipeline()`;
  - roteia a interface para 3 paginas executivas.
- `scripts/medallion_pipeline.py`
  - materializa Bronze, Silver e Gold;
  - publica os arquivos `.parquet` no Google Drive.
- `src/infrastructure/drive_manager.py`
  - descobre os ativos via `get_drive_assets_map()`;
  - carrega parquet com `load_parquet_from_drive()`;
  - atualiza parquet com `update_parquet_in_drive()`.
- `src/presentation/pages/`
  - `dashboard.py`;
  - `production_costs.py`;
  - `faturamento.py`.

## Fontes de Dados

- **Google Drive**: origem persistente dos arquivos Gold (`fato_vendas.parquet`, `gold_rentabilidade.parquet`, `custos_producao_agregado.parquet`, etc.).
- **Google Sheets**: base operacional e manual para cadastros, receitas e apoio de ingestao.
- **data/raw/**: cache local/transitorio para cenarios de fallback e diagnostico.

## Arquitetura Medallion

### Bronze
- ingestao de arquivos brutos CSV/XLSX;
- rastreabilidade por origem e arquivo.

### Silver
- padronizacao de headers e tipos;
- parsing robusto de datas e valores monetarios;
- deduplicacao tecnica sem perder granularidade legitima.

### Gold
- modelagem analitica para consumo executivo;
- fatos, dimensoes, agregados, custos e rentabilidade;
- persistencia principal em Google Drive com leitura diskless no app.

## Camada de Seguranca

- `OAUTH2_CLIENT_ID`, `OAUTH2_CLIENT_SECRET` e `OAUTH2_REDIRECT_URI` sao lidos de `st.secrets`.
- A Service Account e carregada a partir de `st.secrets["gcp_service_account"]`.
- O acesso ao app depende de permissao valida no `GOOGLE_DRIVE_FOLDER_ID`.

## Regras de Limpeza e Confiabilidade

As regras abaixo evitam leituras falsas de lucratividade:

- **Normalizacao textual**: reduz falhas de join entre vendas, custos e rentabilidade.
- **Conversao monetaria robusta**: trata formatos BRL mistos.
- **Parsing de data por origem**: reduz ambiguidade entre formatos US e BR.
- **Tratamento de NaN/zero em custos**:
  - custo ausente nao vira lucro artificial;
  - margem e markup sao invalidados quando custo ou preco sao invalidos;
  - itens sem custo permanecem auditaveis no front-end.
- **Leitura em memoria**: elimina dependencia de disco local volatil no Streamlit Cloud.

## Resultado Arquitetural

Com esse desenho, o app entrega:
- visao executiva confiavel de rentabilidade;
- trilha auditavel para correcoes de custos e chaves;
- armazenamento persistente em Google Drive;
- base tecnica estavel para evolucao incremental do produto.

