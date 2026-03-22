"""
Testes Automatizados — Sistema Hotel Santos

O QUE SÃO TESTES?
------------------
Testes são pequenos programas que verificam se o seu código funciona.
Eles rodam AUTOMATICAMENTE e dizem "✅ Passou" ou "❌ Falhou".

POR QUE TESTAR?
  - Você muda algo na tela de compras e quer ter certeza que não
    quebrou o cálculo de saldo dos hóspedes.
  - Sem testes: você abre o app, cadastra um hóspede, faz uma entrada,
    faz uma saída, confere o saldo... toda vez que muda algo.
  - Com testes: roda "pytest" e em 2 segundos sabe se tudo continua OK.

COMO RODAR:
  cd develop/
  pytest tests/ -v

COMO LER OS RESULTADOS:
  test_cadastro_hospede_valido PASSED       ← Funcionou!
  test_saida_sem_saldo_bloqueia FAILED      ← Quebrou! Algo mudou.

ANATOMIA DE UM TESTE:
  def test_nome_descritivo():
      # 1. ARRANGE (Preparar): criar os dados necessários
      # 2. ACT (Agir): chamar a função que quer testar
      # 3. ASSERT (Verificar): conferir se o resultado é o esperado

CONCEITO: FIXTURE
  Uma fixture é uma "preparação" que roda antes de cada teste.
  No nosso caso, criamos um banco de dados limpo na memória.
  Assim cada teste começa do zero, sem lixo de testes anteriores.
"""

import os
import sys

import pytest

# Adiciona o diretório 'app' ao path para os imports funcionarem
# Isso é necessário porque os testes estão em tests/ e o código em app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from core.database import Database
from core.models import SistemaCreditos

# =============================================================================
# FIXTURES — Preparação que roda antes de cada teste
# =============================================================================


@pytest.fixture
def db():
    """
    Cria um banco de dados LIMPO na memória para cada teste.

    O QUE É ":memory:"?
    O SQLite pode criar um banco que vive só na memória RAM.
    Quando o teste termina, o banco desaparece. Perfeito porque:
      - Cada teste começa do zero (sem dados de testes anteriores)
      - É muito rápido (não escreve no disco)
      - Não polui seu banco de dados real
    """
    banco = Database(":memory:")
    yield banco
    banco.fechar()


@pytest.fixture
def sistema(db):
    """
    Cria uma instância do SistemaCreditos com banco limpo.

    Depende da fixture 'db' acima — o pytest sabe que precisa
    criar o db primeiro e passar como argumento.
    """
    return SistemaCreditos(db)


# =============================================================================
# TESTES DO BANCO DE DADOS
# =============================================================================


class TestDatabase:
    """Testes da camada de banco de dados (migrations, conexão)."""

    def test_banco_cria_com_sucesso(self, db):
        """
        Verifica se o banco é criado e as tabelas existem.

        ASSERT: se o banco foi criado corretamente, a tabela 'hospedes'
        deve existir.
        """
        db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hospedes'")
        resultado = db.cursor.fetchone()

        # assert = "eu afirmo que isso é verdade"
        # Se não for, o teste FALHA e mostra uma mensagem de erro.
        assert resultado is not None, "Tabela 'hospedes' deveria existir!"

    def test_versao_banco_esta_atualizada(self, db):
        """
        Verifica se todas as migrations foram aplicadas.

        A versão do banco deve ser igual ao número total de migrations.
        """
        from core.database import MIGRATIONS

        versao = db._get_versao_banco()
        assert versao == len(MIGRATIONS), f"Banco na versão {versao}, mas existem {len(MIGRATIONS)} migrations"

    def test_tabelas_essenciais_existem(self, db):
        """Verifica que TODAS as tabelas foram criadas."""
        tabelas_esperadas = [
            "hospedes",
            "categorias",
            "historico_zebra",
            "configs",
            "usuarios",
            "logs_auditoria",
            "compras",
            "listas_compras",
            "produtos",
            "funcionarios",
            "agenda",
            "anotacoes",
        ]

        db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas_reais = {row["name"] for row in db.cursor.fetchall()}

        for tabela in tabelas_esperadas:
            assert tabela in tabelas_reais, f"Tabela '{tabela}' não foi criada!"


# =============================================================================
# TESTES DE HÓSPEDES
# =============================================================================


