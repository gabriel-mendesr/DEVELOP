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
from datetime import datetime, timedelta

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

    def test_cnpj_valido(self, sistema):
        """CNPJ com dígitos verificadores corretos."""
        assert sistema._validar_cpf_cnpj("11222333000181") is True

    def test_cnpj_invalido_repetido(self, sistema):
        """CNPJ com todos dígitos iguais é inválido."""
        assert sistema._validar_cpf_cnpj("11111111111111") is False

    def test_cnpj_invalido_digito_errado(self, sistema):
        """CNPJ com dígito verificador corrompido é inválido."""
        assert sistema._validar_cpf_cnpj("11222333000189") is False  # último dígito errado


# =============================================================================
# TESTES FINANCEIRO EXPANDIDO
# =============================================================================


class TestFinanceiroExpandido:
    """Cobre caminhos do core não exercitados pelos testes base."""

    DOC = "52998224725"

    def _hospede(self, sistema):
        sistema.cadastrar_hospede("Teste Expandido", self.DOC)

    def test_saida_parcialmente_consome_entrada(self, sistema):
        """FIFO: saída menor que entrada não zera o crédito."""
        self._hospede(sistema)
        sistema.adicionar_movimentacao(self.DOC, 500, "Cortesia", "ENTRADA")
        sistema.adicionar_movimentacao(self.DOC, 300, "Uso", "SAIDA")
        saldo, _, _ = sistema.get_saldo_info(self.DOC)
        assert saldo == pytest.approx(200.0)

    def test_movimentacao_hospede_inexistente(self, sistema):
        """Adicionar movimentação para doc inexistente lança ValueError."""
        with pytest.raises(ValueError):
            sistema.adicionar_movimentacao("00000000000", 100, "Cat", "ENTRADA")

    def test_pagar_multa_valor_zero_bloqueia(self, sistema):
        """Pagar multa com valor zero ou negativo lança ValueError."""
        self._hospede(sistema)
        sistema.adicionar_multa(self.DOC, 50, "Atraso")
        with pytest.raises(ValueError):
            sistema.pagar_multa(self.DOC, 0, "Dinheiro")

    def test_historico_global_com_tipo_filtro(self, sistema):
        """get_historico_global filtra por tipo corretamente."""
        self._hospede(sistema)
        sistema.adicionar_movimentacao(self.DOC, 100, "Cat", "ENTRADA")
        sistema.adicionar_movimentacao(self.DOC, 50, "Uso", "SAIDA")

        entradas = sistema.get_historico_global(tipos=("ENTRADA",))
        saidas = sistema.get_historico_global(tipos=("SAIDA",))
        assert all(r["tipo"] == "ENTRADA" for r in entradas)
        assert all(r["tipo"] == "SAIDA" for r in saidas)

    def test_historico_global_com_datas(self, sistema):
        """get_historico_global filtra por data_inicio e data_fim."""
        self._hospede(sistema)
        sistema.adicionar_movimentacao(self.DOC, 100, "Cat", "ENTRADA")
        hoje = datetime.today().date().isoformat()
        resultado = sistema.get_historico_global(data_inicio=hoje, data_fim=hoje)
        assert len(resultado) >= 1

    def test_get_dados_grafico_categorias(self, sistema):
        """get_dados_grafico_categorias retorna dados após uma entrada."""
        self._hospede(sistema)
        sistema.adicionar_movimentacao(self.DOC, 200, "Cortesia", "ENTRADA")
        dados = sistema.get_dados_grafico_categorias()
        assert len(dados) >= 1
        assert dados[0][1] == pytest.approx(200.0)

    def test_get_dados_dash_hospede_vencido(self, sistema):
        """Dashboard contabiliza saldo vencido corretamente."""
        self._hospede(sistema)
        # Força validade 0 meses → crédito vence hoje (no passado no próximo segundo)
        sistema.set_config("validade_meses", 0)
        sistema.adicionar_movimentacao(self.DOC, 300, "Cortesia", "ENTRADA")
        total_saldo, total_vencido, _, n, _ = sistema.get_dados_dash()
        assert n >= 1
        assert total_saldo >= 300.0

    def test_get_hospedes_vencendo_em_breve(self, sistema):
        """Hóspede com crédito dentro do alerta aparece no resultado."""
        self._hospede(sistema)
        sistema.set_config("validade_meses", 1)  # vence em ~30 dias
        sistema.set_config("alerta_dias", 60)  # alerta de 60 dias
        sistema.adicionar_movimentacao(self.DOC, 100, "Cat", "ENTRADA")
        resultado = sistema.get_hospedes_vencendo_em_breve()
        assert len(resultado) >= 1
        assert resultado[0][0] == "TESTE EXPANDIDO"


