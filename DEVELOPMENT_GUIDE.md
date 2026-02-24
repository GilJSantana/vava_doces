# 👨‍💻 Guia de Desenvolvimento - Vava Doces

## 🎯 Fluxo de Desenvolvimento Recomendado

### 1. Preparar o Ambiente

```bash
# Entrar no diretório
cd /home/gilunix/Documents/Projects/Vava_doces

# Criar branch de desenvolvimento
git checkout -b develop

# Instalar dependências
uv install

# Verificar que tudo funciona
uv run pytest -v
```

### 2. Implementar Nova Feature

#### Passo 1: Escrever Teste (TDD)
```python
# tests/test_novo_feature.py
def test_nova_funcionalidade():
    """Describe what you want to implement"""
    # Arrange
    dados = {"receita": "Bolo", "custo": 10.0}
    
    # Act
    resultado = novo_feature(dados)
    
    # Assert
    assert resultado == esperado
```

#### Passo 2: Rodar Teste (deve falhar)
```bash
uv run pytest tests/test_novo_feature.py -v
# FAILED: ❌ AttributeError: 'NoneType' object...
```

#### Passo 3: Implementar Feature
```python
# src/domain/novo_feature.py
def novo_feature(dados):
    """Implement the actual feature"""
    return processar(dados)
```

#### Passo 4: Rodar Teste (deve passar)
```bash
uv run pytest tests/test_novo_feature.py -v
# PASSED: ✅
```

#### Passo 5: Refatorar (opcional)
- Melhorar legibilidade
- Remover duplicação
- Otimizar performance

#### Passo 6: Commit
```bash
git add src/ tests/
git commit -m "feat: adicionar novo feature

- Descrever o que foi implementado
- Listar pontos principais
- Mencionar dependências se houver"
```

---

## 📐 Estrutura de Código

### Adicionar Novo Serviço de Domínio

```python
# src/domain/novo_service.py
from src.ports.data_source import DataSource

class NovoService:
    """Descrição clara do serviço"""
    
    def __init__(self, data_source: DataSource):
        self.data_source = data_source
    
    def metodo_principal(self, param: str) -> dict:
        """
        Descrição do método.
        
        Args:
            param: Descrição do parâmetro
            
        Returns:
            dict: Resultado esperado
            
        Raises:
            ValueError: Se parametro inválido
        """
        # Implementação
        pass
```

### Adicionar Novo Adaptador

```python
# src/infrastructure/novo_adapter.py
from src.ports.data_source import DataSource, DataSourceError

class NovoAdapter(DataSource):
    """Adaptador para nova fonte de dados"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def get_data(self, sheet_name: str) -> pd.DataFrame:
        """Implementar método da porta"""
        try:
            # Conectar e recuperar dados
            data = self._fetch_from_source(sheet_name)
            return data
        except Exception as e:
            raise DataSourceError(f"Falha ao buscar dados: {e}")
```

### Adicionar Novo Teste

```python
# tests/test_novo.py
import pytest
from unittest.mock import Mock
from src.seu_modulo import SuaClasse

class TestSuaClasse:
    """Testes para SuaClasse"""
    
    @pytest.fixture
    def fixture_exemplo(self):
        """Setup para testes"""
        return {"dados": "exemplo"}
    
    def test_caso_feliz(self, fixture_exemplo):
        """Teste do fluxo principal"""
        resultado = SuaClasse().processar(fixture_exemplo)
        assert resultado == esperado
    
    def test_erro_esperado(self):
        """Teste de tratamento de erro"""
        with pytest.raises(ValueError):
            SuaClasse().processar(dados_invalidos)
```

---

## 🎨 Adicionar Nova Página no Streamlit

```python
# app.py
def show_nova_pagina(service):
    st.header("📊 Minha Nova Página")
    st.markdown("---")
    
    try:
        # Carregar dados
        dados = service.metodo()
        
        # Criar layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Métrica", valor)
        
        with col2:
            st.bar_chart(dados)
        
        # Adicionar ao menu
        # No sidebar, adicionar em page = st.radio():
        # elif page == "📊 Nova Página":
        #     show_nova_pagina(service)
        
    except Exception as e:
        st.error(f"❌ Erro: {e}")

# No main():
# Adicionar à lista de opções do st.radio()
```

---

## 🧪 Padrões de Teste

### Mock de Adaptador
```python
from unittest.mock import Mock

adapter = Mock(spec=GoogleSheetsAdapter)
adapter.get_data = Mock(return_value=df_teste)
service = CostAnalysisService(data_source=adapter)
```

