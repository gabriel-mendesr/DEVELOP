"""
Regras de Negócio — Sistema Hotel Santos

O QUE ESTE ARQUIVO FAZ:
  - Cadastrar e buscar hóspedes
  - Calcular saldo e vencimento de créditos
  - Registrar movimentações (entradas, saídas, multas)
  - Gerenciar compras e listas de compras
  - Autenticação de usuários
  - Log de auditoria

O QUE ESTE ARQUIVO NÃO FAZ:
  - NÃO cria tabelas (isso é responsabilidade do database.py)
  - NÃO gera PDFs (isso é responsabilidade do exporters.py)
  - NÃO tem nada de interface gráfica

POR QUE SEPARAR?
  Antes, o sistema_clientes.py tinha 1116 linhas misturando banco,
  lógica e PDF. Agora cada arquivo tem UMA responsabilidade.
  Isso permite testar a lógica sem abrir a janela do app e
  sem precisar de um banco de dados real (usamos :memory: nos testes).

COMO USAR:
  from core.database import Database
  from core.models import SistemaCreditos

  db = Database(":memory:")  # ou Database() para o banco real
  sistema = SistemaCreditos(db)
  sistema.cadastrar_hospede("João Silva", "12345678900", usuario_acao="admin")
"""

import hashlib
import secrets
import socket
from datetime import datetime, timedelta
from typing import Any

# Importação relativa: o "." significa "desta mesma pasta (core/)"
from .database import Database