# =============================================================================
# TESTES BUSCA FILTRADA EXPANDIDA
# =============================================================================


class TestBuscaFiltrada:
    """Cobre os filtros não exercitados nos testes base."""

    DOC = "11144477735"

    def _hospede(self, sistema):
        sistema.cadastrar_hospede("Filtro Teste", self.DOC)

    def test_buscar_filtro_vencidos(self, sistema):
        """buscar_filtrado('', 'vencidos') retorna hóspedes com crédito vencido."""
        self._hospede(sistema)
        # Insere diretamente com data de vencimento no passado
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        with sistema.conn:
            sistema.cursor.execute(
                "INSERT INTO historico_zebra (documento, tipo, valor, categoria, data_acao, data_vencimento, obs, usuario)"
                " VALUES (?, 'ENTRADA', 100, 'Cat', ?, ?, '', 'admin')",
                (self.DOC, ontem, ontem),
            )
        resultado = sistema.buscar_filtrado("", "vencidos")
        docs = [r[1] for r in resultado]
        assert self.DOC in docs

    def test_buscar_filtro_com_multa(self, sistema):
        """buscar_filtrado('', 'com_multa') retorna só quem tem multa."""
        self._hospede(sistema)
        sistema.adicionar_multa(self.DOC, 80, "Teste")
        resultado = sistema.buscar_filtrado("", "com_multa")
        docs = [r[1] for r in resultado]
        assert self.DOC in docs

    def test_buscar_filtro_vencendo(self, sistema):
        """buscar_filtrado('', 'vencendo') retorna hóspedes dentro do alerta."""
        self._hospede(sistema)
        sistema.set_config("validade_meses", 1)  # vence em ~30 dias
        sistema.set_config("alerta_dias", 60)
        sistema.adicionar_movimentacao(self.DOC, 150, "Cat", "ENTRADA")
        resultado = sistema.buscar_filtrado("", "vencendo")
        docs = [r[1] for r in resultado]
        assert self.DOC in docs


# =============================================================================
# TESTES COMPRAS EXPANDIDO
# =============================================================================


class TestComprasExpandido:
    """Cobre caminhos de compras não exercitados."""

    def test_compra_data_invalida_usa_hoje(self, sistema):
        """Data inválida faz fallback para hoje sem lançar exceção."""
        lista_id = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra(
            data_compra="nao-e-uma-data",
            produto="Produto X",
            qtd="1",
            valor_unit="10,00",
            lista_id=lista_id,
            usuario="admin",
        )
        itens = sistema.get_itens_lista(lista_id)
        assert len(itens) == 1

    def test_fechar_lista(self, sistema):
        """Fechar lista altera status para FECHADA."""
        lista_id = sistema.criar_lista_compras("admin")
        sistema.fechar_lista_compras(lista_id)
        listas = sistema.get_listas_resumo()
        lista = next(item for item in listas if item["id"] == lista_id)
        assert lista["status"] == "FECHADA"

    def test_itens_lista_tendencia_subiu(self, sistema):
        """Tendência 'subiu' quando preço atual > preço anterior."""
        lista1 = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra("01/01/2025", "CAFÉ", "1", "5,00", lista_id=lista1)
        lista2 = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra("01/03/2025", "CAFÉ", "1", "8,00", lista_id=lista2)
        itens = sistema.get_itens_lista(lista2)
        cafe = next(i for i in itens if i["produto"] == "CAFÉ")
        assert cafe["tendencia"] == "subiu"

    def test_itens_lista_tendencia_desceu(self, sistema):
        """Tendência 'desceu' quando preço atual < preço anterior."""
        lista1 = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra("01/01/2025", "ARROZ", "1", "10,00", lista_id=lista1)
        lista2 = sistema.criar_lista_compras("admin")
        sistema.adicionar_compra("01/03/2025", "ARROZ", "1", "7,00", lista_id=lista2)
        itens = sistema.get_itens_lista(lista2)
        arroz = next(i for i in itens if i["produto"] == "ARROZ")
        assert arroz["tendencia"] == "desceu"


