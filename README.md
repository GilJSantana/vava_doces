<div align="center">
  <img src="assets/logo.png" alt="Vava Doces Logo" width="200" height="200" style="border-radius: 20px;">
</div>

# Vava Doces - Análise de Custos, Margens e Rentabilidade

## Sobre o Projeto

Este repositório apresenta um pipeline de dados aplicado a um pequeno negócio real: a loja Vava Doces. O projeto integra planilhas operacionais (produtos, receitas, matéria-prima e vendas), processa os dados com regras de negócio e disponibiliza análises em um cockpit Streamlit.

O objetivo é transformar dados dispersos em informação acionável para gestão: custo por produto, margem, rentabilidade e impacto no faturamento.

Este projeto faz parte da minha transição profissional para área de dados, unindo minha experiência prévia em tecnologia (QA, automação, infraestrutura AWS) com análise orientada a negócio.

---

## Problema de Negócio e Contexto

A Vava Doces enfrentava um cenário comum em pequenos negócios:

- Não havia cadastro estruturado e confiável de produtos.
- A compra de matéria-prima era operacional, sem visão consolidada de custo por item vendido.
- O sistema contábil registrava vendas com inconsistências de padronização.
- Embora o dono percebesse o negócio "sem dívidas", o caixa chegava pressionado no fim do ano, reduzindo capacidade de investimento.

Esse contexto gera uma dor central: vender não significa necessariamente lucrar. Sem modelo de custo e margem por produto, decisões de preço e mix de vendas ficam no escuro.

---

## Principais Perguntas que o Projeto Responde

1. Quais produtos realmente geram lucro e quais apenas aumentam volume?
2. Quanto custa produzir (ou adquirir) cada produto, considerando sua composição?
3. Qual é a margem de contribuição por produto e por categoria?
4. Quais produtos têm maior impacto no faturamento total?
5. Onde existem distorções entre preço praticado e custo real?
6. Quais ajustes de preço podem melhorar caixa sem comprometer competitividade?
7. Como priorizar compras de matéria-prima e produção com base em rentabilidade?

---

## Como Funciona (Arquitetura)

A arquitetura segue separação clara entre regra de negócio e infraestrutura:

- `Ports` (`src/ports/data_source.py`): define o contrato `DataSource` para leitura de dados.
- `Adapters` (`src/infrastructure/google_sheets_adapter.py`): implementa acesso a Google Sheets via `gspread`.
- `Domain Services`:
  - `src/domain/cost_analysis_service.py`: calcula custo por produto e validações de schema.
  - `src/domain/product_analysis_service.py`: consolida métricas de produtos, margem e impacto de faturamento.
- `App` (`app.py`): interface Streamlit para visualização e apoio à decisão.

Esse desenho facilita testes, manutenção e troca de fonte de dados sem quebrar regras de negócio.

---

## Resultados Esperados para o Dono do Negócio

- Visibilidade clara de custo, margem e rentabilidade por produto.
- Base objetiva para ajustar precificação e mix de vendas.
- Redução de decisões por intuição e maior confiança na gestão do caixa.
- Identificação de produtos que drenam margem ou imobilizam capital.
- Prioridade de investimento em produtos mais rentáveis.
- Permitir ao dono entender por que, mesmo sem dívidas aparentes, o caixa termina o ano pressionado, identificando exatamente onde a margem é perdida.

---

## Estrutura Relevante do Projeto

- `app.py` - aplicação Streamlit (cockpit de análise).
- `src/ports/data_source.py` - contrato de acesso a dados (`DataSource`) e erro de integração.
- `src/infrastructure/google_sheets_adapter.py` - adaptador de leitura da planilha Google Sheets.
- `src/domain/cost_analysis_service.py` - regras de custo por produto.
- `src/domain/product_analysis_service.py` - regras para análise de produtos, margem e faturamento.
- `tests/` - suite com testes de domínio, infraestrutura e aplicação:
  - `tests/test_cost_analysis_service.py`
  - `tests/test_google_sheets_adapter.py`
  - `tests/test_streamlit_app.py`
  - `tests/test_integration.py`
- `scripts/run_app.sh` - script auxiliar para iniciar o Streamlit.

---

## Como Rodar Localmente (com `uv`)

Os comandos abaixo assumem uso de `uv` no Linux (bash).

### 1) Instalar dependências

```bash
uv sync
```

Se preferir executar sem sincronizar lock completo:

```bash
uv pip install -e .
```

### 2) Configurar credenciais do Google Sheets

Crie um arquivo `.env` na raiz com:

```bash
GOOGLE_APPLICATION_CREDENTIALS="/caminho/absoluto/para/service-account.json"
GOOGLE_SHEET_ID="SEU_SHEET_ID"
```

### 3) Rodar testes

```bash
uv run pytest -q
```

### 4) Executar o Streamlit

```bash
uv run streamlit run app.py
```

Ou via script auxiliar:

```bash
bash scripts/run_app.sh
```

Aplicação disponível em `http://localhost:8501`.

---

## Boas Práticas Aplicadas

- Arquitetura em camadas com `ports/adapters` (baixo acoplamento).
- Inversão de dependência: domínio depende de contratos, não de bibliotecas externas.
- Princípios SOLID (com foco em SRP, DIP e OCP).
- TDD e testes unitários para regras de negócio críticas.
- Tratamento de erros de integração com exceções específicas.
- Organização voltada para evolução incremental e onboarding técnico.

---

## Próximos Passos e Melhorias

- Evoluir validação de schema das abas com relatório de inconsistências.
- Adicionar monitoramento de qualidade dos dados (campos obrigatórios, duplicidades, nulos).
- Criar indicadores de tendência (margem ao longo do tempo, sazonalidade e ruptura).
- Publicar documentação técnica no MkDocs + GitHub Pages.
- Configurar CI/CD com execução de testes e checks de qualidade a cada PR.

---

## Contato

Projeto desenvolvido por **Gsantana**.

- Email: `gilmar.jesus@gmail.com`
- Sugestões e melhorias: abra uma issue ou pull request neste repositório.

---

> Este projeto representa uma transição prática para a área de dados: conecta modelagem de negócio, engenharia de software e análise para gerar impacto real em pequenas empresas.
