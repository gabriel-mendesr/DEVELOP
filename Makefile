# =============================================================================
# Makefile — Atalhos para tarefas comuns de desenvolvimento
# =============================================================================
#
# COMO VER TODOS OS COMANDOS:
#   make help
#
# SETUP INICIAL (rodar uma vez após clonar):
#   make install
#
# DIA A DIA:
#   make test-fast  → testa rápido enquanto desenvolve
#   make check      → valida tudo antes de fazer push
#
# =============================================================================

PYTHON   := python3
APP_DIR  := app
TEST_DIR := tests

VERDE   := \033[0;32m
AMARELO := \033[0;33m
VERMELHO:= \033[0;31m
RESET   := \033[0m

.PHONY: help install test test-fast lint format typecheck check clean build version

# =============================================================================
help:
	@echo ""
	@echo "  Sistema Hotel Santos — Comandos disponíveis"
	@echo "  ─────────────────────────────────────────────"
	@echo "  $(VERDE)make install$(RESET)     Instala dependências de desenvolvimento"
	@echo "  $(VERDE)make test$(RESET)        Roda testes com cobertura"
	@echo "  $(VERDE)make test-fast$(RESET)   Roda testes sem cobertura (mais rápido)"
	@echo "  $(VERDE)make lint$(RESET)        Verifica estilo com ruff"
	@echo "  $(VERDE)make format$(RESET)      Formata o código automaticamente"
	@echo "  $(VERDE)make typecheck$(RESET)   Verifica tipos com mypy"
	@echo "  $(VERDE)make check$(RESET)       Lint + tipos + testes (simula o CI)"
	@echo "  $(VERDE)make version$(RESET)     Mostra a versão atual calculada pelo git"
	@echo "  $(VERDE)make clean$(RESET)       Remove cache e arquivos temporários"
	@echo "  $(VERDE)make build$(RESET)       Gera o executável com PyInstaller"
	@echo ""

# =============================================================================
# install
# =============================================================================
install:
	@echo "$(AMARELO)▶ Atualizando pip...$(RESET)"
	$(PYTHON) -m pip install --upgrade pip

	@echo "$(AMARELO)▶ Instalando setuptools-scm primeiro...$(RESET)"
	$(PYTHON) -m pip install "setuptools>=68.0" "setuptools-scm>=8.0"
	#
	# Por que isso é necessário?
	# setuptools-scm precisa estar instalado ANTES do "pip install -e ."
	# porque o pyproject.toml usa dynamic = ["version"], o que significa
	# que pip precisa do setuptools-scm para calcular a versão na hora
	# de instalar o próprio pacote.

	@echo "$(AMARELO)▶ Instalando dependências do projeto...$(RESET)"
	$(PYTHON) -m pip install -e ".[dev]"

	@echo "$(AMARELO)▶ Instalando hooks de pre-commit...$(RESET)"
	pre-commit install

	@echo "$(VERDE)✅ Ambiente configurado!$(RESET)"
	@echo ""
	@echo "  Versão atual: $$($(PYTHON) -m setuptools_scm 2>/dev/null || echo 'sem tag git ainda')"
	@echo ""
	@echo "  Próximos passos:"
	@echo "    make check       → valida que tudo está funcionando"
	@echo "    make version     → vê a versão calculada pelo git"
	@echo ""

# =============================================================================
# test
# =============================================================================
test:
	@echo "$(AMARELO)▶ Rodando testes com cobertura...$(RESET)"
	cd $(APP_DIR) && $(PYTHON) -m pytest ../$(TEST_DIR)/ \
		--cov=core \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-fail-under=70
	@echo "$(VERDE)✅ Relatório HTML: app/htmlcov/index.html$(RESET)"

test-fast:
	@echo "$(AMARELO)▶ Rodando testes (sem cobertura)...$(RESET)"
	cd $(APP_DIR) && $(PYTHON) -m pytest ../$(TEST_DIR)/ -v

# =============================================================================
# lint / format / typecheck
# =============================================================================
lint:
	@echo "$(AMARELO)▶ Verificando com ruff...$(RESET)"
	ruff check $(APP_DIR)/
	@echo "$(VERDE)✅ Sem problemas$(RESET)"

format:
	@echo "$(AMARELO)▶ Formatando com ruff...$(RESET)"
	ruff format $(APP_DIR)/
	ruff check $(APP_DIR)/ --fix
	@echo "$(VERDE)✅ Código formatado$(RESET)"

typecheck:
	@echo "$(AMARELO)▶ Verificando tipos com mypy...$(RESET)"
	mypy $(APP_DIR)/core/
	@echo "$(VERDE)✅ Tipos OK$(RESET)"

# =============================================================================
# check — simula o CI localmente
# =============================================================================
check: lint typecheck test
	@echo ""
	@echo "$(VERDE)══════════════════════════════════════$(RESET)"
	@echo "$(VERDE)  ✅  Tudo certo! Pode fazer o push.  $(RESET)"
	@echo "$(VERDE)══════════════════════════════════════$(RESET)"
	@echo ""

# =============================================================================
# version — mostra a versão calculada pelo git
# =============================================================================
version:
	@echo ""
	@echo "$(AMARELO)Versão calculada pelo setuptools-scm:$(RESET)"
	@$(PYTHON) -m setuptools_scm
	@echo ""
	@echo "$(AMARELO)Última tag git:$(RESET)"
	@git describe --tags --abbrev=0 2>/dev/null || echo "  (nenhuma tag criada ainda)"
	@echo ""
	@echo "$(AMARELO)Para criar a primeira tag:$(RESET)"
	@echo "  git tag v1.0.0"
	@echo "  git push origin v1.0.0"
	@echo ""

# =============================================================================
# clean
# =============================================================================
clean:
	@echo "$(AMARELO)▶ Limpando...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(APP_DIR)/htmlcov/ $(APP_DIR)/.coverage .mypy_cache/ .ruff_cache/ dist/ build/
	@echo "$(VERDE)✅ Limpo$(RESET)"

# =============================================================================
# build
# =============================================================================
build:
	@echo "$(AMARELO)▶ Gerando executável...$(RESET)"
	cd $(APP_DIR) && pyinstaller \
		--onefile \
		--windowed \
		--name "HotelSantos" \
		--icon="app.ico" \
		app_gui.py
	@echo "$(VERDE)✅ Executável em: app/dist/HotelSantos$(RESET)"