### Fixture com Parametrização
```python
@pytest.mark.parametrize("entrada,esperado", [
    ({"receita": "Bolo"}, 10.0),
    ({"receita": "Brigadeiro"}, 5.0),
])
def test_multiplos_casos(entrada, esperado):
    assert funcao(entrada) == esperado
```

### Teste de Erro
```python
def test_erro():
    with pytest.raises(ValueError, match="Mensagem esperada"):
        funcao_que_falha()
```

---

## 📦 Adicionar Nova Dependência

### Instalar
```bash
# Se precisar adicionar nova biblioteca
uv add pandas-excel-reader  # ou qualquer outra

# Atualizar lock file
uv lock
```

### Usar em Código
```python
import pandas_excel_reader as per

# Usar a biblioteca
```

### Commit
```bash
git add pyproject.toml uv.lock
git commit -m "chore: adicionar dependência pandas-excel-reader"
```

---

## 🔍 Code Review Checklist

Antes de fazer PR, verificar:

- [ ] Testes passando: `uv run pytest -v`
- [ ] Sem warnings: `uv run pytest --disable-warnings`
- [ ] Type hints adicionados: `def funcao(param: str) -> dict:`
- [ ] Docstrings presentes: `"""Descrição clara""""`
- [ ] Sem código comentado ou debug
- [ ] Sem credenciais expostas
- [ ] Mensagem de commit clara e descritiva
- [ ] Branches atualizadas com main/develop

---

## 📝 Convenções de Código

### Nomes
```python
# Classes: PascalCase
class CostAnalysisService:
    pass

# Funções/métodos: snake_case
def calculate_cost_per_recipe():
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_RETRIES = 3
```

### Type Hints
```python
from typing import Dict, List, Optional

def processar(dados: Dict[str, float]) -> List[str]:
    """Sempre adicionar type hints"""
    return [str(k) for k in dados.keys()]

def opcional(param: Optional[str] = None) -> None:
    """Use Optional para parâmetros opcionais"""
    pass
```

### Docstrings
```python
def metodo(param: str) -> dict:
    """Breve descrição (uma linha).
    
    Descrição mais detalhada se necessário.
    Pode ter múltiplas linhas.
    
    Args:
        param: Descrição do parâmetro
        
    Returns:
        dict: Descrição do retorno
        
    Raises:
        ValueError: Quando param é inválido
        
    Examples:
        >>> resultado = metodo("teste")
        >>> resultado["chave"]
        "valor"
    """
    pass
```

---

## 🚀 Deploy e CI/CD

### GitHub Actions (em implementação)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install uv
      - run: uv install
      - run: uv run pytest -v
```

---

## 🐛 Debugging

### Print Debugging
```python
# Evitar print(), usar logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Valor: {valor}")
```

### Streamlit Debugging
```bash
# Com logs detalhados
uv run streamlit run app.py --logger.level=debug

# Verificar cache
# @st.cache_resource
# def minha_funcao():
#     return dados  # Verificar se está usando cache
```

### Python Debugger
```python
import pdb; pdb.set_trace()  # Pausar execução
# Comandos: n (next), c (continue), l (list), p var (print)
```

---

## 📚 Recursos Úteis

### Documentação Oficial
- [Pandas](https://pandas.pydata.org/docs/)
- [Streamlit](https://docs.streamlit.io/)
- [Pytest](https://docs.pytest.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

### Neste Projeto
- `README.md` - Visão geral
- `STREAMLIT_SETUP.md` - Setup Streamlit
- `IMPLEMENTATION_SUMMARY.md` - Resumo técnico
- `src/` - Exemplos de código
- `tests/` - Exemplos de testes

---

## 🤝 Contribuindo

1. **Fork** do repositório
2. **Branch** para sua feature (`git checkout -b feature/minha-feature`)
3. **Commit** com mensagens claras
4. **Push** para seu fork
5. **Pull Request** com descrição

Mensagens de commit:
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `test:` Testes
- `chore:` Manutenção
- `refactor:` Refatoração

---

## ✅ Checklist para Nova Feature

- [ ] Teste escrito e falhando
- [ ] Código implementado
- [ ] Teste passando
- [ ] Documentação atualizada
- [ ] Sem breaking changes
- [ ] Cobertura de testes > 80%
- [ ] Commit com mensagem clara

---

**Boa prática**: Sempre rode a suíte de testes antes de fazer push!

```bash
uv run pytest -v && git push
```

---

**Última atualização**: 24/02/2026

