# 📚 Guia para Próximos Desenvolvedores: Correção de Parsing de Datas

## 🔍 Contexto Técnico

### Problema Resolvido
O módulo de faturamento estava descartando silenciosamente 31.3% dos dados (1906 registros) porque o arquivo de vendas continha datas em **DOIS formatos diferentes**:
- Fevereiro: `MM/DD/YYYY` (02/01/2026 = 2 de fevereiro)
- Janeiro: `DD/MM/YYYY` (13/01/2026 = 13 de janeiro)

### Solução Implementada
Refatoração de `_parse_sales_date()` em `src/domain/sales_analysis_service.py` com fallback automático:

```python
1. Tenta formato US (mm/dd/yyyy)
2. Se falhar → tenta formato BR (dd/mm/yyyy)
3. Se ainda falhar → tenta formato ISO (yyyy-mm-dd)
```

---

## 🛠️ Como Executar os Testes

### Teste 1: Diagnóstico Completo
```bash
cd /home/gilunix/Documents/Projects/Vava_doces
python tests/diagnose_sales_date_parsing.py
```

**O que faz**: Análise completa do pipeline em 6 fases
- Coleta de dados
- Análise de formatos
- Comparação de parsers
- Investigação de inválidos
- Amostra com 3 interpretações
- Pipeline completo

**Esperado**: 100% válidos, 6066 registros

### Teste 2: Análise de Inválidos
```bash
python tests/diagnose_invalid_dates.py
```

**O que faz**: Investiga detalhadamente as datas inválidas
- Amostra das datas inválidas
- Análise de padrões
- Teste de formatos alternativos

**Esperado**: Com fallback BR, 1906 registros ficam válidos

### Teste 3: Validação de Filtros
```bash
python tests/test_date_filtering_fix.py
```

**O que faz**: Valida os filtros de data na página de faturamento
- Filtro por janeiro (esperado: 1900)
- Filtro por fevereiro (esperado: 3413)
- Filtro por período (esperado: 5313)
- Total de 2026 (esperado: 6066)

**Esperado**: Todos os testes passam ✅

### Teste 4: Validação na UI
```bash
python -c "
import os
from dotenv import load_dotenv
from src.presentation.pages.faturamento import _diagnose_date_parsing, _normalize_data, _apply_filters
from src.presentation.pages.sales_shared import load_sales_data_cached
from datetime import date

load_dotenv()
df_raw = load_sales_data_cached()
df_base = _normalize_data(df_raw)
df_jan = _apply_filters(df_base, date(2026, 1, 1), date(2026, 1, 31), [])
print(f'Janeiro: {len(df_jan)} registros (esperado: 1900)')
"
```

---

## 📂 Arquivos Modificados

### Core
- **src/domain/sales_analysis_service.py**
  - Função: `_parse_sales_date()`
  - Mudança: Adicionado fallback para DD/MM/YYYY e YYYY-MM-DD
  - Linhas: ~25 linhas modificadas

### Testes Novos
- **tests/diagnose_sales_date_parsing.py** (300+ linhas)
- **tests/diagnose_invalid_dates.py** (150+ linhas)
- **tests/test_date_filtering_fix.py** (70+ linhas)

### Documentação
- **docs/CORRECAO_PARSING_DATAS_FATURAMENTO.md**
- **docs/RELATORIO_FINAL_CORRECAO_FATURAMENTO.md**

---

## 🔧 Quando Usar Esta Solução

### ✅ Use se:
- Seus dados estão em múltiplos formatos de data
- Precisa suportar dados brasileiros e americanos
- Quer fallback automático sem perda de dados
- Trabalha com CSVs/XLSXs de origem inconsistente

### ❌ Não use se:
- Todos os dados estão em um único formato (use parsing direto)
- A perda de dados é aceitável (mais simples)
- Precisa de validação rigorosa (sem fallback)

---