class TestHospedes:
    """Testes do módulo de hóspedes (cadastro, busca)."""

    def test_cadastro_hospede_valido(self, sistema):
        """
        Testa cadastro com CPF válido.

        ARRANGE: preparamos nome e CPF válido
        ACT: chamamos cadastrar_hospede
        ASSERT: o hóspede deve estar no banco
        """
        # CPF válido para teste (gerado em sites de teste)
        sistema.cadastrar_hospede("João Silva", "52998224725")

        hospede = sistema.get_hospede("52998224725")
        assert hospede is not None
        assert hospede["nome"] == "JOÃO SILVA"  # Nome é salvo em maiúscula

    def test_cadastro_cpf_invalido_bloqueia(self, sistema):
        """
        Testa que CPF inválido é rejeitado.

        pytest.raises = "eu espero que essa função lance um erro".
        Se NÃO lançar erro, o teste FALHA.
        """
        with pytest.raises(ValueError, match="Documento inválido"):
            sistema.cadastrar_hospede("Maria", "11111111111")  # CPF repetido

    def test_busca_por_nome(self, sistema):
        """Testa busca parcial pelo nome."""
        sistema.cadastrar_hospede("Ana Paula Santos", "52998224725")
        sistema.cadastrar_hospede("Pedro Henrique", "11144477735")

        # Buscar "Ana" deve retornar só a Ana
        resultados = sistema.buscar_filtrado("Ana")
        assert len(resultados) == 1
        assert resultados[0][0] == "ANA PAULA SANTOS"

    def test_atualizar_hospede_existente(self, sistema):
        """Testa que cadastrar com mesmo documento ATUALIZA em vez de duplicar."""
        sistema.cadastrar_hospede("João Original", "52998224725", "11999990000")
        sistema.cadastrar_hospede("João Atualizado", "52998224725", "11888880000")

        hospede = sistema.get_hospede("52998224725")
        assert hospede["nome"] == "JOÃO ATUALIZADO"
        assert hospede["telefone"] == "11888880000"


# =============================================================================
# TESTES DE SALDO E MOVIMENTAÇÕES
# =============================================================================


class TestFinanceiro:
    """Testes do módulo financeiro (créditos, saldo, multas)."""

    def _criar_hospede(self, sistema):
        """Helper: cria um hóspede para usar nos testes financeiros."""
        sistema.cadastrar_hospede("Teste Financeiro", "52998224725")

    def test_saldo_inicial_zerado(self, sistema):
        """Hóspede recém-cadastrado deve ter saldo zero."""
        self._criar_hospede(sistema)
        saldo, venc, bloqueado = sistema.get_saldo_info("52998224725")

        assert saldo == 0.0
        assert venc == "N/A"
        assert bloqueado is False

    def test_entrada_aumenta_saldo(self, sistema):
        """Adicionar crédito deve aumentar o saldo."""
        self._criar_hospede(sistema)

        sistema.adicionar_movimentacao(
            doc="52998224725",
            valor="500,00",  # Formato brasileiro!
            categoria="Cortesia",
            tipo="ENTRADA",
            usuario="admin",
        )

        saldo, _, _ = sistema.get_saldo_info("52998224725")
        assert saldo == 500.0

    def test_saida_diminui_saldo(self, sistema):
        """Usar crédito deve diminuir o saldo."""
        self._criar_hospede(sistema)

        # Primeiro: adiciona crédito
        sistema.adicionar_movimentacao("52998224725", 500, "Cortesia", "ENTRADA")

        # Depois: usa parte do crédito
        sistema.adicionar_movimentacao("52998224725", 200, "Uso", "SAIDA")

        saldo, _, _ = sistema.get_saldo_info("52998224725")
        assert saldo == 300.0

    def test_saida_sem_saldo_bloqueia(self, sistema):
        """Tentar usar mais crédito do que tem deve dar erro."""
        self._criar_hospede(sistema)
        sistema.adicionar_movimentacao("52998224725", 100, "Cortesia", "ENTRADA")

        with pytest.raises(ValueError, match="Saldo insuficiente"):
            sistema.adicionar_movimentacao("52998224725", 200, "Uso", "SAIDA")

    def test_limpar_valor_formatos(self, sistema):
        """
        Testa conversão de diferentes formatos de valor.

        Isso é importante porque o usuário pode digitar:
        - "1.500,50" (formato brasileiro)
        - "1500.50" (formato americano)
        - "1500" (sem decimais)
        """
        assert sistema.limpar_valor("1.500,50") == 1500.50
        assert sistema.limpar_valor("100,00") == 100.0
        assert sistema.limpar_valor(42.5) == 42.5
        assert sistema.limpar_valor("") == 0.0
        assert sistema.limpar_valor(None) == 0.0

    def test_multa_e_pagamento(self, sistema):
        """Testa fluxo completo de multa → pagamento."""
        self._criar_hospede(sistema)

        # Aplica multa
        sistema.adicionar_multa("52998224725", 100, "Atraso")

        divida = sistema.get_divida_multas("52998224725")
        assert divida == 100.0

        # Paga parcialmente
        sistema.pagar_multa("52998224725", 60, "Dinheiro")

        divida = sistema.get_divida_multas("52998224725")
        assert divida == 40.0

    def test_pagar_multa_acima_divida_bloqueia(self, sistema):
        """Não pode pagar mais que a dívida."""
        self._criar_hospede(sistema)
        sistema.adicionar_multa("52998224725", 50, "Atraso")

        with pytest.raises(ValueError, match="excede a dívida"):
            sistema.pagar_multa("52998224725", 100, "Dinheiro")


