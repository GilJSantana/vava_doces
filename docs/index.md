# Documentação - Vava Doces

Portal principal da documentação do projeto na arquitetura atual.

## Arquitetura Atual

O projeto hoje segue estes princípios:

- autenticação via Google OAuth2;
- autorização baseada em permissões no Google Drive;
- configuração principal via `st.secrets`;
- pipeline Medallion para materialização Bronze → Silver → Gold;
- Google Drive como persistência principal dos ativos `.parquet`;
- 3 páginas executivas no Streamlit:
  - `📊 Dashboard`
  - `💰 Custos de Produção`
  - `💹 Faturamento (Auditoria)`

## Guias Ativos

- [Quick Start Streamlit](QUICK_START_STREAMLIT.md)
- [Quick Start Faturamento](QUICK_START_FATURAMENTO.md)
- [Arquitetura Técnica](ARQUITETURA_TECNICA.md)
- [Integração da Gold Layer](GOLD_LAYER_INTEGRATION.md)
- [Implementação de Segurança OAuth2](IMPLEMENTACAO_SEGURANCA_OAUTH2.md)
- [Guia Operacional de Inicialização](operacional/GUIA_INICIALIZACAO.md)
- [Roadmap / Próximos Passos](NEXT_STEPS.md)

## Documentos de Referência

- [Guia do Usuário de Negócio](GUIA_USUARIO_NEGOCIO.md)
- [Arquivo Histórico](archive/README.md)

## Conteúdo Histórico / Legado

Alguns documentos em `docs/` registram fases anteriores do projeto, refatorações antigas e checkpoints de entrega. Eles foram preservados para histórico, mas não devem ser tratados como fonte principal da arquitetura atual.

Se você encontrar links antigos para `INDEX.md`, use esta página (`index.md`) como entrada canônica.

