# 🚀 Guia de Execução do Streamlit

## 📋 Pré-requisitos

Certifique-se de que:
1. O arquivo `.env` está configurado com suas credenciais do Google Sheets
2. Você tem `uv` instalado no seu sistema
3. As dependências foram instaladas (inclui `streamlit`)

## 🔧 Configuração Inicial

### 1. Preparar o arquivo `.env`

```bash
# Copiar o arquivo de exemplo
cp .env.example .env

# Editar o arquivo .env com suas credenciais
nano .env
```

Configure:
- `GOOGLE_APPLICATION_CREDENTIALS`: Caminho para o arquivo JSON da Service Account
- `GOOGLE_SHEET_ID`: ID da sua planilha do Google Sheets

### 2. Instalar dependências (se não tiver feito)

```bash
uv install
```

## ▶️ Executar a Aplicação

### Opção 1: Usando o script (Recomendado)

```bash
./run_app.sh
```

### Opção 2: Comando direto com `uv`

```bash
uv run streamlit run app.py
```

### Opção 3: Comando direto com Python

```bash
streamlit run app.py
```

## 📖 Acessar a Aplicação

Após iniciar, o Streamlit exibirá uma URL no terminal (geralmente `http://localhost:8501`).

Abra seu navegador e acesse:
```
http://localhost:8501
```

## 🎨 Estrutura da Aplicação

### Páginas Disponíveis

1. **📊 Dashboard**
   - Visão geral dos custos
   - Métricas principais
   - Gráficos de custos por receita
   - Tabela com detalhamento

2. **💰 Custos**
   - Exibição completa dos dados de custos
   - Filtros por receita
   - Download em CSV

3. **📈 Faturamento**
   - Exibição dos dados de faturamento
   - Estatísticas de vendas
   - Download em CSV

4. **🔍 Análise Detalhada**
   - Tabs com diferentes análises:
     - Custos por Receita
     - Margens (em desenvolvimento)
     - Relatórios (em desenvolvimento)

## 🔌 Configuração de Credenciais do Google

### Usar Service Account (Recomendado)

```bash
# 1. Criar Service Account no Google Cloud Console
# 2. Download do JSON da chave
# 3. Compartilhar a planilha com o e-mail da Service Account
# 4. Configurar GOOGLE_APPLICATION_CREDENTIALS no .env

export GOOGLE_APPLICATION_CREDENTIALS="/caminho/para/service-account.json"
```

## 🛠️ Troubleshooting

### Erro: "Arquivo .env não encontrado"
```bash
# Solução: Copiar arquivo de exemplo
cp .env.example .env
```

### Erro: "Failed to fetch data from Google Sheets"
- Verificar se o ID da planilha está correto
- Verificar se a Service Account tem acesso à planilha
- Verificar se o arquivo de credenciais é válido

### Erro: "Module not found"
```bash
# Reinstalar dependências
uv install --force
```

### Erro: "Port already in use"
```bash
# Mudar a porta (no comando)
streamlit run app.py --server.port 8502
```

## 📊 Sheets Esperadas

A aplicação espera as seguintes abas na planilha:

### 1. Aba "Custos"
Colunas obrigatórias (case-insensitive):
- `recipe`: Nome da receita
- `ingredient`: Nome do ingrediente (opcional)
- `qty`: Quantidade
- `unit_price`: Preço unitário

Exemplo:
| recipe | ingredient | qty | unit_price |
|--------|-----------|-----|-----------|
| Bolo de Chocolate | Cacau | 2 | 5.50 |
| Bolo de Chocolate | Açúcar | 1 | 3.00 |

### 2. Aba "Faturamento"
Estrutura flexível - será exibida conforme disponível

## 🔐 Segurança

- **Nunca comite** o arquivo `.env` ou credenciais JSON
- Use `GOOGLE_APPLICATION_CREDENTIALS` como variável de ambiente
- Para CI/CD, use secrets do GitHub/GitLab
- Arquivo `.env` já está no `.gitignore`

## 📝 Logs e Debugging

Para debugging mais detalhado:

```bash
# Ver logs do Streamlit
uv run streamlit run app.py --logger.level=debug
```

## 🎯 Próximas Melhorias

- [ ] Autenticação de usuários
- [ ] Relatórios exportáveis em PDF
- [ ] Cache de dados com TTL
- [ ] Notificações de alertas
- [ ] Integração com outras fontes de dados
- [ ] Temas customizáveis

---

**Dúvidas?** Consulte o README.md principal ou abra uma issue no repositório.

