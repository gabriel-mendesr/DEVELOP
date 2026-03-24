# Sistema Hotel Santos

Sistema desktop de gestão de hóspedes e créditos para o Hotel Santos, desenvolvido em Python com interface CustomTkinter.

![CI](https://github.com/gabriel-mendesr/DEVELOP/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licença](https://img.shields.io/badge/licença-privada-lightgrey)

---

## Funcionalidades

- **Hóspedes** — cadastro, edição, histórico de créditos e filtros por status (vencendo, vencidos, com multa)
- **Financeiro** — lançamentos de entrada/saída, ajuste manual de datas de vencimento
- **Compras** — registro de compras por lista, adição de itens e controle de status
- **Dashboard** — visão geral do sistema com indicadores em tempo real
- **Configurações** — gerenciamento de usuários e permissões (admin/operador)
- **Busca global** — localiza hóspedes pelo campo de busca no topo, disponível em qualquer tela
- **Tema claro/escuro** — troca em tempo real sem reiniciar; Treeview segue o tema corretamente
- **Logger** — registro automático de operações críticas via `LoggerSystem`

---

## Estrutura do Projeto

```
develop/
├── app/
│   ├── app_gui.py          # Janela principal e navegação entre telas
│   ├── core/
│   │   ├── models.py       # Regras de negócio (créditos, multas, hóspedes)
│   │   └── database.py     # Camada de acesso ao SQLite
│   ├── screens/
│   │   ├── base.py         # Classe TelaBase — layout e componentes reutilizáveis
│   │   ├── hospedes.py     # Tela de hóspedes
│   │   ├── financeiro.py   # Tela financeira
│   │   ├── compras.py      # Tela de compras
│   │   ├── dashboard.py    # Dashboard
│   │   └── config.py       # Configurações
│   └── logger_system.py    # Sistema de log de operações
├── tests/
│   ├── test_models.py      # Testes unitários do core
│   └── verificar_sistema.py # Suite de 82 verificações de integridade
├── pyproject.toml          # Configuração central (build, ruff, mypy, pytest)
├── Makefile                # Atalhos para tarefas comuns
└── .github/workflows/
    ├── ci.yml              # Lint + tipos + testes (Python 3.10, 3.11, 3.12)
    └── build-release.yml   # Geração do executável Windows via PyInstaller
```

---

## Requisitos

- Python 3.10 ou superior
- Windows, Linux ou macOS

---

## Instalação

```bash
# Clone o repositório
git clone https://github.com/gabriel-mendesr/DEVELOP.git
cd DEVELOP

# Configure o ambiente de desenvolvimento (instala deps + hooks de pre-commit)
make install

# Verifique se está tudo funcionando
make check
```

---

## Uso

```bash
# Inicia a aplicação
cd app
python app_gui.py
```

---

## Testes

```bash
# Testes com relatório de cobertura (mínimo 70%)
make test

# Testes rápidos sem cobertura
make test-fast
```

Os testes cobrem toda a camada `app/core/` e incluem a suite `verificar_sistema.py` com 82 verificações de integridade do banco e das regras de negócio. Nenhum teste exige interface gráfica — todos rodam em CI headless.

---

## Qualidade de Código

```bash
make lint        # Verifica estilo com ruff
make format      # Formata automaticamente
make typecheck   # Verifica tipos com mypy
make check       # Lint + tipos + testes (equivalente ao CI)
```

---

## Versionamento

A versão é calculada automaticamente a partir das tags git via `setuptools-scm`:

```bash
# Ver a versão atual
make version

# Lançar uma nova versão
git tag v1.2.0
git push origin v1.2.0
```

Ao fazer push de uma tag `v*`, o workflow `build-release.yml` gera o instalador Windows automaticamente.

---

## Pipeline de CI

Cada push dispara três jobs em paralelo:

| Job | Ferramenta | O que verifica |
|-----|-----------|----------------|
| 🔍 Linter | ruff | Estilo, imports, código morto |
| 🔎 Tipos | mypy | Coerência de tipos em `app/core/` e `app/app_gui.py` |
| 🧪 Testes | pytest | Regras de negócio e integridade do banco (Python 3.10–3.12) |

---

## Compilação para Windows

O executável é gerado pelo GitHub Actions no push de uma tag:

```
Actions → build-release → Artifacts → SistemaHotelSantos-Setup-Windows.exe
```

Para gerar localmente (requer Windows ou Wine):

```bash
make build
```