class SistemaCreditos:
    """
    Classe principal com todas as regras de negócio do hotel.

    Recebe um objeto Database no construtor — isso é chamado
    "Injeção de Dependência". A vantagem é que nos testes podemos
    passar um banco na memória, e em produção passamos o banco real.
    """

    def __init__(self, db: Database):
        """
        Args:
            db: Instância de Database (conexão já estabelecida)
        """
        self.db = db

        # Atalhos para não precisar escrever self.db.conn toda hora
        # (mantém compatibilidade com o código existente)
        self.conn = db.conn
        self.cursor = db.cursor

        # Informações da empresa (usadas nos PDFs e na interface)
        self.empresa = {
            "nome": "HOTEL SANTOS",
            "razao": "Hotel e Restaurante Santos Ana Lucia C. dos Santos",
            "cnpj": "03.288.530/0001-75",
            "endereco": "Praca Mota Sobrinho 10, Centro, ES Pinhal - SP",
            "contato": "Tel: (19) 3651-3297 / Whats: (19) 99759-7503",
            "email": "hotelsantoss@hotmail.com",
        }

        # Versão vem do arquivo local (sem depender de internet!)
        # O try/except garante que funciona tanto em desenvolvimento
        # quanto empacotado com PyInstaller
        try:
            from __version__ import __version__ as VERSION
        except ImportError:
            from app.__version__ import __version__ as VERSION
        self.versao_atual = VERSION

        # Popula dados iniciais (categorias, admin) se necessário
        db.popular_dados_iniciais(self._hash_password)

    # =========================================================================
    # AUTENTICAÇÃO & USUÁRIOS
    # =========================================================================

    def _hash_password(self, password: str, salt: str = "") -> str:
        """
        Cria um hash seguro da senha.

        O QUE É HASH?
        Um hash transforma "132032" em algo como "a8f5f167f44f4964e6c998dee827110c".
        É irreversível: não dá pra voltar do hash para a senha original.

        O QUE É SALT?
        É um texto aleatório adicionado à senha antes do hash.
        Isso garante que duas pessoas com a mesma senha tenham hashes diferentes.
        Exemplo: hash("132032" + "abc123") ≠ hash("132032" + "xyz789")
        """
        return hashlib.sha256((str(password) + str(salt)).encode()).hexdigest()

    def verificar_login(self, username: str, password: str) -> dict | None:
        """
        Verifica credenciais do usuário.

        Retorna:
            Dict com dados do usuário se login OK, None se inválido.
        """
        self.cursor.execute("SELECT password, salt FROM usuarios WHERE username = ?", (username,))
        user_data = self.cursor.fetchone()
        if not user_data:
            return None

        # Migração automática: se o usuário não tem salt (versão antiga),
        # valida com hash antigo e atualiza para o formato novo.
        if user_data["salt"] is None:
            legacy_hash = hashlib.sha256(str(password).encode()).hexdigest()
            if legacy_hash == user_data["password"]:
                # Login válido — atualiza para formato com salt
                new_salt = secrets.token_hex(16)
                new_hash = self._hash_password(password, new_salt)
                with self.conn:
                    self.cursor.execute(
                        "UPDATE usuarios SET password = ?, salt = ? WHERE username = ?", (new_hash, new_salt, username)
                    )
                self.cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
                return dict(self.cursor.fetchone())
            return None

        # Login normal com salt
        pass_hash = self._hash_password(password, user_data["salt"])
        if pass_hash == user_data["password"]:
            self.cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
            return dict(self.cursor.fetchone())

        return None

    def get_usuarios(self) -> list[dict]:
        self.cursor.execute("SELECT * FROM usuarios")
        return [dict(r) for r in self.cursor.fetchall()]

    def salvar_usuario(
        self,
        username: str,
        password: str,
        is_admin: bool,
        can_change_dates: bool,
        can_manage_products: bool,
        usuario_acao: str = "Sistema",
    ) -> None:
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        with self.conn:
            self.cursor.execute(
                "INSERT OR REPLACE INTO usuarios "
                "(username, password, is_admin, can_change_dates, can_manage_products, salt) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, password_hash, int(is_admin), int(can_change_dates), int(can_manage_products), salt),
            )
        self.registrar_log(usuario_acao, "SALVAR_USUARIO", f"Usuario alvo: {username} | Admin: {is_admin}")

    def excluir_usuario(self, username: str, usuario_acao: str = "Sistema") -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM usuarios WHERE username = ?", (username,))
        self.registrar_log(usuario_acao, "EXCLUIR_USUARIO", f"Usuario alvo: {username}")

    # =========================================================================
    # MÓDULO HÓSPEDES
    # =========================================================================

    def get_hospede(self, doc: str) -> dict | None:
        self.cursor.execute("SELECT * FROM hospedes WHERE documento = ?", (doc,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def cadastrar_hospede(
        self, nome: str, doc: str, telefone: str = "", email: str = "", usuario_acao: str = "Sistema"
    ) -> None:
        """Cadastra novo hóspede ou atualiza existente."""
        doc_limpo = str(doc).strip()

        if not self._validar_cpf_cnpj(doc_limpo):
            raise ValueError("Documento inválido (CPF/CNPJ incorreto). Verifique os dígitos.")

        with self.conn:
            self.cursor.execute("SELECT 1 FROM hospedes WHERE documento = ?", (doc_limpo,))
            if self.cursor.fetchone():
                # Atualiza
                self.cursor.execute(
                    "UPDATE hospedes SET nome = ?, telefone = ?, email = ? WHERE documento = ?",
                    (nome.upper().strip(), telefone, email, doc_limpo),
                )
                self.registrar_log(usuario_acao, "ATUALIZAR_HOSPEDE", f"Doc: {doc_limpo}")
            else:
                # Novo cadastro
                self.cursor.execute(
                    "INSERT INTO hospedes (nome, documento, telefone, email) VALUES (?, ?, ?, ?)",
                    (nome.upper().strip(), doc_limpo, telefone, email),
                )
                self.registrar_log(usuario_acao, "CADASTRAR_HOSPEDE", f"Doc: {doc_limpo}")

    def buscar_filtrado(self, termo: str = "", filtro: str = "todos") -> list[tuple[str, str, float]]:
        """
        Busca hóspedes com filtro por nome/documento e status de saldo.

        Args:
            termo: Texto para buscar no nome ou documento
            filtro: "todos", "vencidos", ou outro (com saldo > 0)
        """
        termo_limpo = str(termo).strip()
        self.cursor.execute(
            "SELECT nome, documento FROM hospedes WHERE nome LIKE ? OR documento LIKE ?",
            (f"%{termo_limpo}%", f"%{termo_limpo}%"),
        )
        hospedes = self.cursor.fetchall()

        resultado = []
        for h in hospedes:
            saldo, venc, bloqueado = self._processar_saldo(h["documento"])
            if filtro == "vencidos" and not bloqueado:
                continue
            if saldo <= 0 and filtro != "todos":
                continue
            resultado.append((h["nome"], h["documento"], saldo))

        return resultado

    # =========================================================================
    # MÓDULO FINANCEIRO
    # =========================================================================

    def limpar_valor(self, valor: Any) -> float:
        """
        Converte qualquer formato de valor para float.

        Aceita: "1.500,50" (BR), "1500.50" (US), 1500.50 (já float)
        Retorna: 1500.50

        EXPLICAÇÃO DO TRUQUE:
        - Remove PONTOS (separador de milhar no BR): "1.500" → "1500"
        - Troca VÍRGULA por PONTO (decimal BR → US): "1500,50" → "1500.50"
        - Converte para float: "1500.50" → 1500.50
        """
        if isinstance(valor, int | float):
            return float(valor)
        if not valor or str(valor).strip() == "":
            return 0.0
        return float(str(valor).replace(".", "").replace(",", ".").strip())

    def _processar_saldo(self, doc: str) -> tuple[float, str, bool]:
        """
        Calcula saldo, próximo vencimento e status de bloqueio de um hóspede.

        LÓGICA (FIFO — First In, First Out):
        Os créditos mais antigos são consumidos primeiro.
        Se um crédito venceu e ainda tem saldo, o hóspede fica BLOQUEADO.

        Retorna:
            (saldo, data_vencimento_formatada, esta_bloqueado)
            Ex: (150.00, "25/12/2025", False)
        """
        self.cursor.execute(
            "SELECT tipo, valor, data_vencimento FROM historico_zebra " "WHERE documento = ? ORDER BY id ASC", (doc,)
        )
        movs = self.cursor.fetchall()

        entradas = [{"valor": m["valor"], "venc": m["data_vencimento"]} for m in movs if m["tipo"] == "ENTRADA"]
        saidas_total = sum(m["valor"] for m in movs if m["tipo"] == "SAIDA")

        hoje = datetime.now().strftime("%Y-%m-%d")
        saldo, prox_venc, bloqueado = 0.0, "N/A", False

        for e in entradas:
            if saidas_total >= e["valor"]:
                saidas_total -= e["valor"]
                e["valor"] = 0
            else:
                e["valor"] -= saidas_total
                saidas_total = 0

            if e["valor"] > 0:
                saldo += e["valor"]
                if prox_venc == "N/A":
                    prox_venc = e["venc"]
                    if prox_venc and prox_venc < hoje:
                        bloqueado = True

        if prox_venc != "N/A" and prox_venc:
            prox_venc = datetime.strptime(prox_venc, "%Y-%m-%d").strftime("%d/%m/%Y")

        return round(max(0, saldo), 2), prox_venc, bloqueado

    def get_saldo_info(self, doc: str) -> tuple[float, str, bool]:
        """Atalho público para _processar_saldo."""
        return self._processar_saldo(doc)

    def adicionar_movimentacao(
        self, doc: str, valor: Any, categoria: str, tipo: str, obs: str = "", usuario: str = "Sistema"
    ) -> None:
        """
        Registra uma entrada ou saída de crédito.

        Args:
            tipo: "ENTRADA" (compra de crédito) ou "SAIDA" (uso de crédito)
        """
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()

        # Verifica se o hóspede existe
        self.cursor.execute("SELECT 1 FROM hospedes WHERE documento = ?", (doc_limpo,))
        if not self.cursor.fetchone():
            raise ValueError(f"Hóspede com documento {doc_limpo} não encontrado.")

        # Validações para SAÍDA
        if tipo == "SAIDA":
            saldo, venc, bloqueado = self._processar_saldo(doc_limpo)
            if bloqueado:
                raise ValueError(f"BLOQUEIO: Crédito vencido em {venc}!")
            if v_float > saldo:
                raise ValueError("Saldo insuficiente!")

        with self.conn:
            venc = ""
            data_hj = datetime.now()
            if tipo == "ENTRADA":
                meses = self.get_config("validade_meses")
                venc = (data_hj + timedelta(days=meses * 30)).strftime("%Y-%m-%d")

            self.cursor.execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, data_vencimento, obs, usuario) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (doc_limpo, tipo, v_float, categoria, data_hj.strftime("%Y-%m-%d"), venc, obs, usuario),
            )

        self.registrar_log(usuario, f"ADD_MOV_{tipo}", f"Doc: {doc_limpo}, Valor: {v_float}")

    def adicionar_multa(self, doc: str, valor: Any, motivo: str, obs: str = "", usuario: str = "Sistema") -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()
        with self.conn:
            data_hj = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, obs, usuario) "
                "VALUES (?,?,?,?,?,?,?)",
                (doc_limpo, "MULTA", v_float, motivo, data_hj, obs, usuario),
            )
        self.registrar_log(usuario, "ADD_MULTA", f"Doc: {doc_limpo}, Valor: {v_float}, Motivo: {motivo}")

    def pagar_multa(self, doc: str, valor: Any, forma_pagamento: str, obs: str = "", usuario: str = "Sistema") -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()

        divida = self.get_divida_multas(doc_limpo)
        if v_float <= 0:
            raise ValueError("Valor deve ser maior que zero.")
        if v_float > divida:
            raise ValueError(f"Valor (R$ {v_float:.2f}) excede a dívida atual (R$ {divida:.2f})")

        with self.conn:
            data_hj = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, obs, usuario) "
                "VALUES (?,?,?,?,?,?,?)",
                (doc_limpo, "PAGAMENTO_MULTA", v_float, forma_pagamento, data_hj, obs, usuario),
            )
        self.registrar_log(usuario, "PAGAR_MULTA", f"Doc: {doc_limpo}, Valor: {v_float}")

    def get_divida_multas(self, doc: str) -> float:
        """Calcula total de multas pendentes (multas - pagamentos)."""
        self.cursor.execute("SELECT SUM(valor) FROM historico_zebra " "WHERE documento = ? AND tipo = 'MULTA'", (doc,))
        total_multas = self.cursor.fetchone()[0] or 0.0

        self.cursor.execute(
            "SELECT SUM(valor) FROM historico_zebra " "WHERE documento = ? AND tipo = 'PAGAMENTO_MULTA'", (doc,)
        )
        total_pagamentos = self.cursor.fetchone()[0] or 0.0

        return total_multas - total_pagamentos

    def get_devedores_multas(self) -> list[tuple[str, str, str | None, float]]:
        """Retorna hóspedes com dívida de multas > 0."""
        self.cursor.execute("SELECT nome, documento, telefone FROM hospedes")
        todos = self.cursor.fetchall()
        devedores = []
        for h in todos:
            divida = self.get_divida_multas(h["documento"])
            if divida > 0:
                devedores.append((h["nome"], h["documento"], h["telefone"], divida))
        return sorted(devedores, key=lambda x: x[3], reverse=True)

    def get_historico_detalhado(self, doc: str) -> list[dict[str, Any]]:
        self.cursor.execute(
            "SELECT id, tipo, valor, data_acao, categoria, obs, usuario "
            "FROM historico_zebra WHERE documento = ? ORDER BY id DESC",
            (doc,),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def get_historico_global(
        self, filtro: str = "", limite: int = 100, tipos: tuple[str, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Retorna histórico de todos os clientes (com filtros opcionais)."""
        base_query = """
            SELECT h.id, h.data_acao, c.nome, h.documento, h.tipo,
                   h.valor, h.categoria, h.usuario, h.obs
            FROM historico_zebra h
            JOIN hospedes c ON h.documento = c.documento
        """
        conditions = []
        params: list[Any] = []

        if filtro:
            conditions.append("(c.nome LIKE ? OR c.documento LIKE ?)")
            params.extend([f"%{filtro}%", f"%{filtro}%"])

        if tipos:
            placeholders = ", ".join("?" for _ in tipos)
            conditions.append(f"h.tipo IN ({placeholders})")
            params.extend(tipos)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " ORDER BY h.id DESC LIMIT ?"
        params.append(int(limite))

        self.cursor.execute(base_query, params)
        return [dict(r) for r in self.cursor.fetchall()]

    def excluir_movimentacao(self, id_mov: int, usuario_acao: str = "Sistema") -> None:
        with self.conn:
            self.cursor.execute("SELECT * FROM historico_zebra WHERE id = ?", (id_mov,))
            mov = self.cursor.fetchone()
            if not mov:
                raise ValueError("Movimentação não encontrada.")
            self.cursor.execute("DELETE FROM historico_zebra WHERE id = ?", (id_mov,))
        self.registrar_log(
            usuario_acao, "EXCLUIR_MOVIMENTACAO", f"ID: {id_mov} | Doc: {mov['documento']} | Valor: {mov['valor']}"
        )

    def atualizar_data_vencimento_manual(self, id_mov: int, data_br: str, usuario_acao: str = "Sistema") -> None:
        d_iso = datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        with self.conn:
            self.cursor.execute("UPDATE historico_zebra SET data_vencimento = ? WHERE id = ?", (d_iso, id_mov))
        self.registrar_log(usuario_acao, "ALTERAR_VENCIMENTO", f"ID Mov: {id_mov} | Nova Data: {data_br}")

    # =========================================================================
    # MÓDULO COMPRAS
    # =========================================================================

    def adicionar_compra(
        self,
        data_compra: str,
        produto: str,
        qtd: Any,
        valor_unit: Any,
        obs: str = "",
        usuario: str = "Sistema",
        lista_id: int | None = None,
    ) -> None:
        qtd_float = self.limpar_valor(qtd)
        unit_float = self.limpar_valor(valor_unit)
        total = qtd_float * unit_float

        try:
            data_iso = datetime.strptime(data_compra, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            data_iso = datetime.now().strftime("%Y-%m-%d")

        with self.conn:
            self.cursor.execute(
                "INSERT INTO compras "
                "(data_compra, produto, quantidade, valor_unitario, valor_total, usuario, obs, lista_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (data_iso, produto.upper().strip(), qtd_float, unit_float, total, usuario, obs, lista_id),
            )
        self.registrar_log(usuario, "ADD_COMPRA", f"Prod: {produto} | Total: {total}")

    def criar_lista_compras(self, usuario: str, obs: str = "") -> int:
        data_hj = datetime.now().strftime("%Y-%m-%d")
        with self.conn:
            self.cursor.execute(
                "INSERT INTO listas_compras (data_criacao, status, usuario, obs) " "VALUES (?, ?, ?, ?)",
                (data_hj, "ABERTA", usuario, obs),
            )
            return self.cursor.lastrowid or 0

    def fechar_lista_compras(self, lista_id: int) -> None:
        with self.conn:
            self.cursor.execute("UPDATE listas_compras SET status = 'FECHADA' WHERE id = ?", (lista_id,))

    def get_listas_resumo(self) -> list[dict[str, Any]]:
        self.cursor.execute("""
            SELECT l.id, l.data_criacao, l.status, l.usuario,
                   COUNT(c.id) as qtd_itens, SUM(c.valor_total) as total_valor
            FROM listas_compras l
            LEFT JOIN compras c ON l.id = c.lista_id
            GROUP BY l.id ORDER BY l.id DESC
        """)
        return [dict(r) for r in self.cursor.fetchall()]

    def get_itens_lista(self, lista_id: int) -> list[dict[str, Any]]:
        self.cursor.execute("SELECT * FROM compras WHERE lista_id = ? ORDER BY id DESC", (lista_id,))
        itens = [dict(r) for r in self.cursor.fetchall()]
        for c in itens:
            self.cursor.execute(
                "SELECT valor_unitario FROM compras "
                "WHERE produto = ? AND data_compra < ? "
                "ORDER BY data_compra DESC LIMIT 1",
                (c["produto"], c["data_compra"]),
            )
            res = self.cursor.fetchone()
            c["tendencia"] = "igual"
            if res:
                if c["valor_unitario"] > res["valor_unitario"]:
                    c["tendencia"] = "subiu"
                elif c["valor_unitario"] < res["valor_unitario"]:
                    c["tendencia"] = "desceu"
        return itens

    def adicionar_produto_predefinido(self, nome: str) -> None:
        if not nome:
            return
        with self.conn:
            self.cursor.execute("INSERT OR IGNORE INTO produtos (nome) VALUES (?)", (nome.upper().strip(),))

    def remover_produto_predefinido(self, nome: str) -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM produtos WHERE nome = ?", (nome,))

    def get_produtos_predefinidos(self) -> list[str]:
        self.cursor.execute("SELECT nome FROM produtos ORDER BY nome")
        return [r["nome"] for r in self.cursor.fetchall()]

    # =========================================================================
    # MÓDULO CALENDÁRIO / AGENDA
    # =========================================================================

    def get_funcionarios(self) -> list[dict]:
        self.cursor.execute("SELECT * FROM funcionarios ORDER BY nome")
        return [dict(r) for r in self.cursor.fetchall()]

    def adicionar_funcionario(self, nome: str, usuario_acao: str = "Sistema") -> None:
        if not nome or not nome.strip():
            raise ValueError("O nome do funcionário não pode ser vazio.")
        with self.conn:
            self.cursor.execute("INSERT OR IGNORE INTO funcionarios (nome) VALUES (?)", (nome.strip().upper(),))
        self.registrar_log(usuario_acao, "ADD_FUNCIONARIO", f"Nome: {nome.strip().upper()}")

    def remover_funcionario(self, funcionario_id: int, usuario_acao: str = "Sistema") -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM agenda WHERE funcionario_id = ?", (funcionario_id,))
            self.cursor.execute("DELETE FROM funcionarios WHERE id = ?", (funcionario_id,))
        self.registrar_log(usuario_acao, "DEL_FUNCIONARIO", f"ID: {funcionario_id}")

    def get_agenda_mes(self, ano: int, mes: int) -> dict[str, str]:
        like_str = f"{ano}-{mes:02d}-%"
        self.cursor.execute(
            """
            SELECT a.data, f.nome FROM agenda a
            JOIN funcionarios f ON a.funcionario_id = f.id
            WHERE a.data LIKE ?
        """,
            (like_str,),
        )
        eventos: dict[str, str] = {}
        for row in self.cursor.fetchall():
            dt, nm = row["data"], row["nome"]
            eventos[dt] = f"{eventos[dt]}, {nm}" if dt in eventos else nm
        return eventos

    def get_tarefas_dia(self, data_iso: str) -> list[dict[str, Any]]:
        self.cursor.execute(
            """
            SELECT a.id, a.data, a.funcionario_id, a.obs, f.nome
            FROM agenda a
            JOIN funcionarios f ON a.funcionario_id = f.id
            WHERE a.data = ?
        """,
            (data_iso,),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def salvar_agendamento(
        self, data_iso: str, funcionario_id: int, obs: str = "", usuario_acao: str = "Sistema"
    ) -> None:
        with self.conn:
            self.cursor.execute(
                "INSERT INTO agenda (data, funcionario_id, obs) VALUES (?, ?, ?)", (data_iso, funcionario_id, obs)
            )
        self.registrar_log(usuario_acao, "SAVE_AGENDAMENTO", f"Data: {data_iso}, FuncID: {funcionario_id}")

    def remover_agendamento_id(self, agenda_id: int, usuario_acao: str = "Sistema") -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM agenda WHERE id = ?", (agenda_id,))
        self.registrar_log(usuario_acao, "DEL_AGENDAMENTO", f"ID: {agenda_id}")

    # =========================================================================
    # DASHBOARD
    # =========================================================================

    def get_dados_dash(self) -> tuple[float, float, float, int, float]:
        """Retorna dados resumidos para o dashboard."""
        self.cursor.execute("SELECT documento FROM hospedes")
        docs = [d["documento"] for d in self.cursor.fetchall()]

        total_saldo, total_vencido, total_a_vencer = 0.0, 0.0, 0.0
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")

        self.cursor.execute("SELECT SUM(valor) FROM historico_zebra WHERE tipo='MULTA'")
        res = self.cursor.fetchone()
        total_multas = res[0] if res and res[0] else 0.0

        for d in docs:
            s, v, b = self._processar_saldo(d)
            if s > 0:
                total_saldo += s
                if v != "N/A":
                    v_iso = datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
                    if b:
                        total_vencido += s
                    elif hoje <= v_iso <= alerta:
                        total_a_vencer += s

        return total_saldo, total_vencido, total_a_vencer, len(docs), total_multas

    def get_dados_grafico_categorias(self) -> list[tuple[str, float]]:
        self.cursor.execute(
            "SELECT categoria, SUM(valor) as total " "FROM historico_zebra WHERE tipo='ENTRADA' GROUP BY categoria"
        )
        return [(r["categoria"], r["total"]) for r in self.cursor.fetchall()]

    def get_dados_grafico_mensal(self) -> tuple[list[str], list[float], list[float]]:
        meses_alvo: list[str] = []
        year, month = datetime.now().year, datetime.now().month
        for _ in range(6):
            meses_alvo.insert(0, f"{year}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1

        start_date = meses_alvo[0] + "-01"
        self.cursor.execute(
            "SELECT strftime('%Y-%m', data_acao) as mes, tipo, SUM(valor) as total "
            "FROM historico_zebra WHERE data_acao >= ? GROUP BY mes, tipo",
            (start_date,),
        )

        dados = {m: {"ENTRADA": 0.0, "SAIDA": 0.0} for m in meses_alvo}
        for r in self.cursor.fetchall():
            if r["mes"] in dados:
                dados[r["mes"]][r["tipo"]] = r["total"]

        entradas = [dados[m]["ENTRADA"] for m in meses_alvo]
        saidas = [dados[m]["SAIDA"] for m in meses_alvo]
        meses_fmt = [datetime.strptime(m, "%Y-%m").strftime("%m/%Y") for m in meses_alvo]
        return meses_fmt, entradas, saidas

    def get_hospedes_vencendo_em_breve(self) -> list[tuple[str, str, str]]:
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        self.cursor.execute("SELECT nome, documento FROM hospedes")
        docs = self.cursor.fetchall()
        resultado = []
        for h in docs:
            s, v, b = self._processar_saldo(h["documento"])
            if v != "N/A":
                v_iso = datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
                if not b and hoje <= v_iso <= alerta:
                    resultado.append((h["nome"], v, f"{s:.2f}"))
        return sorted(resultado, key=lambda x: x[1])

    # =========================================================================
    # CONFIGURAÇÕES & UTILITÁRIOS
    # =========================================================================

    def get_config(self, chave: str) -> int:
        self.cursor.execute("SELECT valor FROM configs WHERE chave = ?", (chave,))
        res = self.cursor.fetchone()
        return res["valor"] if res and res["valor"] is not None else 30

    def set_config(self, chave: str, valor: int, usuario_acao: str = "Sistema") -> None:
        antigo = self.get_config(chave)
        with self.conn:
            self.cursor.execute("INSERT OR REPLACE INTO configs (chave, valor) VALUES (?, ?)", (chave, valor))
        self.registrar_log(usuario_acao, "ALTERAR_CONFIG", f"Chave: {chave} | De: {antigo} Para: {valor}")

    def get_categorias(self) -> list[str]:
        self.cursor.execute("SELECT nome FROM categorias ORDER BY nome")
        return [r["nome"] for r in self.cursor.fetchall()]

    def adicionar_categoria(self, nome: str) -> None:
        if not nome:
            return
        with self.conn:
            self.cursor.execute("INSERT OR IGNORE INTO categorias VALUES (?)", (nome,))

    def remover_categoria(self, nome: str) -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM categorias WHERE nome = ?", (nome,))

    def get_anotacao(self, doc: str) -> str:
        self.cursor.execute("SELECT texto FROM anotacoes WHERE documento = ?", (doc,))
        res = self.cursor.fetchone()
        return res["texto"] if res else ""

    def salvar_anotacao(self, doc: str, texto: str) -> None:
        with self.conn:
            self.cursor.execute("INSERT OR REPLACE INTO anotacoes (documento, texto) VALUES (?, ?)", (doc, texto))

    def registrar_log(self, usuario: str, acao: str, detalhes: str = "") -> None:
        try:
            maquina = socket.gethostname()
        except Exception:
            maquina = "Desconhecido"
        dh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            self.cursor.execute(
                "INSERT INTO logs_auditoria (data_hora, usuario, acao, detalhes, maquina) " "VALUES (?,?,?,?,?)",
                (dh, usuario, acao, detalhes, maquina),
            )

    def get_logs(self) -> list[dict]:
        self.cursor.execute("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 100")
        return [dict(r) for r in self.cursor.fetchall()]

    def limpar_logs_auditoria(self, usuario_acao: str = "Sistema") -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM logs_auditoria")
        self.registrar_log(usuario_acao, "LIMPEZA_LOGS", "Histórico de auditoria apagado completamente.")

    # =========================================================================
    # VALIDAÇÃO DE DOCUMENTOS (CPF/CNPJ)
    # =========================================================================

    def _validar_cpf_cnpj(self, doc: str) -> bool:
        """
        Valida CPF (11 dígitos) ou CNPJ (14 dígitos).
        Outros tamanhos são aceitos como RG/Passaporte se > 3 caracteres.
        """
        numeros = "".join(filter(str.isdigit, str(doc)))

        if len(numeros) not in (11, 14):
            # Não é CPF nem CNPJ — aceita como RG/Passaporte
            return len(str(doc).strip()) >= 3

        # Validação de CPF
        if len(numeros) == 11:
            if numeros == numeros[0] * 11:
                return False  # CPF com todos dígitos iguais (111.111.111-11)
            for i in range(9, 11):
                val = sum(int(numeros[num]) * ((i + 1) - num) for num in range(0, i))
                digit = ((val * 10) % 11) % 10
                if digit != int(numeros[i]):
                    return False
            return True

        # Validação de CNPJ
        if len(numeros) == 14:
            if numeros == numeros[0] * 14:
                return False
            pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            for i in range(12, 14):
                soma = sum(int(numeros[num]) * pesos[num + (1 if i == 12 else 0)] for num in range(0, i))
                digit = 0 if (soma % 11) < 2 else (11 - (soma % 11))
                if digit != int(numeros[i]):
                    return False
            return True

        return True
