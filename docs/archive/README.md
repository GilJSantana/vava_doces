# Arquivo Histórico

Esta seção reúne documentos preservados apenas para contexto histórico do projeto.

## Quando usar

Consulte estes arquivos apenas se você precisar entender:

- fases antigas da refatoração do Streamlit;
- checkpoints de entrega e relatórios intermediários;
- resumos operacionais que não representam mais a arquitetura atual.

## Fonte principal da arquitetura atual

Para o estado vigente do projeto, use:

- [`../index.md`](../index.md)
- [`../QUICK_START_STREAMLIT.md`](../QUICK_START_STREAMLIT.md)
- [`../ARQUITETURA_TECNICA.md`](../ARQUITETURA_TECNICA.md)
- [`../IMPLEMENTACAO_SEGURANCA_OAUTH2.md`](../IMPLEMENTACAO_SEGURANCA_OAUTH2.md)
- [`../GOLD_LAYER_INTEGRATION.md`](../GOLD_LAYER_INTEGRATION.md)

## Conteúdo arquivado

Os documentos foram agrupados por tema e data para reduzir ruído na raiz de `docs/` e na navegação do MkDocs.

### 2026-02 · Refatoração inicial do Streamlit

Pasta: [`streamlit_refactor_2026_02/`](streamlit_refactor_2026_02/)

Documentos principais:
- [`REFACTORING_SUMMARY.md`](streamlit_refactor_2026_02/REFACTORING_SUMMARY.md)
- [`README_REFATORACAO.txt`](streamlit_refactor_2026_02/README_REFATORACAO.txt)
- [`PROJECT_COMPLETION_REPORT.txt`](streamlit_refactor_2026_02/PROJECT_COMPLETION_REPORT.txt)

Materiais complementares:
- [`FINAL_CHECKLIST.txt`](streamlit_refactor_2026_02/FINAL_CHECKLIST.txt)
- [`FILES_SUMMARY.txt`](streamlit_refactor_2026_02/FILES_SUMMARY.txt)
- [`STREAMLIT_REFACTORING_SUMMARY.txt`](streamlit_refactor_2026_02/STREAMLIT_REFACTORING_SUMMARY.txt)
- [`ARQUIVOS_CRIADOS.txt`](streamlit_refactor_2026_02/ARQUIVOS_CRIADOS.txt)
- [`COMMIT_HISTORY_NEW.md`](streamlit_refactor_2026_02/COMMIT_HISTORY_NEW.md)

Use este grupo apenas para entender a fase antiga em que a aplicação ainda descrevia 7 páginas operacionais e uma arquitetura anterior ao fluxo executivo atual.

### 2026-04 · Ajustes de largura e refatoração visual do Streamlit

Pasta: [`streamlit_width_refactor_2026_04/`](streamlit_width_refactor_2026_04/)

Documentos principais:
- [`REFACTORING_SUMMARY.md`](streamlit_width_refactor_2026_04/REFACTORING_SUMMARY.md)
- [`TECHNICAL_REFACTORING_REPORT.md`](streamlit_width_refactor_2026_04/TECHNICAL_REFACTORING_REPORT.md)
- [`FINAL_EXECUTION_SUMMARY.md`](streamlit_width_refactor_2026_04/FINAL_EXECUTION_SUMMARY.md)

Validação:
- [`refactoring_verification.md`](streamlit_width_refactor_2026_04/refactoring_verification.md)

### 2026-04 · Rollout de segurança OAuth2

Pasta: [`security_rollout_2026_04/`](security_rollout_2026_04/)

Documentos principais:
- [`SECURITY_IMPLEMENTATION_COMPLETE.md`](security_rollout_2026_04/SECURITY_IMPLEMENTATION_COMPLETE.md)
- [`OAUTH2_IMPLEMENTATION_COMPLETE.txt`](security_rollout_2026_04/OAUTH2_IMPLEMENTATION_COMPLETE.txt)

Este grupo registra a fase de implantação inicial da camada de segurança antes dos ajustes finais para `st.secrets`, `gcp_service_account` e a arquitetura atual do Drive-backed Gold layer.

### 2026-04 · Deduplicação e correções de pipeline

Pasta: [`dedup_fix/`](dedup_fix/)

Documentos principais:
- [`DEDUP_FIX_IMPLEMENTATION.md`](dedup_fix/DEDUP_FIX_IMPLEMENTATION.md)
- [`COMMITS_DEDUP_FIX.md`](dedup_fix/COMMITS_DEDUP_FIX.md)
- [`TASK_COMPLETION_SUMMARY.md`](dedup_fix/TASK_COMPLETION_SUMMARY.md)

### Releases e marcos de entrega

Pasta: [`releases/`](releases/)

Documentos disponíveis:
- [`PROJETO_CONCLUIDO_FINAL.md`](releases/PROJETO_CONCLUIDO_FINAL.md)
- [`PROJETO_FINALIZADO.md`](releases/PROJETO_FINALIZADO.md)

## Como navegar pelo histórico

- Se você quer entender a **arquitetura atual**, volte para [`../index.md`](../index.md).
- Se você quer entender **como a interface já foi organizada no passado**, comece por `streamlit_refactor_2026_02/`.
- Se você quer investigar **o rollout antigo de OAuth2**, consulte `security_rollout_2026_04/`.
- Se você quer rastrear **correções de dados e deduplicação**, consulte `dedup_fix/`.