# =============================================================================
# TESTES DE AUTENTICAÇÃO
# =============================================================================


class TestAuth:
    """Testes do módulo de autenticação."""

    def test_usuario_admin_padrao_existe(self, sistema):
        """O usuário 'gabriel' deve ser criado automaticamente."""
        user = sistema.verificar_login("gabriel", "132032")
        assert user is not None
        assert user["is_admin"] == 1

    def test_login_senha_errada_falha(self, sistema):
        """Senha errada deve retornar None (não dict vazio ou erro)."""
        user = sistema.verificar_login("gabriel", "senha_errada")
        assert user is None

    def test_login_usuario_inexistente_falha(self, sistema):
        """Usuário que não existe deve retornar None."""
        user = sistema.verificar_login("nao_existe", "123")
        assert user is None

    def test_criar_e_logar_novo_usuario(self, sistema):
        """Testa ciclo completo: criar usuário → fazer login."""
        sistema.salvar_usuario("maria", "abc123", False, True, False)

        user = sistema.verificar_login("maria", "abc123")
        assert user is not None
        assert user["is_admin"] == 0
        assert user["can_change_dates"] == 1


# =============================================================================
# TESTES DE CONFIGURAÇÃO
# =============================================================================


class TestConfig:
    """Testes das configurações do sistema."""

    def test_configs_padrao(self, sistema):
        """Verifica que as configs padrão foram criadas."""
        assert sistema.get_config("validade_meses") == 6
        assert sistema.get_config("alerta_dias") == 30
        assert sistema.get_config("tema") == 0  # Light mode

    def test_alterar_config(self, sistema):
        """Testa alteração de uma configuração."""
        sistema.set_config("alerta_dias", 15)
        assert sistema.get_config("alerta_dias") == 15

    def test_config_inexistente_retorna_padrao(self, sistema):
        """Config que não existe deve retornar 30 (padrão)."""
        assert sistema.get_config("chave_que_nao_existe") == 30


# =============================================================================
# TESTES DE COMPRAS
# =============================================================================


class TestCompras:
    """Testes do módulo de compras."""

    def test_criar_lista_compras(self, sistema):
        """Testa criação de lista de compras."""
        lista_id = sistema.criar_lista_compras("admin", "Lista de teste")
        assert lista_id > 0

        listas = sistema.get_listas_resumo()
        assert len(listas) >= 1

    def test_adicionar_item_lista(self, sistema):
        """Testa adição de item a uma lista."""
        lista_id = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra(
            data_compra="22/03/2026",
            produto="Arroz 5kg",
            qtd="2",
            valor_unit="25,90",
            lista_id=lista_id,
            usuario="admin",
        )

        itens = sistema.get_itens_lista(lista_id)
        assert len(itens) == 1
        assert itens[0]["produto"] == "ARROZ 5KG"
        assert itens[0]["valor_total"] == pytest.approx(51.80, abs=0.01)

    def test_produto_predefinido(self, sistema):
        """Testa cadastro e listagem de produtos predefinidos."""
        sistema.adicionar_produto_predefinido("Café")
        sistema.adicionar_produto_predefinido("Açúcar")

        produtos = sistema.get_produtos_predefinidos()
        assert "CAFÉ" in produtos
        assert "AÇÚCAR" in produtos


# =============================================================================
# TESTES DE VALIDAÇÃO DE CPF/CNPJ
# =============================================================================


class TestValidacao:
    """Testes de validação de documentos."""

    def test_cpf_valido(self, sistema):
        assert sistema._validar_cpf_cnpj("52998224725") is True

    def test_cpf_invalido_repetido(self, sistema):
        """CPF com todos dígitos iguais é inválido."""
        assert sistema._validar_cpf_cnpj("11111111111") is False
        assert sistema._validar_cpf_cnpj("00000000000") is False

    def test_cpf_invalido_digito_errado(self, sistema):
        assert sistema._validar_cpf_cnpj("52998224726") is False  # Último dígito errado

    def test_documento_curto_aceito_como_rg(self, sistema):
        """Documentos que não são CPF nem CNPJ são aceitos se > 3 chars."""
        assert sistema._validar_cpf_cnpj("MG1234567") is True  # RG de MG
        assert sistema._validar_cpf_cnpj("AB") is False  # Muito curto
