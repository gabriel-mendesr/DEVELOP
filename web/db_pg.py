"""Adapter PostgreSQL para o Hotel Santos Web.

Implementa a mesma interface de core.models.SistemaCreditos
usando psycopg2 em vez de SQLite.

Ativado automaticamente quando a variável DATABASE_URL estiver definida.

CORREÇÃO APLICADA: Substituída conexão única por pool de conexões com
reconexão automática (pool_pre_ping equivalente via psycopg2.pool).
Isso resolve o erro 'connection already closed' causado pela hibernação
do banco no Render/Neon.
"""

import hashlib
import os
import secrets
import socket
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import psycopg2
import psycopg2.extras
import psycopg2.pool

# =============================================================================
# Schema PostgreSQL
# =============================================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hospedes (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    documento TEXT UNIQUE NOT NULL,
    telefone TEXT,
    email TEXT,
    ativo INTEGER DEFAULT 1
);
ALTER TABLE hospedes ADD COLUMN IF NOT EXISTS ativo INTEGER DEFAULT 1;

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
    can_access_relatorios INTEGER DEFAULT 1,
    can_access_treinamento INTEGER DEFAULT 1
);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS can_access_treinamento INTEGER DEFAULT 1;

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

CREATE TABLE IF NOT EXISTS funcionarios (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS escala (
    id BIGSERIAL PRIMARY KEY,
    data TEXT NOT NULL,
    turno TEXT NOT NULL,
    funcionario_id INTEGER REFERENCES funcionarios(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tarefas_turno (
    id BIGSERIAL PRIMARY KEY,
    escala_id INTEGER REFERENCES escala(id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,
    concluida INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS funcionario_escala_padrao (
    funcionario_id INTEGER REFERENCES funcionarios(id) ON DELETE CASCADE,
    dia_semana INTEGER NOT NULL,
    turno TEXT NOT NULL,
    PRIMARY KEY (funcionario_id, dia_semana)
);

-- índices
CREATE INDEX IF NOT EXISTS idx_hospedes_nome ON hospedes(nome);
CREATE INDEX IF NOT EXISTS idx_historico_doc ON historico_zebra(documento);
CREATE INDEX IF NOT EXISTS idx_compras_prod ON compras(produto);
CREATE INDEX IF NOT EXISTS idx_escala_data ON escala(data);

-- configs padrão
INSERT INTO configs (chave, valor) VALUES ('validade_meses', 6) ON CONFLICT DO NOTHING;
INSERT INTO configs (chave, valor) VALUES ('alerta_dias', 30) ON CONFLICT DO NOTHING;
INSERT INTO configs (chave, valor) VALUES ('tema', 0) ON CONFLICT DO NOTHING;
"""

_CATEGORIAS_PADRAO = [("Remarcacao",), ("Cancelamento",), ("Cortesia",), ("Uso",)]


def _q(sql: str) -> str:
    """Converte placeholders SQLite (?) para PostgreSQL (%s)."""
    return sql.replace("?", "%s")


def _nova_conexao(url: str) -> psycopg2.extensions.connection:
    """Cria uma nova conexão com o banco, com timeout de conexão."""
    return psycopg2.connect(
        url,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
    )


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
        # Pool com mínimo 1 e máximo 5 conexões simultâneas
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
            connect_timeout=10,
        )
        self._setup_schema()

    # ------------------------------------------------------------------
    # Gerenciamento de conexão com reconexão automática
    # ------------------------------------------------------------------

    @contextmanager
    def _get_conn(self):
        """
        Obtém uma conexão do pool. Se estiver morta (hibernação do Render/Neon),
        fecha e reabre automaticamente antes de devolver.
        """
        conn = self._pool.getconn()
        try:
            # Testa se a conexão ainda está viva
            if conn.closed:
                raise psycopg2.InterfaceError("connection closed")
            conn.cursor().execute("SELECT 1")
        except Exception:
            # Conexão morta: descarta e cria uma nova
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = _nova_conexao(self._url)
            conn.autocommit = False

        try:
            yield conn
        finally:
            try:
                self._pool.putconn(conn)
            except Exception:
                pass

    def _setup_schema(self) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
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
                    cur.executemany(
                        "INSERT INTO categorias VALUES (%s) ON CONFLICT DO NOTHING",
                        _CATEGORIAS_PADRAO,
                    )
            conn.commit()

    # ------------------------------------------------------------------
    # helpers internos
    # ------------------------------------------------------------------

    @contextmanager
    def _tx(self):
        with self._get_conn() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_q(sql), params)
                return [dict(r) for r in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_q(sql), params)
                row = cur.fetchone()
                return dict(row) if row else None

    def _execute(self, sql: str, params: tuple = (), conn=None) -> None:
        if conn:
            with conn.cursor() as cur:
                cur.execute(_q(sql), params)
        else:
            with self._get_conn() as conn_:
                with conn_.cursor() as cur:
                    cur.execute(_q(sql), params)

    def _insert_returning(self, sql: str, params: tuple = (), conn=None) -> int:
        """INSERT … RETURNING id → retorna o id gerado."""
        pg_sql = _q(sql)
        if "returning" not in pg_sql.lower():
            pg_sql += " RETURNING id"

        def _run(c):
            with c.cursor() as cur:
                cur.execute(pg_sql, params)
                row = cur.fetchone()
                return int(row["id"]) if row else 0

        if conn:
            return _run(conn)
        with self._get_conn() as conn_:
            return _run(conn_)

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
        """Gera hash bcrypt. Parâmetro salt ignorado — bcrypt embute o próprio salt."""
        return bcrypt.hashpw(str(password).encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, password: str, stored_hash: str, legacy_salt: str | None = None) -> bool:
        """Verifica senha contra hash bcrypt ou SHA-256 legado."""
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            return bcrypt.checkpw(str(password).encode(), stored_hash.encode())
        if legacy_salt:
            return hashlib.sha256((str(password) + str(legacy_salt)).encode()).hexdigest() == stored_hash
        return hashlib.sha256(str(password).encode()).hexdigest() == stored_hash

    def verificar_login(self, username: str, password: str) -> dict | None:
        row = self._fetchone("SELECT password, salt FROM usuarios WHERE username = %s", (username,))
        if not row:
            return None

        stored_hash = row["password"]
        salt = row["salt"]

        if not self._verify_password(password, stored_hash, legacy_salt=salt):
            return None

        # Migração automática: re-hashar SHA-256 legado para bcrypt
        if not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
            new_hash = self._hash_password(password)
            with self._tx() as conn:
                self._execute(
                    "UPDATE usuarios SET password = %s, salt = NULL WHERE username = %s",
                    (new_hash, username),
                    conn=conn,
                )

        return self._fetchone("SELECT * FROM usuarios WHERE username = %s", (username,))

    def get_usuarios(self) -> list[dict]:
        return self._fetch("SELECT * FROM usuarios")

    def get_usuario(self, username: str) -> dict | None:
        rows = self._fetch("SELECT * FROM usuarios WHERE username = %s", (username,))
        return rows[0] if rows else None

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
        can_access_treinamento: bool = True,
        usuario_acao: str = "Sistema",
    ) -> None:
        phash = self._hash_password(password)
        with self._tx() as conn:
            self._execute(
                """INSERT INTO usuarios
                   (username, password, is_admin, can_change_dates, can_manage_products,
                    can_access_hospedes, can_access_financeiro, can_access_compras,
                    can_access_dash, can_access_relatorios, can_access_treinamento, salt)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                   ON CONFLICT (username) DO UPDATE SET
                     password=EXCLUDED.password, is_admin=EXCLUDED.is_admin,
                     can_change_dates=EXCLUDED.can_change_dates,
                     can_manage_products=EXCLUDED.can_manage_products,
                     can_access_hospedes=EXCLUDED.can_access_hospedes,
                     can_access_financeiro=EXCLUDED.can_access_financeiro,
                     can_access_compras=EXCLUDED.can_access_compras,
                     can_access_dash=EXCLUDED.can_access_dash,
                     can_access_relatorios=EXCLUDED.can_access_relatorios,
                     can_access_treinamento=EXCLUDED.can_access_treinamento,
                     salt=NULL""",
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
                    int(can_access_treinamento),
                ),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "SALVAR_USUARIO", f"Usuario alvo: {username}")

    def atualizar_permissoes_usuario(
        self,
        username: str,
        is_admin: int,
        can_change_dates: int,
        can_manage_products: int,
        can_access_hospedes: int,
        can_access_financeiro: int,
        can_access_compras: int,
        can_access_dash: int,
        can_access_relatorios: int,
        can_access_treinamento: int,
        usuario_acao: str = "Sistema",
    ) -> None:
        with self._tx() as conn:
            self._execute(
                """UPDATE usuarios SET
                   is_admin=?, can_change_dates=?, can_manage_products=?,
                   can_access_hospedes=?, can_access_financeiro=?,
                   can_access_compras=?, can_access_dash=?, can_access_relatorios=?,
                   can_access_treinamento=?
                   WHERE username=?""",
                (
                    is_admin,
                    can_change_dates,
                    can_manage_products,
                    can_access_hospedes,
                    can_access_financeiro,
                    can_access_compras,
                    can_access_dash,
                    can_access_relatorios,
                    can_access_treinamento,
                    username,
                ),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "EDITAR_USUARIO", f"Usuario alvo: {username}")

    def excluir_usuario(self, username: str, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM usuarios WHERE username = ?", (username,), conn=conn)
        self.registrar_log(usuario_acao, "EXCLUIR_USUARIO", f"Usuario alvo: {username}")

    def alterar_senha(self, username: str, nova_senha: str, usuario_acao: str = "Sistema") -> None:
        phash = self._hash_password(nova_senha)
        with self._tx() as conn:
            self._execute(
                "UPDATE usuarios SET password = %s, salt = NULL WHERE username = %s",
                (phash, username),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "ALTERAR_SENHA", f"Usuario alvo: {username}")

    # ------------------------------------------------------------------
    # Hóspedes
    # ------------------------------------------------------------------

    def _validar_cpf_cnpj(self, doc: str) -> bool:
        """Valida CPF (11 dígitos) ou CNPJ (14 dígitos). Outros formatos aceitos como RG/Passaporte."""
        numeros = "".join(filter(str.isdigit, str(doc)))
        if len(numeros) not in (11, 14):
            return len(str(doc).strip()) >= 3
        if len(numeros) == 11:
            if numeros == numeros[0] * 11:
                return False
            for i in range(9, 11):
                val = sum(int(numeros[n]) * ((i + 1) - n) for n in range(0, i))
                if ((val * 10) % 11) % 10 != int(numeros[i]):
                    return False
            return True
        # CNPJ
        if numeros == numeros[0] * 14:
            return False
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for i in range(12, 14):
            soma = sum(int(numeros[n]) * pesos[n + (1 if i == 12 else 0)] for n in range(0, i))
            digit = 0 if (soma % 11) < 2 else (11 - (soma % 11))
            if digit != int(numeros[i]):
                return False
        return True

    def get_hospede(self, doc: str) -> dict | None:
        return self._fetchone("SELECT * FROM hospedes WHERE documento = ?", (doc,))

    def cadastrar_hospede(
        self, nome: str, doc: str, telefone: str = "", email: str = "", usuario_acao: str = "Sistema"
    ) -> None:
        # Normaliza: mantém apenas dígitos (remove pontos, traços, barras)
        doc_limpo = "".join(filter(str.isdigit, str(doc)))
        if not self._validar_cpf_cnpj(doc_limpo):
            raise ValueError("Documento inválido (CPF/CNPJ incorreto). Verifique os dígitos.")
        with self._tx() as conn:
            existing = self._fetchone("SELECT 1 FROM hospedes WHERE documento = ?", (doc_limpo,))
            if existing:
                self._execute(
                    "UPDATE hospedes SET nome = ?, telefone = ?, email = ? WHERE documento = ?",
                    (nome.upper().strip(), telefone, email, doc_limpo),
                    conn=conn,
                )
                self.registrar_log(usuario_acao, "ATUALIZAR_HOSPEDE", f"Doc: {doc_limpo}")
            else:
                self._execute(
                    "INSERT INTO hospedes (nome, documento, telefone, email) VALUES (?, ?, ?, ?)",
                    (nome.upper().strip(), doc_limpo, telefone, email),
                    conn=conn,
                )
                self.registrar_log(usuario_acao, "CADASTRAR_HOSPEDE", f"Doc: {doc_limpo}")

    def inativar_hospede(self, doc: str, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("UPDATE hospedes SET ativo = 0 WHERE documento = ?", (doc,), conn=conn)
        self.registrar_log(usuario_acao, "INATIVAR_HOSPEDE", f"Doc: {doc}")

    def reativar_hospede(self, doc: str, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("UPDATE hospedes SET ativo = 1 WHERE documento = ?", (doc,), conn=conn)
        self.registrar_log(usuario_acao, "REATIVAR_HOSPEDE", f"Doc: {doc}")

    def excluir_hospede(self, doc: str, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM historico_zebra WHERE documento = ?", (doc,), conn=conn)
            self._execute("DELETE FROM anotacoes WHERE documento = ?", (doc,), conn=conn)
            self._execute("DELETE FROM hospedes WHERE documento = ?", (doc,), conn=conn)
        self.registrar_log(usuario_acao, "EXCLUIR_HOSPEDE", f"Doc: {doc}")

    def buscar_filtrado(self, termo: str = "", filtro: str = "todos") -> list[dict]:
        termo_limpo = str(termo).strip()
        hospedes = self._fetch(
            "SELECT nome, documento FROM hospedes WHERE (nome ILIKE %s OR documento LIKE %s) AND ativo = 1",
            (f"%{termo_limpo}%", f"%{termo_limpo}%"),
        )
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        saldos = self._processar_saldos_bulk()
        resultado = []
        for h in hospedes:
            saldo, venc, bloqueado = saldos.get(h["documento"], (0.0, "N/A", False))
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
            resultado.append(
                {
                    "nome": h["nome"],
                    "documento": h["documento"],
                    "saldo": saldo,
                    "vencimento": venc,
                    "bloqueado": bloqueado,
                }
            )
        return resultado

    # ------------------------------------------------------------------
    # Financeiro
    # ------------------------------------------------------------------

    @staticmethod
    def _calcular_saldo_de_movs(movs: list[dict]) -> tuple[float, str, bool]:
        """Calcula (saldo, vencimento_br, bloqueado) a partir de uma lista de movimentações já ordenadas por id."""
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

    def _processar_saldo(self, doc: str) -> tuple[float, str, bool]:
        movs = self._fetch(
            "SELECT tipo, valor, data_vencimento FROM historico_zebra WHERE documento = ? ORDER BY id ASC", (doc,)
        )
        return self._calcular_saldo_de_movs(movs)

    def _processar_saldos_bulk(self) -> dict[str, tuple[float, str, bool]]:
        """Carrega todo o historico_zebra em 1 query e calcula saldo para cada hóspede.
        Use no lugar de N chamadas a _processar_saldo() quando precisar de todos os saldos.
        """
        movs = self._fetch(
            "SELECT documento, tipo, valor, data_vencimento FROM historico_zebra ORDER BY documento, id ASC"
        )
        from collections import defaultdict

        por_doc: dict[str, list[dict]] = defaultdict(list)
        for m in movs:
            por_doc[m["documento"]].append(m)
        return {doc: self._calcular_saldo_de_movs(lista) for doc, lista in por_doc.items()}

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
        with self._tx() as conn:
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
                conn=conn,
            )
        self.registrar_log(usuario, f"ADD_MOV_{tipo}", f"Doc: {doc_limpo}, Valor: {v_float}")

    def adicionar_multa(self, doc: str, valor: Any, motivo: str, obs: str = "", usuario: str = "Sistema") -> None:
        v_float = self.limpar_valor(valor)
        doc_limpo = str(doc).strip()
        with self._tx() as conn:
            self._execute(
                "INSERT INTO historico_zebra "
                "(documento, tipo, valor, categoria, data_acao, obs, usuario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_limpo, "MULTA", v_float, motivo, datetime.now().strftime("%Y-%m-%d"), obs, usuario),
                conn=conn,
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
        with self._tx() as conn:
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
                conn=conn,
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
        t1 = float(r1["t"]) if r1 else 0.0
        t2 = float(r2["t"]) if r2 else 0.0
        return t1 - t2

    def excluir_movimentacao(self, id_mov: int, usuario_acao: str = "Sistema") -> None:
        mov = self._fetchone("SELECT * FROM historico_zebra WHERE id = %s", (id_mov,))
        if not mov:
            raise ValueError("Movimentação não encontrada.")
        with self._tx() as conn:
            self._execute("DELETE FROM historico_zebra WHERE id = %s", (id_mov,), conn=conn)
        self.registrar_log(
            usuario_acao, "EXCLUIR_MOVIMENTACAO", f"ID: {id_mov} | Doc: {mov['documento']} | Valor: {mov['valor']}"
        )

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
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def atualizar_data_vencimento_manual(self, id_mov: int, data_br: str, usuario_acao: str = "Sistema") -> None:
        d_iso = datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        with self._tx() as conn:
            self._execute("UPDATE historico_zebra SET data_vencimento = ? WHERE id = ?", (d_iso, id_mov), conn=conn)
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
        with self._tx() as conn:
            self._execute(
                "INSERT INTO compras "
                "(data_compra, produto, quantidade, valor_unitario, valor_total, usuario, obs, lista_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (data_iso, produto.upper().strip(), qtd_float, unit_float, total, usuario, obs, lista_id),
                conn=conn,
            )
        self.registrar_log(usuario, "ADD_COMPRA", f"Prod: {produto} | Total: {total}")

    def criar_lista_compras(self, usuario: str, obs: str = "") -> int:
        data_hj = datetime.now().strftime("%Y-%m-%d")
        with self._tx() as conn:
            lista_id = self._insert_returning(
                "INSERT INTO listas_compras (data_criacao, status, usuario, obs) VALUES (?, ?, ?, ?)",
                (data_hj, "ABERTA", usuario, obs),
                conn=conn,
            )
        return lista_id

    def fechar_lista_compras(self, lista_id: int) -> None:
        with self._tx() as conn:
            self._execute("UPDATE listas_compras SET status = 'FECHADA' WHERE id = ?", (lista_id,), conn=conn)

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
        with self._tx() as conn:
            self._execute(
                "INSERT INTO produtos (nome) VALUES (?) ON CONFLICT DO NOTHING",
                (nome.upper().strip(),),
                conn=conn,
            )

    def remover_produto_predefinido(self, nome: str) -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM produtos WHERE nome = ?", (nome,), conn=conn)

    def get_produtos_predefinidos(self) -> list[str]:
        rows = self._fetch("SELECT nome FROM produtos ORDER BY nome")
        return [r["nome"] for r in rows]

    def get_historico_precos(self, produtos: list[str]) -> dict[str, list[dict]]:
        if not produtos:
            return {}
        placeholders = ", ".join("%s" for _ in produtos)
        rows = self._fetch(
            f"SELECT produto, data_compra, valor_unitario FROM compras "
            f"WHERE produto IN ({placeholders}) ORDER BY produto, data_compra",
            tuple(produtos),
        )
        resultado: dict[str, list[dict]] = {}
        for r in rows:
            p = r["produto"]
            if p not in resultado:
                resultado[p] = []
            resultado[p].append({"data": r["data_compra"], "valor": float(r["valor_unitario"])})
        return resultado

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_movimentos_mensais(self, meses: int = 6) -> dict:
        """Retorna entradas e saídas agrupadas por mês (últimos N meses)."""
        inicio = (datetime.now().replace(day=1) - timedelta(days=meses * 30)).strftime("%Y-%m-01")
        rows = self._fetch(
            """
            SELECT LEFT(data_acao, 7) AS mes, tipo, COALESCE(SUM(valor), 0)::float AS total
            FROM historico_zebra
            WHERE data_acao >= %s AND tipo IN ('ENTRADA', 'SAIDA')
            GROUP BY mes, tipo
            ORDER BY mes
            """,
            (inicio,),
        )
        # Garante todos os meses no intervalo, mesmo sem movimentos
        meses_labels: list[str] = []
        cur = datetime.now().replace(day=1)
        for _ in range(meses):
            meses_labels.insert(0, cur.strftime("%Y-%m"))
            if cur.month == 1:
                cur = cur.replace(year=cur.year - 1, month=12)
            else:
                cur = cur.replace(month=cur.month - 1)

        entradas = {m: 0.0 for m in meses_labels}
        saidas = {m: 0.0 for m in meses_labels}
        for r in rows:
            mes = r["mes"]
            if mes in entradas:
                if r["tipo"] == "ENTRADA":
                    entradas[mes] = round(float(r["total"]), 2)
                else:
                    saidas[mes] = round(float(r["total"]), 2)

        labels = [f"{m[5:]}/{m[:4]}" for m in meses_labels]  # MM/AAAA
        return {
            "labels": labels,
            "entradas": list(entradas.values()),
            "saidas": list(saidas.values()),
        }

    def get_dados_dash(self) -> tuple[float, float, float, int, float]:
        docs_rows = self._fetch("SELECT documento FROM hospedes")
        docs = [r["documento"] for r in docs_rows]
        total_saldo, total_vencido, total_a_vencer = 0.0, 0.0, 0.0
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        r = self._fetchone("SELECT COALESCE(SUM(valor), 0) AS t FROM historico_zebra WHERE tipo='MULTA'")
        total_multas = float(r["t"]) if r else 0.0
        saldos = self._processar_saldos_bulk()
        for d in docs:
            s, v, b = saldos.get(d, (0.0, "N/A", False))
            if s > 0:
                total_saldo += s
                if v != "N/A":
                    v_iso = datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
                    if b:
                        total_vencido += s
                    elif hoje <= v_iso <= alerta:
                        total_a_vencer += s
        return total_saldo, total_vencido, total_a_vencer, len(docs), total_multas

    def get_devedores_multas(self) -> list[tuple[str, str, str, float]]:
        hospedes = self._fetch("SELECT nome, documento, telefone FROM hospedes")
        saldos = self._processar_saldos_bulk()
        resultado = []
        for h in hospedes:
            saldo, _, bloqueado = saldos.get(h["documento"], (0.0, "N/A", False))
            if bloqueado and saldo > 0:
                resultado.append((h["nome"], h["documento"], h["telefone"] or "", saldo))
        return sorted(resultado, key=lambda x: x[0])

    def get_hospedes_vencendo_em_breve(self) -> list[tuple[str, str, str]]:
        hoje = datetime.now().strftime("%Y-%m-%d")
        alerta = (datetime.now() + timedelta(days=self.get_config("alerta_dias"))).strftime("%Y-%m-%d")
        hospedes = self._fetch("SELECT nome, documento FROM hospedes")
        saldos = self._processar_saldos_bulk()
        resultado = []
        for h in hospedes:
            s, v, b = saldos.get(h["documento"], (0.0, "N/A", False))
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
        with self._tx() as conn:
            self._execute(
                "INSERT INTO configs (chave, valor) VALUES (?, ?) "
                "ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor",
                (chave, valor),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "ALTERAR_CONFIG", f"Chave: {chave} | De: {antigo} Para: {valor}")

    def get_categorias(self) -> list[str]:
        rows = self._fetch("SELECT nome FROM categorias ORDER BY nome")
        return [r["nome"] for r in rows]

    def adicionar_categoria(self, nome: str) -> None:
        if not nome:
            return
        with self._tx() as conn:
            self._execute("INSERT INTO categorias VALUES (?) ON CONFLICT DO NOTHING", (nome,), conn=conn)

    def remover_categoria(self, nome: str) -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM categorias WHERE nome = ?", (nome,), conn=conn)

    def get_anotacao(self, doc: str) -> str:
        row = self._fetchone("SELECT texto FROM anotacoes WHERE documento = ?", (doc,))
        return row["texto"] if row else ""

    def salvar_anotacao(self, doc: str, texto: str) -> None:
        with self._tx() as conn:
            self._execute(
                "INSERT INTO anotacoes (documento, texto) VALUES (?, ?) "
                "ON CONFLICT (documento) DO UPDATE SET texto=EXCLUDED.texto",
                (doc, texto),
                conn=conn,
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
        with self._tx() as conn:
            self._execute(
                "INSERT INTO logs_auditoria (data_hora, usuario, acao, detalhes, maquina) VALUES (?,?,?,?,?)",
                (dh, usuario, acao, detalhes, maquina),
                conn=conn,
            )

    def get_logs(self) -> list[dict]:
        return self._fetch("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 100")

    def limpar_logs_auditoria(self, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM logs_auditoria", conn=conn)
        self.registrar_log(usuario_acao, "LIMPEZA_LOGS", "Histórico de auditoria apagado.")

    # ------------------------------------------------------------------
    # Banco de dados (operações administrativas)
    # ------------------------------------------------------------------

    def otimizar_banco(self) -> None:
        """VACUUM no PostgreSQL."""
        with self._get_conn() as conn:
            old_autocommit = conn.autocommit
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("VACUUM ANALYZE")
            conn.autocommit = old_autocommit

    def fazer_backup(self) -> str:
        return "Backup via pg_dump recomendado para PostgreSQL. Acesse o painel do Neon.tech."

    # ------------------------------------------------------------------
    # Agenda / Turnos
    # ------------------------------------------------------------------

    def get_funcionarios(self) -> list[dict]:
        return self._fetch("SELECT id, nome FROM funcionarios ORDER BY nome")

    def adicionar_funcionario(self, nome: str, usuario_acao: str = "Sistema") -> None:
        if not nome:
            return
        with self._tx() as conn:
            self._execute(
                "INSERT INTO funcionarios (nome) VALUES (?) ON CONFLICT DO NOTHING",
                (nome.upper().strip(),),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "ADD_FUNCIONARIO", f"Nome: {nome.upper().strip()}")

    def remover_funcionario(self, func_id: int, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM funcionarios WHERE id = ?", (func_id,), conn=conn)
        self.registrar_log(usuario_acao, "REM_FUNCIONARIO", f"ID: {func_id}")

    def get_escala_padrao(self, func_id: int) -> dict:
        """Retorna {dia_semana: turno} para o funcionário."""
        rows = self._fetch(
            "SELECT dia_semana, turno FROM funcionario_escala_padrao WHERE funcionario_id = ?",
            (func_id,),
        )
        return {r["dia_semana"]: r["turno"] for r in rows}

    def set_escala_padrao(self, func_id: int, dias_turnos: dict, usuario_acao: str = "Sistema") -> None:
        """Substitui a escala padrão do funcionário. dias_turnos: {dia_semana: turno|''}"""
        with self._tx() as conn:
            self._execute(
                "DELETE FROM funcionario_escala_padrao WHERE funcionario_id = ?",
                (func_id,),
                conn=conn,
            )
            for dia, turno in dias_turnos.items():
                if turno in ("manha", "tarde", "noite"):
                    self._execute(
                        "INSERT INTO funcionario_escala_padrao (funcionario_id, dia_semana, turno) VALUES (?, ?, ?)",
                        (func_id, int(dia), turno),
                        conn=conn,
                    )
        self.registrar_log(usuario_acao, "SET_ESCALA_PADRAO", f"Func ID: {func_id}")

    def get_escala_padrao_all(self) -> dict:
        """Retorna {funcionario_id: {dia_semana: turno}} para todos os funcionários."""
        rows = self._fetch(
            "SELECT funcionario_id, dia_semana, turno FROM funcionario_escala_padrao ORDER BY funcionario_id, dia_semana"
        )
        result: dict = {}
        for r in rows:
            fid = r["funcionario_id"]
            if fid not in result:
                result[fid] = {}
            result[fid][r["dia_semana"]] = r["turno"]
        return result

    def get_escala_dia(self, data_iso: str) -> dict:
        turnos: dict = {"manha": [], "tarde": [], "noite": []}
        rows = self._fetch(
            """SELECT e.id, e.turno, e.funcionario_id, f.nome
               FROM escala e JOIN funcionarios f ON f.id = e.funcionario_id
               WHERE e.data = ? ORDER BY f.nome""",
            (data_iso,),
        )
        for r in rows:
            tarefas = self._fetch(
                "SELECT id, descricao, concluida FROM tarefas_turno WHERE escala_id = ? ORDER BY id",
                (r["id"],),
            )
            entry = {
                "id": r["id"],
                "funcionario_id": r["funcionario_id"],
                "nome": r["nome"],
                "tarefas": [dict(t) for t in tarefas],
            }
            if r["turno"] in turnos:
                turnos[r["turno"]].append(entry)
        return turnos

    def get_resumo_mes(self, ano: int, mes: int) -> dict:
        """Retorna {data: {manha:[nomes], tarde:[nomes], noite:[nomes]}} para o mês."""
        inicio = f"{ano:04d}-{mes:02d}-01"
        fim = f"{ano:04d}-{mes:02d}-31"
        rows = self._fetch(
            """SELECT e.data, e.turno, f.nome
               FROM escala e JOIN funcionarios f ON f.id = e.funcionario_id
               WHERE e.data >= %s AND e.data <= %s ORDER BY e.data, e.turno, f.nome""",
            (inicio, fim),
        )
        resultado: dict = {}
        for r in rows:
            d = r["data"]
            if d not in resultado:
                resultado[d] = {"manha": [], "tarde": [], "noite": []}
            if r["turno"] in resultado[d]:
                resultado[d][r["turno"]].append(r["nome"])
        return resultado

    def get_dias_com_escala(self, ano: int, mes: int) -> set:
        inicio = f"{ano:04d}-{mes:02d}-01"
        fim = f"{ano:04d}-{mes:02d}-31"
        rows = self._fetch(
            "SELECT DISTINCT data FROM escala WHERE data >= ? AND data <= ?",
            (inicio, fim),
        )
        return {r["data"] for r in rows}

    def escalar_funcionario(self, data_iso: str, turno: str, funcionario_id: int, usuario_acao: str = "Sistema") -> int:
        with self._tx() as conn:
            esc_id = self._insert_returning(
                "INSERT INTO escala (data, turno, funcionario_id) VALUES (?, ?, ?)",
                (data_iso, turno, funcionario_id),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "ADD_ESCALA", f"Data: {data_iso} Turno: {turno}")
        return esc_id

    def remover_escala(self, escala_id: int, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM escala WHERE id = ?", (escala_id,), conn=conn)
        self.registrar_log(usuario_acao, "REM_ESCALA", f"ID: {escala_id}")

    def adicionar_tarefa_turno(self, escala_id: int, descricao: str, usuario_acao: str = "Sistema") -> None:
        if not descricao:
            return
        with self._tx() as conn:
            self._execute(
                "INSERT INTO tarefas_turno (escala_id, descricao) VALUES (?, ?)",
                (escala_id, descricao.strip()),
                conn=conn,
            )
        self.registrar_log(usuario_acao, "ADD_TAREFA", f"Escala: {escala_id}")

    def remover_tarefa_turno(self, tarefa_id: int, usuario_acao: str = "Sistema") -> None:
        with self._tx() as conn:
            self._execute("DELETE FROM tarefas_turno WHERE id = ?", (tarefa_id,), conn=conn)
        self.registrar_log(usuario_acao, "REM_TAREFA", f"ID: {tarefa_id}")

    def concluir_tarefa_turno(self, tarefa_id: int, usuario_acao: str = "Sistema") -> None:
        row = self._fetchone("SELECT concluida FROM tarefas_turno WHERE id = ?", (tarefa_id,))
        if row:
            novo = 0 if row["concluida"] else 1
            with self._tx() as conn:
                self._execute(
                    "UPDATE tarefas_turno SET concluida = ? WHERE id = ?",
                    (novo, tarefa_id),
                    conn=conn,
                )
        self.registrar_log(usuario_acao, "TOGGLE_TAREFA", f"ID: {tarefa_id}")