# =============================================================================
# TESTES DE EXPORTAÇÃO
# =============================================================================


class TestExportacao:
    """Cobre métodos de exportação CSV."""

    def test_exportar_csv_gera_arquivo(self, sistema):
        """exportar_csv() cria um arquivo não-vazio."""
        import os

        caminho = sistema.exportar_csv()
        assert os.path.exists(caminho)
        assert os.path.getsize(caminho) > 0
        os.unlink(caminho)

    def test_exportar_historico_sem_mes(self, sistema):
        """exportar_historico_financeiro_csv(None) cria arquivo sem filtro de mês."""
        import os

        caminho = sistema.exportar_historico_financeiro_csv(None)
        assert os.path.exists(caminho)
        os.unlink(caminho)

    def test_exportar_historico_com_mes(self, sistema):
        """exportar_historico_financeiro_csv('03/2026') cria arquivo filtrado."""
        import os

        caminho = sistema.exportar_historico_financeiro_csv("03/2026")
        assert os.path.exists(caminho)
        os.unlink(caminho)


# =============================================================================
# TESTES DE LOG E ANOTAÇÕES
# =============================================================================


class TestLogEAnotacoes:
    """Cobre registrar_log, get_logs, limpar_logs e anotações."""

    def test_registrar_e_ler_log(self, sistema):
        """registrar_log adiciona entrada visível em get_logs."""
        sistema.registrar_log("admin", "TESTE_LOG", "detalhe qualquer")
        logs = sistema.get_logs()
        assert any(log["acao"] == "TESTE_LOG" for log in logs)

    def test_limpar_logs(self, sistema):
        """limpar_logs_auditoria apaga os logs anteriores."""
        sistema.registrar_log("admin", "LOG_ANTES", "x")
        sistema.limpar_logs_auditoria("admin")
        logs = sistema.get_logs()
        # Após limpar, só deve existir o log da própria limpeza
        assert all(log["acao"] == "LIMPEZA_LOGS" for log in logs)

    def test_salvar_e_ler_anotacao(self, sistema):
        """salvar_anotacao persiste e get_anotacao recupera o texto."""
        sistema.cadastrar_hospede("Anot Teste", "52998224725")
        sistema.salvar_anotacao("52998224725", "Nota de teste aqui")
        texto = sistema.get_anotacao("52998224725")
        assert texto == "Nota de teste aqui"


# =============================================================================
# TESTES DE AUTENTICAÇÃO LEGADA
# =============================================================================


class TestAuthLegacy:
    """Cobre migração automática de usuário sem salt (formato legado)."""

    def test_login_legado_sem_salt(self, sistema):
        """
        Usuário com hash SHA-256 puro (sem salt) é autenticado e
        automaticamente migrado para o novo formato com salt.
        """
        import hashlib

        legacy_hash = hashlib.sha256(b"minhasenha").hexdigest()
        with sistema.conn:
            sistema.cursor.execute(
                "INSERT INTO usuarios (username, password, salt, is_admin, can_change_dates, can_manage_products)"
                " VALUES (?, ?, NULL, 0, 0, 0)",
                ("usuario_legado", legacy_hash),
            )

        # Primeiro login: autentica e migra
        user = sistema.verificar_login("usuario_legado", "minhasenha")
        assert user is not None
        assert user["username"] == "usuario_legado"

        # Segundo login: agora usa o novo formato com salt
        user2 = sistema.verificar_login("usuario_legado", "minhasenha")
        assert user2 is not None
