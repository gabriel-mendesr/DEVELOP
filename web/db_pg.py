"""Adapter PostgreSQL para o Hotel Santos Web.

Implementa a mesma interface de core.models.SistemaCreditos
usando psycopg2 em vez de SQLite.

Ativado automaticamente quando a variável DATABASE_URL estiver definida.
"""

import hashlib
import os
import secrets
import socket
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import psycopg2
import psycopg2.extras

# =============================================================================
# Schema PostgreSQL
# =============================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS hospedes (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    documento TEXT UNIQUE NOT NULL,
    telefone TEXT,
    email TEXT
);
CREATE TABLE IF NOT EXISTS categorias (nome TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS historico_zebra (
    id BIGSERIAL PRIMARY KEY,
    documento TEXT REFERENCES hospedes(documento),
    tipo TEXT,
    valor NUMERIC,
    categoria TEXT,
    data_acao TEXT,
    data_vencimento TEXT,
    obs TEXT,
    usuario TEXT,
    quarto TEXT
);
CREATE TABLE IF NOT EXISTS configs (chave TEXT PRIMARY KEY, valor INTEGER);
CREATE TABLE IF NOT EXISTS anotacoes (documento TEXT PRIMARY KEY, texto TEXT);
CREATE TABLE IF NOT EXISTS usuarios (
    username TEXT PRIMARY KEY,
    password TEXT,
    is_admin INTEGER DEFAULT 0,
    can_change_dates INTEGER DEFAULT 0,
    salt TEXT,
    can_manage_products INTEGER DEFAULT 0,
    can_access_hospedes INTEGER DEFAULT 1,
    can_access_financeiro INTEGER DEFAULT 1,
    can_access_compras INTEGER DEFAULT 1,
    can_access_dash INTEGER DEFAULT 1,
    can_access_relatorios INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS logs_auditoria (
    id BIGSERIAL PRIMARY KEY,
    data_hora TEXT,
    usuario TEXT,
    acao TEXT,
    detalhes TEXT,
    maquina TEXT
);
CREATE TABLE IF NOT EXISTS compras (
    id BIGSERIAL PRIMARY KEY,
    data_compra TEXT,
    produto TEXT,
    quantidade NUMERIC,
    valor_unitario NUMERIC,
    valor_total NUMERIC,
    usuario TEXT,
    obs TEXT,
    lista_id INTEGER
);
CREATE TABLE IF NOT EXISTS listas_compras (
    id BIGSERIAL PRIMARY KEY,
    data_criacao TEXT,
    status TEXT DEFAULT 'ABERTA',
    usuario TEXT,
    obs TEXT
);
CREATE TABLE IF NOT EXISTS produtos (nome TEXT PRIMARY KEY);

-- índices
CREATE INDEX IF NOT EXISTS idx_hospedes_nome ON hospedes(nome);
CREATE INDEX IF NOT EXISTS idx_historico_doc ON historico_zebra(documento);
CREATE INDEX IF NOT EXISTS idx_compras_prod ON compras(produto);

-- configs padrão
INSERT INTO configs (chave, valor) VALUES ('validade_meses', 6) ON CONFLICT DO NOTHING;
INSERT INTO configs (chave, valor) VALUES ('alerta_dias', 30) ON CONFLICT DO NOTHING;
INSERT INTO configs (chave, valor) VALUES ('tema', 0) ON CONFLICT DO NOTHING;
"""

_CATEGORIAS_PADRAO = [("Remarcacao",), ("Cancelamento",), ("Cortesia",), ("Uso",)]


def _q(sql: str) -> str:
    """Converte placeholders SQLite (?) para PostgreSQL (%s)."""
    return sql.replace("?", "%s")


class SistemaCreditos:
    """Interface idêntica à core.models.SistemaCreditos, mas sobre PostgreSQL."""

    empresa = {
        "nome": "HOTEL SANTOS",
        "razao": "Hotel e Restaurante Santos Ana Lucia C. dos Santos",
        "cnpj": "03.288.530/0001-75",
        "endereco": "Praca Mota Sobrinho 10, Centro, ES Pinhal - SP",
        "contato": "Tel: (19) 3651-3297 / Whats: (19) 99759-7503",
        "email": "hotelsantoss@hotmail.com",
    }
    versao_atual = os.getenv("APP_VERSION", "web")

    def __init__(self, database_url: str):
        self._url = database_url
        self.conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        self.conn.autocommit = False
        self._setup_schema()

    def _setup_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(_SCHEMA)
            # Admin padrão
            cur.execute("SELECT 1 FROM usuarios WHERE username = 'admin'")
            if not cur.fetchone():
                salt = secrets.token_hex(16)
                phash = self._hash_password("admin", salt)
                cur.execute(
                    "INSERT INTO usuarios (username, password, is_admin, can_change_dates, salt) "
                    "VALUES (%s, %s, 1, 1, %s) ON CONFLICT DO NOTHING",
                    ("admin", phash, salt),
                )
            # Categorias padrão
            cur.execute("SELECT 1 FROM categorias LIMIT 1")
            if not cur.fetchone():
                cur.executemany("INSERT INTO categorias VALUES (%s) ON CONFLICT DO NOTHING", _CATEGORIAS_PADRAO)
        self.conn.commit()

    # ------------------------------------------------------------------
    # helpers internos
    # ------------------------------------------------------------------

    @contextmanager
    def _tx(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(_q(sql), params)
            return [dict(r) for r in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(_q(sql), params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(_q(sql), params)

    def _insert_returning(self, sql: str, params: tuple = ()) -> int:
        """INSERT … RETURNING id → retorna o id gerado."""
        pg_sql = _q(sql)
        if "returning" not in pg_sql.lower():
            pg_sql += " RETURNING id"
        with self.conn.cursor() as cur:
            cur.execute(pg_sql, params)
            row = cur.fetchone()
            return int(row["id"]) if row else 0

    # ------------------------------------------------------------------
    # Utilitários de valor
    # ------------------------------------------------------------------

    def limpar_valor(self, valor: Any) -> float:
        if isinstance(valor, int | float):
            return float(valor)
        if not valor or str(valor).strip() == "":
            return 0.0
        return float(str(valor).replace(".", "").replace(",", ".").strip())

    # ------------------------------------------------------------------
    # Autenticação & usuários
    # ------------------------------------------------------------------

    def _hash_password(self, password: str, salt: str = "") -> str:
        return hashlib.sha256((str(password) + str(salt)).encode()).hexdigest()

    def verificar_login(self, username: str, password: str) -> dict | None:
        row = self._fetchone("SELECT password, salt FROM usuarios WHERE username = ?", (username,))
        if not row:
            return None
        if row["salt"] is None:
            if hashlib.sha256(str(password).encode()).hexdigest() == row["password"]:
                new_salt = secrets.token_hex(16)
                new_hash = self._hash_password(password, new_salt)
                with self._tx():
                    self._execute(
                        "UPDATE usuarios SET password = ?, salt = ? WHERE username = ?",
                        (new_hash, new_salt, username),
                    )
                return self._fetchone("SELECT * FROM usuarios WHERE username = ?", (username,))
            return None
        if self._hash_password(password, row["salt"]) == row["password"]:
            return self._fetchone("SELECT * FROM usuarios WHERE username = ?", (username,))
        return None

    def get_usuarios(self) -> list[dict]:
        return self._fetch("SELECT * FROM usuarios")

    def salvar_usuario(
        self,
        username: str,
        password: str,
        is_admin: bool,
        can_change_dates: bool,
        can_manage_products: bool,
        can_access_hospedes: bool = True,
        can_access_financeiro: bool = True,
        can_access_compras: bool = True,
        can_access_dash: bool = True,
        can_access_relatorios: bool = True,
        usuario_acao: str = "Sistema",
    ) -> None:
        salt = secrets.token_hex(16)
        phash = self._hash_password(password, salt)
        with self._tx():
            self._execute(
                """INSERT INTO usuarios
                    (username, password, is_admin, can_change_dates, can_manage_products,
                     can_access_hospedes, can_access_financeiro, can_access_compras,
                     can_access_dash, can_access_relatorios, salt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (username) DO UPDATE SET
                     password=EXCLUDED.password, is_admin=EXCLUDED.is_admin,
                     can_change_dates=EXCLUDED.can_change_dates,
                     can_manage_products=EXCLUDED.can_manage_products,
                     can_access_hospedes=EXCLUDED.can_access_hospedes,
                     can_access_financeiro=EXCLUDED.can_access_financeiro,
                     can_access_compras=EXCLUDED.can_access_compras,
                     can_access_dash=EXCLUDED.can_access_dash,
                     can_access_relatorios=EXCLUDED.can_access_relatorios,
                     salt=EXCLUDED.salt""",
                (
                    username,
                    phash,
                    int(is_admin),
                    int(can_change_dates),
                    int(can_manage_products),
                    int(can_access_hospedes),
                    int(can_access_financeiro),
                    int(can_access_compras),
                    int(can_access_dash),
                    int(can_access_relatorios),
                    salt,
                ),
            )
        self.registrar_log(usuario_acao, "SALVAR_USUARIO", f"Usuario alvo: {username}")

    def excluir_usuario(self, username: str, usuario_acao: str = "Sistema") -> None:
        with self._tx():
            self._execute("DELETE FROM usuarios WHERE username = ?", (username,))
        self.registrar_log(usuario_acao, "EXCLUIR_USUARIO", f"Usuario alvo: {username}")

    # ------------------------------------------------------------------
    # Hóspedes
    # ------------------------------------------------------------------

    def _validar_cpf_cnpj(self, doc: str) -> bool:
        d = "".join(filter(str.isdigit, doc))
        return len(d) in (11, 14)

    def get_hospede(self, doc: str) -> dict | None:
        return self._fetchone("SELECT * FROM hospedes WHERE documento = ?", (doc,))

    def cadastrar_hospede(
        self, nome: str, doc: str, telefone: str = "", email: str = "", usuario_acao: str = "Sistema"
    ) -> None:
        doc_limpo = str(doc).strip()
        if not self._validar_cpf_cnpj(doc_limpo):
            raise ValueError("Documento inválido (CPF/CNPJ incorreto). Verifique os dígitos.")
        with self._tx():
            existing = self._fetchone("SELECT 1 FROM hospedes WHERE documento = ?", (doc_limpo,))
            if existing:
                self._execute(
                    "UPDATE hospedes SET nome = ?, telefone = ?, email = ? WHERE documento = ?",
                    (nome.upper().strip(), telefone, email, doc_limpo),
                )
                self.registrar_log(usuario_acao, "ATUALIZAR_HOSPEDE", f"Doc: {doc_limpo}")
            else:
                self._execute(
                    "INSERT INTO hospedes (nome, documento, telefone, email) VALUES (?, ?, ?, ?)",
                    (nome.upper().strip(), doc_limpo, telefone, email),
                )
                self.registrar_log(usuario_acao, "CADASTRAR_HOSPEDE", f"Doc: {doc_limpo}")

    def buscar_filtrado(self, termo: str = "", filtro: str = "todos") -> list[tuple[str, str, float]]:
        termo_limpo = str(termo).strip()
        hospedes = self._fetch(
            "SELECT nome, documento FROM hospedes WHERE nome ILIKE ? OR documento LIKE ?",
            (f"%{termo_limpo}%", f"%{termo_limpo}%"),
        )
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        resultado = []
        for h in hospedes:
            saldo, venc, bloqueado = self._processar_saldo(h["documento"])
            if filtro == "vencidos" and not bloqueado:
                continue
            if filtro == "vencendo":
                if venc == "N/A" or bloqueado:
                    continue
                v_iso = datetime.strptime(venc, "%d/%m/%Y").strftime("%Y-%m-%d")
                if not (hoje <= v_iso <= alerta):
                    continue
            if filtro == "com_multa" and self.get_divida_multas(h["documento"]) <= 0:
                continue
            if saldo <= 0 and filtro not in ("todos", "com_multa"):
                continue
            resultado.append((h["nome"], h["documento"], saldo))
        return resultado

    # ------------------------------------------------------------------
    # Financeiro
    # ------------------------------------------------------------------

    def _processar_saldo(self, doc: str) -> tuple[float, str, bool]:
        movs = self._fetch(
            "SELECT tipo, valor, data_vencimento FROM historico_zebra WHERE documento = ? ORDER BY id ASC", (doc,)
        )
        entradas = [{"valor": float(m["valor"]), "venc": m["data_vencimento"]} for m in movs if m["tipo"] == "ENTRADA"]
        saidas_total = sum(float(m["valor"]) for m in movs if m["tipo"] == "SAIDA")
        hoje = datetime.now().strftime("%Y-%m-%d")
        saldo, prox_venc, bloqueado = 0.0, "N/A", False
        for e in entradas:
            if saidas_total >= e["valor"]:
                saidas_total -= e["valor"]
                e["valor"] = 0.0
            else:
                e["valor"] -= saidas_total
                saidas_total = 0.0
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
        return self._processar_saldo(doc)

    def adicionar_movimentacao(
        self, doc: str, valor: Any, categoria: str, tipo: str, obs: str = "", usuario: str = "Sistema"
    ) -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()
        if not self._fetchone("SELECT 1 FROM hospedes WHERE documento = ?", (doc_limpo,)):
            raise ValueError(f"Hóspede com documento {doc_limpo} não encontrado.")
        if tipo == "SAIDA":
            saldo, venc, bloqueado = self._processar_saldo(doc_limpo)
            if bloqueado:
                raise ValueError(f"BLOQUEIO: Crédito vencido em {venc}!")
            if v_float > saldo:
                raise ValueError("Saldo insuficiente!")
        with self._tx():
            venc_str = ""
            data_hj = datetime.now()
            if tipo == "ENTRADA":
                meses = self.get_config("validade_meses")
                venc_str = (data_hj + timedelta(days=meses * 30)).strftime("%Y-%m-%d")
            self._execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, data_vencimento, obs, usuario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_limpo, tipo, v_float, categoria, data_hj.strftime("%Y-%m-%d"), venc_str, obs, usuario),
            )
        self.registrar_log(usuario, f"ADD_MOV_{tipo}", f"Doc: {doc_limpo}, Valor: {v_float}")

    def adicionar_multa(self, doc: str, valor: Any, motivo: str, obs: str = "", usuario: str = "Sistema") -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()
        with self._tx():
            self._execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, obs, usuario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_limpo, "MULTA", v_float, motivo, datetime.now().strftime("%Y-%m-%d"), obs, usuario),
            )
        self.registrar_log(usuario, "ADD_MULTA", f"Doc: {doc_limpo}, Valor: {v_float}")

    def pagar_multa(self, doc: str, valor: Any, forma_pagamento: str, obs: str = "", usuario: str = "Sistema") -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()
        divida = self.get_divida_multas(doc_limpo)
        if v_float <= 0:
            raise ValueError("Valor deve ser maior que zero.")
        if v_float > divida:
            raise ValueError(f"Valor (R$ {v_float:.2f}) excede a dívida atual (R$ {divida:.2f})")
        with self._tx():
            self._execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, obs, usuario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_limpo,
                    "PAGAMENTO_MULTA",
                    v_float,
                    forma_pagamento,
                    datetime.now().strftime("%Y-%m-%d"),
                    obs,
                    usuario,
                ),
            )
        self.registrar_log(usuario, "PAGAR_MULTA", f"Doc: {doc_limpo}, Valor: {v_float}")

    def get_divida_multas(self, doc: str) -> float:
        r1 = self._fetchone(
            "SELECT COALESCE(SUM(valor), 0) AS t FROM historico_zebra WHERE documento = ? AND tipo = 'MULTA'", (doc,)
        )
        r2 = self._fetchone(
            "SELECT COALESCE(SUM(valor), 0) AS t FROM historico_zebra WHERE documento = ? AND tipo = 'PAGAMENTO_MULTA'",
            (doc,),
        )
        return float(r1["t"]) - float(r2["t"])

    def get_historico_detalhado(self, doc: str) -> list[dict]:
        return self._fetch(
            "SELECT id, tipo, valor, data_acao, categoria, obs, usuario "
            "FROM historico_zebra WHERE documento = ? ORDER BY id DESC",
            (doc,),
        )

    def get_historico_global(
        self,
        filtro: str = "",
        limite: int = 100,
        tipos: tuple[str, ...] | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ) -> list[dict]:
        sql = """
            SELECT h.id, h.data_acao, c.nome, h.documento, h.tipo,
                   h.valor, h.categoria, h.usuario, h.obs
            FROM historico_zebra h
            JOIN hospedes c ON h.documento = c.documento
        """
        conditions: list[str] = []
        params: list[Any] = []
        if filtro:
            conditions.append("(c.nome ILIKE %s OR c.documento LIKE %s)")
            params += [f"%{filtro}%", f"%{filtro}%"]
        if tipos:
            placeholders = ", ".join("%s" for _ in tipos)
            conditions.append(f"h.tipo IN ({placeholders})")
            params += list(tipos)
        if data_inicio:
            conditions.append("h.data_acao >= %s")
            params.append(data_inicio)
        if data_fim:
            conditions.append("h.data_acao <= %s")
            params.append(data_fim)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY h.id DESC LIMIT %s"
        params.append(int(limite))
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def atualizar_data_vencimento_manual(self, id_mov: int, data_br: str, usuario_acao: str = "Sistema") -> None:
        d_iso = datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        with self._tx():
            self._execute("UPDATE historico_zebra SET data_vencimento = ? WHERE id = ?", (d_iso, id_mov))
        self.registrar_log(usuario_acao, "ALTERAR_VENCIMENTO", f"ID Mov: {id_mov} | Nova Data: {data_br}")

    # ------------------------------------------------------------------
    # Compras
    # ------------------------------------------------------------------

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
        with self._tx():
            self._execute(
                "INSERT INTO compras "
                "(data_compra, produto, quantidade, valor_unitario, valor_total, usuario, obs, lista_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (data_iso, produto.upper().strip(), qtd_float, unit_float, total, usuario, obs, lista_id),
            )
        self.registrar_log(usuario, "ADD_COMPRA", f"Prod: {produto} | Total: {total}")

    def criar_lista_compras(self, usuario: str, obs: str = "") -> int:
        data_hj = datetime.now().strftime("%Y-%m-%d")
        with self._tx():
            lista_id = self._insert_returning(
                "INSERT INTO listas_compras (data_criacao, status, usuario, obs) VALUES (?, ?, ?, ?)",
                (data_hj, "ABERTA", usuario, obs),
            )
        return lista_id

    def fechar_lista_compras(self, lista_id: int) -> None:
        with self._tx():
            self._execute("UPDATE listas_compras SET status = 'FECHADA' WHERE id = ?", (lista_id,))

    def get_listas_resumo(self) -> list[dict]:
        return self._fetch("""
            SELECT l.id, l.data_criacao, l.status, l.usuario,
                   COUNT(c.id) AS qtd_itens,
                   COALESCE(SUM(c.valor_total), 0) AS total_valor
            FROM listas_compras l
            LEFT JOIN compras c ON l.id = c.lista_id
            GROUP BY l.id ORDER BY l.id DESC
        """)

    def get_itens_lista(self, lista_id: int) -> list[dict]:
        itens = self._fetch("SELECT * FROM compras WHERE lista_id = ? ORDER BY id DESC", (lista_id,))
        for item in itens:
            anterior = self._fetchone(
                "SELECT valor_unitario FROM compras "
                "WHERE produto = ? AND data_compra < ? ORDER BY data_compra DESC LIMIT 1",
                (item["produto"], item["data_compra"]),
            )
            item["tendencia"] = "igual"
            if anterior:
                vu = float(item["valor_unitario"])
                va = float(anterior["valor_unitario"])
                if vu > va:
                    item["tendencia"] = "subiu"
                elif vu < va:
                    item["tendencia"] = "desceu"
        return itens

    def adicionar_produto_predefinido(self, nome: str) -> None:
        if not nome:
            return
        with self._tx():
            self._execute(
                "INSERT INTO produtos (nome) VALUES (?) ON CONFLICT DO NOTHING",
                (nome.upper().strip(),),
            )

    def remover_produto_predefinido(self, nome: str) -> None:
        with self._tx():
            self._execute("DELETE FROM produtos WHERE nome = ?", (nome,))

    def get_produtos_predefinidos(self) -> list[str]:
        rows = self._fetch("SELECT nome FROM produtos ORDER BY nome")
        return [r["nome"] for r in rows]

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dados_dash(self) -> tuple[float, float, float, int, float]:
        docs_rows = self._fetch("SELECT documento FROM hospedes")
        docs = [r["documento"] for r in docs_rows]
        total_saldo, total_vencido, total_a_vencer = 0.0, 0.0, 0.0
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        r = self._fetchone("SELECT COALESCE(SUM(valor), 0) AS t FROM historico_zebra WHERE tipo='MULTA'")
        total_multas = float(r["t"]) if r else 0.0
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

    def get_hospedes_vencendo_em_breve(self) -> list[tuple[str, str, str]]:
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        hospedes = self._fetch("SELECT nome, documento FROM hospedes")
        resultado = []
        for h in hospedes:
            s, v, b = self._processar_saldo(h["documento"])
            if v != "N/A":
                v_iso = datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
                if not b and hoje <= v_iso <= alerta:
                    resultado.append((h["nome"], v, f"{s:.2f}"))
        return sorted(resultado, key=lambda x: x[1])

    # ------------------------------------------------------------------
    # Configurações
    # ------------------------------------------------------------------

    def get_config(self, chave: str) -> int:
        row = self._fetchone("SELECT valor FROM configs WHERE chave = ?", (chave,))
        return int(row["valor"]) if row and row["valor"] is not None else 30

    def set_config(self, chave: str, valor: int, usuario_acao: str = "Sistema") -> None:
        antigo = self.get_config(chave)
        with self._tx():
            self._execute(
                "INSERT INTO configs (chave, valor) VALUES (?, ?) "
                "ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor",
                (chave, valor),
            )
        self.registrar_log(usuario_acao, "ALTERAR_CONFIG", f"Chave: {chave} | De: {antigo} Para: {valor}")

    def get_categorias(self) -> list[str]:
        rows = self._fetch("SELECT nome FROM categorias ORDER BY nome")
        return [r["nome"] for r in rows]

    def adicionar_categoria(self, nome: str) -> None:
        if not nome:
            return
        with self._tx():
            self._execute("INSERT INTO categorias VALUES (?) ON CONFLICT DO NOTHING", (nome,))

    def remover_categoria(self, nome: str) -> None:
        with self._tx():
            self._execute("DELETE FROM categorias WHERE nome = ?", (nome,))

    def get_anotacao(self, doc: str) -> str:
        row = self._fetchone("SELECT texto FROM anotacoes WHERE documento = ?", (doc,))
        return row["texto"] if row else ""

    def salvar_anotacao(self, doc: str, texto: str) -> None:
        with self._tx():
            self._execute(
                "INSERT INTO anotacoes (documento, texto) VALUES (?, ?) "
                "ON CONFLICT (documento) DO UPDATE SET texto=EXCLUDED.texto",
                (doc, texto),
            )

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def registrar_log(self, usuario: str, acao: str, detalhes: str = "") -> None:
        try:
            maquina = socket.gethostname()
        except Exception:
            maquina = "Desconhecido"
        dh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._tx():
            self._execute(
                "INSERT INTO logs_auditoria (data_hora, usuario, acao, detalhes, maquina) VALUES (?,?,?,?,?)",
                (dh, usuario, acao, detalhes, maquina),
            )

    def get_logs(self) -> list[dict]:
        return self._fetch("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 100")

    def limpar_logs_auditoria(self, usuario_acao: str = "Sistema") -> None:
        with self._tx():
            self._execute("DELETE FROM logs_auditoria")
        self.registrar_log(usuario_acao, "LIMPEZA_LOGS", "Histórico de auditoria apagado.")

    # ------------------------------------------------------------------
    # Banco de dados (operações administrativas)
    # ------------------------------------------------------------------

    def otimizar_banco(self) -> None:
        """VACUUM no PostgreSQL."""
        old_autocommit = self.conn.autocommit
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("VACUUM ANALYZE")
        self.conn.autocommit = old_autocommit

    def fazer_backup(self) -> str:
        return "Backup via pg_dump recomendado para PostgreSQL. Acesse o painel do Neon.tech."
