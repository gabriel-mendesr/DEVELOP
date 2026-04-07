# Guia de Desenvolvimento — Hotel Santos

## Arquitetura do Projeto

O sistema é uma aplicação web com **FastAPI** + **Jinja2** + **PostgreSQL**.

- **Módulo `web/`:** Toda a lógica ativa — rotas, templates, banco de dados.
- **Módulo `app/` (Legado):** Interface Desktop (CustomTkinter) inativa. Consultar apenas para lógica de negócio em `app/core/` enquanto a migração não for concluída.

## Guia de Comandos

### Configuração e Execução

- **Instalar dependências:** `pip install -r web/requirements.txt`
- **Executar o servidor:** `cd web && uvicorn main:app --reload`

### Testes e Qualidade

- **Todos os testes:** `pytest`
- **Teste único:** `pytest tests/test_filename.py`
- **Linter (geral):** `ruff check .`
- **Linter (arquivo):** `ruff check caminho/do/arquivo.py`
- **Formatação:** `ruff format .`
- **Tipagem (Core):** `mypy app/core/`
- **CI Local:** `make check`

## Padrões de Código

### Regras de Ouro e Estilo

- **Rotas:** definidas em `web/main.py` com decoradores FastAPI (`@app.get`, `@app.post`).
- **Banco de Dados:** **NÃO use ORM** (SQLAlchemy/Django). Use SQL puro via `psycopg2` em `web/db_pg.py`.
- **Frontend:** Jinja2 em `web/templates/`. O layout mestre é `web/templates/base.html`.
- **Exportações:** `web/exporters.py` para geração de PDF/Excel.
- **Nomenclatura:**
  - Variáveis e funções: `snake_case`
  - Classes: `PascalCase`
  - Constantes: `CAPS_SNAKE_CASE`
- **Tipagem:** Type hints em todos os novos métodos.
- **Documentação:** Docstrings em português para funções complexas.

### Banco de Dados

- Queries diretas com `psycopg2` — sem ORM.
- Toda interação com o banco passa por funções em `web/db_pg.py`.
- Variável de ambiente para conexão: `DATABASE_URL`.

### Tratamento de Erros

- Erros de validação devem levantar `HTTPException` com código e mensagem adequados.
- Exibição de erros ao usuário via template `web/templates/erro.html`.

## Estado do Projeto

- **Prioridade:** Web (FastAPI). O diretório `app/` é legado e deve ser consultado apenas para lógica de negócio.
- **Core:** A lógica em `app/core/` está sendo migrada ou reutilizada no backend web.
- **Documentação:** Manuais de usuário em Markdown residem em `web/static/docs/`.

## Estrutura de Pastas

```text
develop/
├── web/                        # Módulo Web (Ativo)
│   ├── main.py                 # Rotas FastAPI e ponto de entrada
│   ├── db_pg.py                # Acesso ao PostgreSQL
│   ├── exporters.py            # Geração de PDF e relatórios
│   ├── requirements.txt        # Dependências de produção
│   ├── templates/              # Templates Jinja2
│   │   ├── base.html           # Layout base (sidebar, nav)
│   │   └── *.html              # Telas individuais
│   └── static/                 # CSS, ícones e documentação web
│       └── docs/               # Manuais servidos em /ajuda
├── app/                        # Módulo Desktop (Legado)
│   └── core/                   # Lógica de negócio — consultar durante migração
├── tests/                      # Suite de Testes
│   ├── test_models.py          # Testes unitários (legados — app/core)
│   └── verificar_sistema.py    # Verificações de integridade (legadas)
├── docs/                       # Documentação geral
├── pyproject.toml              # Configurações de Ruff, Mypy e Pytest
├── Makefile                    # Atalhos (make lint, test, check)
└── .pre-commit-config.yaml     # Hooks de qualidade (Ruff, Mypy)
```