## 🚨 Possíveis Problemas

### Problema 1: Ambigüidade
```
Entrada: "01/02/2026"
MM/DD: 1º de fevereiro
DD/MM: 2 de janeiro

Solução: Tenta MM/DD primeiro (padrão Excel/EUA)
Resultado: Alguns registros podem ser parseados incorretamente
```

**Como mitigar**:
- Validar dados de origem
- Documentar formato esperado
- Adicionar coluna de audit (_source_file já presente)

### Problema 2: Performance
Se tiver milhões de registros, o fallback pode ser lento.

**Como mitigar**:
```python
# Processar em chunks
chunk_size = 10000
for i in range(0, len(df), chunk_size):
    df.iloc[i:i+chunk_size] = process_chunk(...)
```

### Problema 3: Novos Formatos
Se encontrar um novo formato de data, adicione:

```python
# Em _parse_sales_date()
# Fallback 3: Novo formato
another_missing = parsed.isna()
if another_missing.any():
    custom = pd.to_datetime(
        text[another_missing],
        format="%d-%m-%Y",  # Seu formato
        errors="coerce"
    )
    parsed.loc[another_missing] = custom
```

---

## 📊 Métricas Para Monitorar

### Em Produção, Verifique:
1. **Taxa de Parsing**: % de datas válidas
   - Esperado: ≥ 99%
   - Alerta: < 95%

2. **Distribuição Mensal**: Verificar padrão
   - Verificar se há período com 0 registros
   - Comparar com período anterior

3. **Quantidade de Fallbacks**: Logs de quando BR/ISO foi usado
   - Normal: alguns % dos dados
   - Anormal: > 50% dos dados

### Adicionar Logging
```python
if br_used > (len(series) * 0.1):
    logger.warning(f"Alto uso de fallback BR: {br_used} registros")
```

---

## 🔄 Fluxo de Desenvolvimento

Se precisar modificar:

1. **Edite** `src/domain/sales_analysis_service.py`
2. **Execute** `tests/diagnose_sales_date_parsing.py`
3. **Valide** `tests/test_date_filtering_fix.py`
4. **Teste na UI** na página de faturamento
5. **Commit** com descrição clara

```bash
git commit -m "fix(data): adiciona suporte para formato YYYY-MM-DD/HH:MM:SS"
```

---

## 📞 Referências

### Documentação Interna
- `docs/CORRECAO_PARSING_DATAS_FATURAMENTO.md` - Documentação técnica
- `docs/RELATORIO_FINAL_CORRECAO_FATURAMENTO.md` - Relatório executivo

### Links Úteis
- [Pandas to_datetime](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)
- [Python datetime formats](https://docs.python.org/3/library/datetime.html)

### Commits Referência
- `91343e7` - Implementação original
- `ceca637` - Documentação final

---

## ✅ Checklist Para Modificação

- [ ] Li a documentação técnica
- [ ] Entendo o problema original
- [ ] Testei os 4 scripts de diagnóstico
- [ ] Minha mudança não quebra os testes
- [ ] Executei `diagnose_sales_date_parsing.py` com sucesso
- [ ] Executei `test_date_filtering_fix.py` com sucesso
- [ ] Documentei minha mudança
- [ ] Criei um commit descritivo
- [ ] Fiz push para GitHub

---

## 🎓 Lições Aprendidas (Para Evitar Problemas Similares)

1. **Sempre validar origem**: Verificar formatos de data no CSV/XLSX original
2. **Fallback robusto**: Não confie em parsing automático
3. **Diagnóstico isolado**: Criar scripts específicos para investigar
4. **Documentação**: Documentar formatos aceitos explicitamente
5. **Testes específicos**: Testar cada formato separadamente
6. **Dados mistos**: Estar preparado para múltiplos formatos

---

**Última Atualização**: 23 de março de 2026
**Desenvolvedor**: gsantana
**Status**: Ativo em Produção

