"""
╔══════════════════════════════════════════════════════════════════╗
║        SCRIPT DE DIAGNÓSTICO — Sistema Hotel Santos             ║
╠══════════════════════════════════════════════════════════════════╣
║  COMO RODAR (de dentro da pasta app/):                           ║
║    python verificar_sistema.py                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import ast
import os
import shutil
import sys
import tempfile
import traceback

# Garante que o script encontra o pacote 'core' de onde quer que seja rodado
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Funciona tanto rodando de app/ quanto de tests/ (CI)
_app_candidato = os.path.join(SCRIPT_DIR, "..", "app")
if os.path.isdir(_app_candidato) and os.path.isdir(os.path.join(_app_candidato, "core")):
    SCRIPT_DIR = os.path.normpath(_app_candidato)
elif not os.path.isdir(os.path.join(SCRIPT_DIR, "core")):
    # Tenta subir mais um nível
    _app_candidato2 = os.path.join(SCRIPT_DIR, "..", "..", "app")
    if os.path.isdir(os.path.join(_app_candidato2, "core")):
        SCRIPT_DIR = os.path.normpath(_app_candidato2)
sys.path.insert(0, SCRIPT_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# MINI-FRAMEWORK DE TESTES
# ─────────────────────────────────────────────────────────────────────────────

_passou = 0
_falhou = 0
_erros = []
_secao = ""


def secao(titulo):
    global _secao
    _secao = titulo
    print(f"\n{'─'*62}")
    print(f"  {titulo}")
    print(f"{'─'*62}")


def checar(nome, func):
    """Executa func() e registra ✅ ou ❌."""
    global _passou, _falhou
    try:
        func()
        _passou += 1
        print(f"  ✅  {nome}")
    except AssertionError as e:
        _falhou += 1
        _erros.append((_secao, nome, str(e) or "AssertionError sem mensagem"))
        print(f"  ❌  {nome}")
        print(f"       → {str(e)[:120]}")
    except Exception:
        _falhou += 1
        tb = traceback.format_exc()
        _erros.append((_secao, nome, tb))
        primeira_linha = tb.strip().split("\n")[-1][:120]
        print(f"  ❌  {nome}")
        print(f"       → {primeira_linha}")


def novo_sistema():
    """Retorna um SistemaCreditos com banco limpo na memória."""
    from core.database import Database  # noqa: E402
    from core.models import SistemaCreditos  # noqa: E402

    return SistemaCreditos(Database(":memory:"))


# ─────────────────────────────────────────────────────────────────────────────
# 1. ESTRUTURA DE ARQUIVOS
# ─────────────────────────────────────────────────────────────────────────────
secao("1. ESTRUTURA DE ARQUIVOS")

for nome_rel, nome_abs in [
    ("__version__.py", os.path.join(SCRIPT_DIR, "__version__.py")),
    ("core/__init__.py", os.path.join(SCRIPT_DIR, "core", "__init__.py")),
    ("core/database.py", os.path.join(SCRIPT_DIR, "core", "database.py")),
    ("core/models.py", os.path.join(SCRIPT_DIR, "core", "models.py")),
    ("update_manager.py", os.path.join(SCRIPT_DIR, "update_manager.py")),
    ("logger_system.py", os.path.join(SCRIPT_DIR, "logger_system.py")),
]:
    # Cria uma função separada para capturar o valor correto no loop
    def _checar_arquivo(caminho=nome_abs, exib=nome_rel):
        def _inner():
            assert os.path.isfile(caminho), f"Não encontrado: {caminho}"

        checar(f"Existe: {exib}", _inner)

    _checar_arquivo()


def _checar_app_gui():
    p1 = os.path.join(SCRIPT_DIR, "app_gui.py")
    p2 = os.path.join(os.path.dirname(SCRIPT_DIR), "app_gui.py")
    assert os.path.isfile(p1) or os.path.isfile(p2), "app_gui.py não encontrado nem em app/ nem na pasta pai"


checar("app_gui.py", _checar_app_gui)


# ─────────────────────────────────────────────────────────────────────────────
# 2. IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
secao("2. IMPORTS")


def _imp_database():
    from core.database import MIGRATIONS, Database  # noqa: E402

    assert Database and MIGRATIONS


checar("from core.database import Database, MIGRATIONS", _imp_database)  # noqa: E402


def _imp_models():
    from core.models import SistemaCreditos  # noqa: E402

    assert SistemaCreditos


checar("from core.models import SistemaCreditos", _imp_models)  # noqa: E402


def _imp_version():
    from __version__ import __version__ as VERSION  # noqa: E402

    assert VERSION


checar("from __version__ import VERSION", _imp_version)  # noqa: E402


def _imp_update():
    import update_manager

    assert update_manager


checar("import update_manager", _imp_update)


def _imp_logger():
    import logger_system

    assert logger_system


checar("import logger_system", _imp_logger)


# ─────────────────────────────────────────────────────────────────────────────
# 3. BANCO DE DADOS
# ─────────────────────────────────────────────────────────────────────────────
secao("3. BANCO DE DADOS")

from core.database import MIGRATIONS, Database  # noqa: E402


def _banco_cria():
    Database(":memory:")


checar("Database(':memory:') inicializa sem erros", _banco_cria)


def _versao_banco():
    db = Database(":memory:")
    v = db._get_versao_banco()
    assert v == len(MIGRATIONS), f"Banco na versão {v}, mas existem {len(MIGRATIONS)} migrations"


checar("Versão do banco == número de migrations", _versao_banco)


def _todas_tabelas():
    db = Database(":memory:")
    db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existentes = {r["name"] for r in db.cursor.fetchall()}
    esperadas = [
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
    faltando = [t for t in esperadas if t not in existentes]
    assert not faltando, f"Tabelas faltando: {faltando}"


checar("Todas as 12 tabelas essenciais existem", _todas_tabelas)


def _configs_padrao():
    s = novo_sistema()
    assert s.get_config("validade_meses") == 6, "validade_meses deveria ser 6"
    assert s.get_config("alerta_dias") == 30, "alerta_dias deveria ser 30"
    assert s.get_config("tema") == 0, "tema deveria ser 0"


checar("Configs padrão: validade=6, alerta=30, tema=0", _configs_padrao)


def _admin_padrao():
    s = novo_sistema()
    u = s.verificar_login("gabriel", "132032")
    assert u is not None, "Login gabriel/132032 falhou"
    assert u["is_admin"] == 1, "gabriel deveria ser admin"


checar("Usuário admin 'gabriel' criado automaticamente", _admin_padrao)


# ─────────────────────────────────────────────────────────────────────────────
# 4. HÓSPEDES
# ─────────────────────────────────────────────────────────────────────────────
secao("4. HÓSPEDES")

CPF_VALIDO = "52998224725"
CPF_VALIDO2 = "11144477735"


def _cadastro_cpf_valido():
    s = novo_sistema()
    s.cadastrar_hospede("João Silva", CPF_VALIDO)
    h = s.get_hospede(CPF_VALIDO)
    assert h is not None, "Hóspede não encontrado após cadastro"
    assert h["nome"] == "JOÃO SILVA", f"Nome: {h['nome']}"


checar("Cadastro com CPF válido", _cadastro_cpf_valido)


def _cpf_repetido():
    s = novo_sistema()
    try:
        s.cadastrar_hospede("Teste", "11111111111")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("CPF com dígitos repetidos (11111111111) lança ValueError", _cpf_repetido)


def _cpf_digito_errado():
    s = novo_sistema()
    try:
        s.cadastrar_hospede("Teste", "52998224726")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("CPF com dígito verificador errado lança ValueError", _cpf_digito_errado)


def _cnpj_valido():
    s = novo_sistema()
    s.cadastrar_hospede("Empresa XYZ", "11222333000181")
    assert s.get_hospede("11222333000181") is not None


checar("CNPJ válido aceito", _cnpj_valido)


def _rg_aceito():
    s = novo_sistema()
    s.cadastrar_hospede("Ana", "MG1234567")
    assert s.get_hospede("MG1234567") is not None


checar("RG (> 3 chars) aceito como documento livre", _rg_aceito)


def _doc_curto_rejeitado():
    s = novo_sistema()
    try:
        s.cadastrar_hospede("Ana", "AB")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("Documento com 2 chars lança ValueError", _doc_curto_rejeitado)


def _atualiza_nao_duplica():
    s = novo_sistema()
    s.cadastrar_hospede("Nome Antigo", CPF_VALIDO, "11900000000")
    s.cadastrar_hospede("Nome Novo", CPF_VALIDO, "11988888888")
    h = s.get_hospede(CPF_VALIDO)
    assert h["nome"] == "NOME NOVO", f"Nome: {h['nome']}"
    assert h["telefone"] == "11988888888", f"Tel: {h['telefone']}"
    s.cursor.execute("SELECT COUNT(*) as c FROM hospedes WHERE documento=?", (CPF_VALIDO,))
    assert s.cursor.fetchone()["c"] == 1, "Cadastro duplicado!"


checar("Cadastrar doc existente ATUALIZA (não duplica)", _atualiza_nao_duplica)


def _busca_parcial():
    s = novo_sistema()
    s.cadastrar_hospede("Ana Paula", CPF_VALIDO)
    s.cadastrar_hospede("Pedro Costa", CPF_VALIDO2)
    r = s.buscar_filtrado("Ana")
    assert len(r) == 1, f"Esperava 1, veio {len(r)}"
    assert r[0][0] == "ANA PAULA"


checar("Busca parcial por nome retorna só o correto", _busca_parcial)


def _busca_vazia_todos():
    s = novo_sistema()
    s.cadastrar_hospede("Ana", CPF_VALIDO)
    s.cadastrar_hospede("Pedro", CPF_VALIDO2)
    assert len(s.buscar_filtrado("")) == 2


checar("Busca vazia retorna todos os hóspedes", _busca_vazia_todos)


def _filtro_vencidos():
    s = novo_sistema()
    s.cadastrar_hospede("Vencido", CPF_VALIDO)
    s.cursor.execute(
        "INSERT INTO historico_zebra "
        "(documento, tipo, valor, categoria, data_acao, data_vencimento, usuario) "
        "VALUES (?, 'ENTRADA', 100, 'Test', '2020-01-01', '2020-06-01', 'admin')",
        (CPF_VALIDO,),
    )
    s.conn.commit()
    r = s.buscar_filtrado("", "vencidos")
    assert len(r) == 1, f"Esperava 1 vencido, veio {len(r)}"


checar("Filtro 'vencidos' retorna apenas bloqueados", _filtro_vencidos)


# ─────────────────────────────────────────────────────────────────────────────
# 5. FINANCEIRO
# ─────────────────────────────────────────────────────────────────────────────
secao("5. FINANCEIRO")


def _sistema_com_hospede():
    s = novo_sistema()
    s.cadastrar_hospede("Teste Financeiro", CPF_VALIDO)
    return s


def _saldo_inicial_zero():
    s = _sistema_com_hospede()
    saldo, venc, bloq = s.get_saldo_info(CPF_VALIDO)
    assert saldo == 0.0, f"Saldo: {saldo}"
    assert venc == "N/A", f"Vencimento: {venc}"
    assert bloq is False, f"Bloqueado: {bloq}"


checar("Saldo inicial = 0,00, vencimento = N/A, não bloqueado", _saldo_inicial_zero)


def _entrada_aumenta():
    s = _sistema_com_hospede()
    s.adicionar_movimentacao(CPF_VALIDO, "500,00", "Cortesia", "ENTRADA")
    saldo, _, _ = s.get_saldo_info(CPF_VALIDO)
    assert saldo == 500.0, f"Saldo: {saldo}"


checar("ENTRADA de R$500 → saldo fica 500,00", _entrada_aumenta)


def _saida_diminui():
    s = _sistema_com_hospede()
    s.adicionar_movimentacao(CPF_VALIDO, 500, "Cortesia", "ENTRADA")
    s.adicionar_movimentacao(CPF_VALIDO, 200, "Uso", "SAIDA")
    saldo, _, _ = s.get_saldo_info(CPF_VALIDO)
    assert saldo == 300.0, f"Saldo: {saldo}"


checar("ENTRADA 500 - SAÍDA 200 → saldo fica 300,00", _saida_diminui)


def _saida_sem_saldo():
    s = _sistema_com_hospede()
    s.adicionar_movimentacao(CPF_VALIDO, 100, "Cortesia", "ENTRADA")
    try:
        s.adicionar_movimentacao(CPF_VALIDO, 200, "Uso", "SAIDA")
        assert False, "Deveria lançar ValueError"
    except ValueError as e:
        assert "insuficiente" in str(e).lower(), f"Mensagem esperada 'insuficiente', veio: {e}"


checar("SAÍDA maior que saldo → ValueError('Saldo insuficiente')", _saida_sem_saldo)


def _saida_vencido():
    s = _sistema_com_hospede()
    s.cursor.execute(
        "INSERT INTO historico_zebra "
        "(documento, tipo, valor, categoria, data_acao, data_vencimento, usuario) "
        "VALUES (?, 'ENTRADA', 100, 'Test', '2020-01-01', '2020-06-01', 'admin')",
        (CPF_VALIDO,),
    )
    s.conn.commit()
    try:
        s.adicionar_movimentacao(CPF_VALIDO, 10, "Uso", "SAIDA")
        assert False, "Deveria lançar ValueError (bloqueio)"
    except ValueError as e:
        msg = str(e).lower()
        assert "bloqueio" in msg or "vencido" in msg, f"Mensagem esperada mencionar bloqueio/vencido, veio: {e}"


checar("SAÍDA com crédito vencido → ValueError com 'BLOQUEIO'", _saida_vencido)


def _limpar_valor_formatos():
    s = novo_sistema()
    casos = [
        ("1.500,50", 1500.50),
        ("100,00", 100.0),
        (42.5, 42.5),
        ("", 0.0),
        (None, 0.0),
        (0, 0.0),
    ]
    for entrada, esperado in casos:
        resultado = s.limpar_valor(entrada)
        assert resultado == esperado, f"limpar_valor({entrada!r}) = {resultado}, esperava {esperado}"


checar("limpar_valor: formatos BR, float, vazio, None, zero", _limpar_valor_formatos)


def _multa_e_pagamento():
    s = _sistema_com_hospede()
    s.adicionar_multa(CPF_VALIDO, 100, "Atraso")
    assert s.get_divida_multas(CPF_VALIDO) == 100.0
    s.pagar_multa(CPF_VALIDO, 60, "Dinheiro")
    assert s.get_divida_multas(CPF_VALIDO) == 40.0


checar("Multa 100 + pagamento 60 → dívida fica 40,00", _multa_e_pagamento)


def _pagamento_acima_divida():
    s = _sistema_com_hospede()
    s.adicionar_multa(CPF_VALIDO, 50, "Atraso")
    try:
        s.pagar_multa(CPF_VALIDO, 100, "Dinheiro")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("Pagamento maior que a dívida lança ValueError", _pagamento_acima_divida)


def _devedores_multas():
    s = novo_sistema()
    s.cadastrar_hospede("Devedor", CPF_VALIDO)
    s.cadastrar_hospede("Limpo", CPF_VALIDO2)
    s.adicionar_multa(CPF_VALIDO, 80, "Dano")
    d = s.get_devedores_multas()
    assert len(d) == 1, f"Esperava 1 devedor, veio {len(d)}"
    assert d[0][1] == CPF_VALIDO


checar("get_devedores_multas retorna só quem tem dívida", _devedores_multas)


def _excluir_movimentacao():
    s = _sistema_com_hospede()
    s.adicionar_movimentacao(CPF_VALIDO, 200, "Cortesia", "ENTRADA")
    hist = s.get_historico_detalhado(CPF_VALIDO)
    assert len(hist) == 1
    s.excluir_movimentacao(hist[0]["id"], "admin")
    assert len(s.get_historico_detalhado(CPF_VALIDO)) == 0


checar("Excluir movimentação remove do histórico", _excluir_movimentacao)


def _excluir_inexistente():
    s = novo_sistema()
    try:
        s.excluir_movimentacao(9999, "admin")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("Excluir ID inexistente lança ValueError", _excluir_inexistente)


def _atualizar_vencimento():
    s = _sistema_com_hospede()
    s.adicionar_movimentacao(CPF_VALIDO, 100, "Cortesia", "ENTRADA")
    hist = s.get_historico_detalhado(CPF_VALIDO)
    s.atualizar_data_vencimento_manual(hist[0]["id"], "31/12/2030", "admin")
    s.cursor.execute("SELECT data_vencimento FROM historico_zebra WHERE id = ?", (hist[0]["id"],))
    assert s.cursor.fetchone()["data_vencimento"] == "2030-12-31"


checar("Atualizar data de vencimento manual persiste corretamente", _atualizar_vencimento)


def _historico_filtro_tipo():
    s = novo_sistema()
    s.cadastrar_hospede("Teste", CPF_VALIDO)
    s.adicionar_movimentacao(CPF_VALIDO, 100, "Cortesia", "ENTRADA")
    s.adicionar_multa(CPF_VALIDO, 50, "Dano")
    entradas = s.get_historico_global(tipos=("ENTRADA",))
    multas = s.get_historico_global(tipos=("MULTA",))
    assert all(r["tipo"] == "ENTRADA" for r in entradas), "Filtro ENTRADA trouxe outro tipo"
    assert all(r["tipo"] == "MULTA" for r in multas), "Filtro MULTA trouxe outro tipo"


checar("get_historico_global filtra corretamente por tipo", _historico_filtro_tipo)


def _anotacoes():
    s = _sistema_com_hospede()
    s.salvar_anotacao(CPF_VALIDO, "Hóspede VIP — quarto 201")
    assert s.get_anotacao(CPF_VALIDO) == "Hóspede VIP — quarto 201"


checar("Salvar e recuperar anotação do hóspede", _anotacoes)


# ─────────────────────────────────────────────────────────────────────────────
# 6. COMPRAS
# ─────────────────────────────────────────────────────────────────────────────
secao("6. COMPRAS")


def _criar_lista():
    s = novo_sistema()
    lid = s.criar_lista_compras("admin", "Lista de teste")
    assert lid > 0, f"ID inválido: {lid}"


checar("criar_lista_compras retorna ID > 0", _criar_lista)


def _lista_no_resumo():
    s = novo_sistema()
    s.criar_lista_compras("admin")
    assert len(s.get_listas_resumo()) == 1


checar("Lista criada aparece em get_listas_resumo", _lista_no_resumo)


def _adicionar_item():
    s = novo_sistema()
    lid = s.criar_lista_compras("admin")
    s.adicionar_compra("22/03/2026", "Arroz 5kg", "2", "25,90", lista_id=lid)
    itens = s.get_itens_lista(lid)
    assert len(itens) == 1
    assert itens[0]["produto"] == "ARROZ 5KG", f"Produto: {itens[0]['produto']}"
    assert abs(itens[0]["valor_total"] - 51.80) < 0.01, f"Total: {itens[0]['valor_total']}"


checar("Adicionar item: maiúsculo + total (2 × 25,90 = 51,80)", _adicionar_item)


def _fechar_lista():
    s = novo_sistema()
    lid = s.criar_lista_compras("admin")
    s.fechar_lista_compras(lid)
    assert s.get_listas_resumo()[0]["status"] == "FECHADA"


checar("fechar_lista_compras muda status para FECHADA", _fechar_lista)


def _produto_predefinido():
    s = novo_sistema()
    s.adicionar_produto_predefinido("Café")
    s.adicionar_produto_predefinido("Açúcar")
    prods = s.get_produtos_predefinidos()
    assert "CAFÉ" in prods, f"CAFÉ não encontrado em {prods}"
    assert "AÇÚCAR" in prods, f"AÇÚCAR não encontrado em {prods}"


checar("Adicionar e listar produtos predefinidos", _produto_predefinido)


def _produto_duplicado():
    s = novo_sistema()
    s.adicionar_produto_predefinido("Sal")
    s.adicionar_produto_predefinido("Sal")
    ocorr = [p for p in s.get_produtos_predefinidos() if p == "SAL"]
    assert len(ocorr) == 1, f"Duplicou SAL: {ocorr}"


checar("Produto duplicado é ignorado (INSERT OR IGNORE)", _produto_duplicado)


def _remover_produto():
    s = novo_sistema()
    s.adicionar_produto_predefinido("Farinha")
    s.remover_produto_predefinido("FARINHA")
    assert "FARINHA" not in s.get_produtos_predefinidos()


checar("Remover produto predefinido funciona", _remover_produto)


def _multiplos_itens():
    s = novo_sistema()
    lid = s.criar_lista_compras("admin")
    s.adicionar_compra("01/01/2026", "Produto A", "1", "10,00", lista_id=lid)
    s.adicionar_compra("01/01/2026", "Produto B", "3", "5,00", lista_id=lid)
    assert len(s.get_itens_lista(lid)) == 2


checar("Múltiplos itens na mesma lista", _multiplos_itens)


# ─────────────────────────────────────────────────────────────────────────────
# 7. AGENDA & FUNCIONÁRIOS
# ─────────────────────────────────────────────────────────────────────────────
secao("7. AGENDA & FUNCIONÁRIOS")


def _add_funcionario():
    s = novo_sistema()
    s.adicionar_funcionario("Maria Silva", "admin")
    funcs = s.get_funcionarios()
    assert len(funcs) == 1
    assert funcs[0]["nome"] == "MARIA SILVA"


checar("Adicionar funcionário e listar", _add_funcionario)


def _funcionario_nome_vazio():
    s = novo_sistema()
    try:
        s.adicionar_funcionario("", "admin")
        assert False, "Deveria lançar ValueError"
    except ValueError:
        pass


checar("Nome vazio lança ValueError", _funcionario_nome_vazio)


def _funcionario_duplicado():
    s = novo_sistema()
    s.adicionar_funcionario("João", "admin")
    s.adicionar_funcionario("João", "admin")
    assert len(s.get_funcionarios()) == 1


checar("Funcionário duplicado ignorado (INSERT OR IGNORE)", _funcionario_duplicado)


def _agendamento():
    s = novo_sistema()
    s.adicionar_funcionario("Carlos", "admin")
    fid = s.get_funcionarios()[0]["id"]
    s.salvar_agendamento("2026-03-22", fid, "Turno Manhã", "admin")
    tarefas = s.get_tarefas_dia("2026-03-22")
    assert len(tarefas) == 1
    assert "CARLOS" in tarefas[0]["nome"]


checar("Salvar e buscar agendamento do dia", _agendamento)


def _remover_agendamento():
    s = novo_sistema()
    s.adicionar_funcionario("Ana", "admin")
    fid = s.get_funcionarios()[0]["id"]
    s.salvar_agendamento("2026-03-22", fid, "Teste", "admin")
    aid = s.get_tarefas_dia("2026-03-22")[0]["id"]
    s.remover_agendamento_id(aid, "admin")
    assert len(s.get_tarefas_dia("2026-03-22")) == 0


checar("Remover agendamento por ID", _remover_agendamento)


def _agenda_mes():
    s = novo_sistema()
    s.adicionar_funcionario("Paulo", "admin")
    fid = s.get_funcionarios()[0]["id"]
    s.salvar_agendamento("2026-03-15", fid, "Plantão", "admin")
    agenda = s.get_agenda_mes(2026, 3)
    assert "2026-03-15" in agenda, f"Data não encontrada. Agenda: {agenda}"


checar("get_agenda_mes retorna mapa {data_iso: nomes}", _agenda_mes)


def _remover_func_cascateia():
    s = novo_sistema()
    s.adicionar_funcionario("Temp", "admin")
    fid = s.get_funcionarios()[0]["id"]
    s.salvar_agendamento("2026-04-01", fid, "Serviço", "admin")
    s.remover_funcionario(fid, "admin")
    assert len(s.get_funcionarios()) == 0, "Funcionário ainda existe"
    assert len(s.get_tarefas_dia("2026-04-01")) == 0, "Agendamento não foi removido"


checar("Remover funcionário cascateia para agendamentos", _remover_func_cascateia)


# ─────────────────────────────────────────────────────────────────────────────
# 8. AUTENTICAÇÃO & USUÁRIOS
# ─────────────────────────────────────────────────────────────────────────────
secao("8. AUTENTICAÇÃO & USUÁRIOS")


def _login_valido():
    s = novo_sistema()
    u = s.verificar_login("gabriel", "132032")
    assert u is not None, "Login retornou None"
    assert u["is_admin"] == 1, "gabriel deveria ser admin"


checar("Login gabriel/132032 retorna dict com is_admin=1", _login_valido)


def _login_senha_errada():
    s = novo_sistema()
    assert s.verificar_login("gabriel", "senhaerrada") is None


checar("Senha errada retorna None", _login_senha_errada)


def _login_inexistente():
    s = novo_sistema()
    assert s.verificar_login("fantasma", "123456") is None


checar("Usuário inexistente retorna None", _login_inexistente)


def _criar_e_logar():
    s = novo_sistema()
    s.salvar_usuario("joana", "senha123", False, True, False)
    u = s.verificar_login("joana", "senha123")
    assert u is not None, "Login falhou após criar usuário"
    assert u["is_admin"] == 0
    assert u["can_change_dates"] == 1


checar("Criar usuário e logar com as novas credenciais", _criar_e_logar)


def _atualizar_senha():
    s = novo_sistema()
    s.salvar_usuario("joana", "senha123", False, False, False)
    s.salvar_usuario("joana", "novaSenha", False, False, False)
    assert s.verificar_login("joana", "novaSenha") is not None, "Nova senha não funciona"
    assert s.verificar_login("joana", "senha123") is None, "Senha antiga ainda funciona"


checar("Atualizar senha invalida a senha antiga", _atualizar_senha)


def _excluir_usuario():
    s = novo_sistema()
    s.salvar_usuario("temporario", "abc123", False, False, False)
    s.excluir_usuario("temporario")
    assert s.verificar_login("temporario", "abc123") is None


checar("Excluir usuário impede login posterior", _excluir_usuario)


def _get_usuarios():
    s = novo_sistema()
    lista = s.get_usuarios()
    assert isinstance(lista, list)
    assert len(lista) >= 1, "Esperava ao menos o gabriel"


checar("get_usuarios retorna lista com ao menos o admin", _get_usuarios)


# ─────────────────────────────────────────────────────────────────────────────
# 9. CONFIGURAÇÕES & LOG
# ─────────────────────────────────────────────────────────────────────────────
secao("9. CONFIGURAÇÕES & LOG DE AUDITORIA")


def _config_inexistente():
    s = novo_sistema()
    assert s.get_config("chave_inexistente") == 30, "Chave inexistente deveria retornar 30 (padrão)"


checar("get_config de chave inexistente retorna 30 (padrão)", _config_inexistente)


def _set_get_config():
    s = novo_sistema()
    s.set_config("alerta_dias", 45)
    assert s.get_config("alerta_dias") == 45


checar("set_config persiste o valor, get_config recupera", _set_get_config)


def _categorias_padrao():
    s = novo_sistema()
    assert len(s.get_categorias()) > 0, "Nenhuma categoria padrão encontrada"


checar("Categorias padrão inseridas na inicialização", _categorias_padrao)


def _add_remove_categoria():
    s = novo_sistema()
    s.adicionar_categoria("MinhaCategoria")
    assert "MinhaCategoria" in s.get_categorias()
    s.remover_categoria("MinhaCategoria")
    assert "MinhaCategoria" not in s.get_categorias()


checar("Adicionar e remover categoria", _add_remove_categoria)


def _log_auditoria():
    s = novo_sistema()
    s.registrar_log("admin", "ACAO_TESTE", "Detalhe aqui")
    assert any(log["acao"] == "ACAO_TESTE" for log in s.get_logs()), "Log ACAO_TESTE não encontrado"


checar("registrar_log e get_logs funcionam", _log_auditoria)


def _limpar_logs():
    s = novo_sistema()
    s.registrar_log("admin", "ACAO1", "")
    s.registrar_log("admin", "ACAO2", "")
    s.limpar_logs_auditoria("admin")
    restantes = [log for log in s.get_logs() if log["acao"] != "LIMPEZA_LOGS"]
    assert len(restantes) == 0, f"Sobrou {len(restantes)} log(s) inesperado(s)"


checar("limpar_logs_auditoria apaga tudo (exceto o log da limpeza)", _limpar_logs)


# ─────────────────────────────────────────────────────────────────────────────
# 10. DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
secao("10. DASHBOARD")


def _dados_dash():
    s = novo_sistema()
    r = s.get_dados_dash()
    assert len(r) == 5, f"Esperava 5 valores, veio {len(r)}"
    assert all(isinstance(v, int | float) for v in r), f"Valores não numéricos: {r}"


checar("get_dados_dash retorna 5 valores numéricos", _dados_dash)


def _grafico_mensal():
    s = novo_sistema()
    meses, entradas, saidas = s.get_dados_grafico_mensal()
    assert len(meses) == 6, f"Esperava 6 meses, veio {len(meses)}"
    assert len(entradas) == 6
    assert len(saidas) == 6


checar("get_dados_grafico_mensal retorna 6 meses", _grafico_mensal)


def _grafico_categorias():
    s = novo_sistema()
    s.cadastrar_hospede("Teste", CPF_VALIDO)
    s.adicionar_movimentacao(CPF_VALIDO, 100, "Cortesia", "ENTRADA")
    r = s.get_dados_grafico_categorias()
    assert isinstance(r, list) and len(r) > 0, "Esperava lista não vazia após uma entrada"


checar("get_dados_grafico_categorias retorna dados após entrada", _grafico_categorias)


def _hospedes_vencendo():
    s = novo_sistema()
    r = s.get_hospedes_vencendo_em_breve()
    assert isinstance(r, list)


checar("get_hospedes_vencendo_em_breve retorna lista", _hospedes_vencendo)


# ─────────────────────────────────────────────────────────────────────────────
# 11. BACKUP & MANUTENÇÃO
# ─────────────────────────────────────────────────────────────────────────────
secao("11. BACKUP & MANUTENÇÃO")


def _fazer_backup():
    pasta = tempfile.mkdtemp(prefix="hotel_bkp_test_")
    try:
        db_path = os.path.join(pasta, "hotel.db")
        db = Database(db_path)
        db.base_dir = pasta  # redireciona backups para pasta temporária
        caminho = db.fazer_backup()
        assert os.path.isfile(caminho), f"Arquivo não criado: {caminho}"
        assert os.path.getsize(caminho) > 0, "Arquivo vazio"
        db.fechar()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


checar("Database.fazer_backup() cria arquivo .db não vazio", _fazer_backup)


def _otimizar():
    db = Database(":memory:")
    db.otimizar()  # não deve lançar exceção


checar("Database.otimizar() executa sem erro", _otimizar)


def _core_expoe_db():
    s = novo_sistema()
    assert hasattr(s, "db"), "SistemaCreditos não tem atributo 'db'"
    assert hasattr(s.db, "fazer_backup"), "Database não tem 'fazer_backup'"
    assert hasattr(s.db, "otimizar"), "Database não tem 'otimizar'"
    assert hasattr(s.db, "restaurar_backup"), "Database não tem 'restaurar_backup'"


checar("SistemaCreditos.db expõe fazer_backup, otimizar, restaurar_backup", _core_expoe_db)


# ─────────────────────────────────────────────────────────────────────────────
# 12. app_gui.py — ANÁLISE ESTÁTICA (sem abrir janela)
# ─────────────────────────────────────────────────────────────────────────────
secao("12. app_gui.py — ANÁLISE ESTÁTICA")


def _achar_app_gui():
    for p in [
        os.path.join(SCRIPT_DIR, "app_gui.py"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "app_gui.py"),
    ]:
        if os.path.isfile(p):
            return p
    return None


def _abrir_source():
    path = _achar_app_gui()
    assert path, "app_gui.py não encontrado (coloque-o na pasta app/)"
    with open(path, encoding="utf-8") as f:
        return f.read()


def _app_gui_sintaxe():
    source = _abrir_source()
    ast.parse(source, filename="app_gui.py")  # lança SyntaxError se inválido


checar("app_gui.py: sem SyntaxError", _app_gui_sintaxe)


def _app_gui_imports_novos():
    source = _abrir_source()
    tree = ast.parse(source)
    modulos = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "core.database" in modulos, f"'from core.database import ...' não encontrado. Módulos: {modulos}"  # noqa: E402
    assert "core.models" in modulos, f"'from core.models import ...' não encontrado. Módulos: {modulos}"  # noqa: E402


checar("app_gui.py: importa 'core.database' e 'core.models'", _app_gui_imports_novos)


def _app_gui_sem_import_antigo():
    source = _abrir_source()
    # Filtra linhas de comentário para evitar falsos positivos na documentação
    linhas_codigo = [linha for linha in source.splitlines() if not linha.strip().startswith("#")]
    codigo = "\n".join(linhas_codigo)
    assert (
        "from sistema_clientes import" not in codigo
    ), "Import antigo 'from sistema_clientes import' ainda presente no código!"


checar("app_gui.py: import de 'sistema_clientes' removido", _app_gui_sem_import_antigo)


def _app_gui_backup_correto():
    source = _abrir_source()
    # Filtra linhas de comentário para evitar falsos positivos na documentação
    linhas_codigo = [linha for linha in source.splitlines() if not linha.strip().startswith("#")]
    codigo = "\n".join(linhas_codigo)
    assert (
        "self.core.fazer_backup()" not in codigo
    ), "Encontrado self.core.fazer_backup() — deve ser self.core.db.fazer_backup()"
    assert "self.core.db.fazer_backup()" in codigo, "self.core.db.fazer_backup() não encontrado em on_closing"


checar("app_gui.py: on_closing usa self.core.db.fazer_backup()", _app_gui_backup_correto)


def _app_gui_def_tela_agenda():
    source = _abrir_source()
    assert "def tela_agenda(self)" in source, "'def tela_agenda(self)' não encontrado — cabeçalho pode estar faltando"


checar("app_gui.py: 'def tela_agenda(self)' existe", _app_gui_def_tela_agenda)


def _app_gui_cal_agenda():
    source = _abrir_source()
    assert "self.cal_agenda" in source, "self.cal_agenda não encontrado — agenda pode estar usando variável solta"


checar("app_gui.py: agenda usa self.cal_agenda", _app_gui_cal_agenda)


# ─────────────────────────────────────────────────────────────────────────────
# RESUMO FINAL
# ─────────────────────────────────────────────────────────────────────────────

total = _passou + _falhou
pct = (_passou / total * 100) if total > 0 else 0

print(f"\n{'═'*62}")
print("  RESULTADO FINAL")
print(f"{'═'*62}")
print(f"  ✅  Passou : {_passou}/{total}  ({pct:.0f}%)")
if _falhou:
    print(f"  ❌  Falhou : {_falhou}")

if _erros:
    print(f"\n{'─'*62}")
    print("  DETALHES DAS FALHAS:")
    print(f"{'─'*62}")
    for i, (sec, teste, motivo) in enumerate(_erros, 1):
        print(f"\n  [{i}]  Seção : {sec}")
        print(f"        Teste : {teste}")
        linhas = motivo.strip().split("\n")
        for linha in linhas[:12]:
            print(f"              {linha}")
        if len(linhas) > 12:
            print(f"              ... (+{len(linhas)-12} linhas omitidas)")

print(f"\n{'═'*62}")
if _falhou == 0:
    print("  🎉  Tudo certo! Sistema pronto para uso.")
else:
    print(f"  ⚠️   Corrija os {_falhou} erro(s) acima antes de usar em produção.")
print(f"{'═'*62}\n")

if __name__ == "__main__":
    sys.exit(0 if _falhou == 0 else 1)


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRAÇÃO COM PYTEST
# Quando pytest coleta este arquivo, executa um único teste que reporta
# todas as 88+ verificações como aprovadas ou falhas.
# ─────────────────────────────────────────────────────────────────────────────
def test_todas_as_verificacoes_passam():
    """Garante que todos os checar() acima não retornaram falha."""
    erros_fmt = "\n".join(f"[{sec}] {teste}: {motivo[:120]}" for sec, teste, motivo in _erros)
    assert _falhou == 0, f"{_falhou} verificação(ões) falharam:\n{erros_fmt}"
