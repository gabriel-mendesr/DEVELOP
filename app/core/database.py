"""
Camada de Banco de Dados — Sistema Hotel Santos

O QUE ESTE ARQUIVO FAZ:
  - Conecta ao banco SQLite
  - Cria as tabelas iniciais
  - Roda migrations de forma organizada (com versionamento)
  - Fornece métodos utilitários para backup e otimização

O QUE ESTE ARQUIVO NÃO FAZ:
  - NÃO tem regras de negócio (cálculo de saldo, validação de CPF, etc.)
  - NÃO gera PDFs ou CSVs
  - NÃO tem nada de interface gráfica

CONCEITO: MIGRATIONS VERSIONADAS
---------------------------------
O SQLite tem um recurso chamado "user_version": um número inteiro que
fica salvo DENTRO do arquivo .db. Funciona como um "carimbo" dizendo
"este banco está na versão X".

Cada migration tem um número. Quando o app abre:
  1. Lê a versão atual do banco (ex: 3)
  2. Roda APENAS as migrations que faltam (4, 5, 6...)
  3. Salva a nova versão no banco

Isso é MUITO melhor que try/except porque:
  - Sabemos exatamente em que estado o banco está
  - Cada migration roda UMA VEZ, garantido
  - Se uma migration falhar, sabemos qual foi
"""

import os
import shutil
import sqlite3
from datetime import datetime

# =============================================================================
# LISTA DE MIGRATIONS
# =============================================================================
# REGRAS PARA ADICIONAR MIGRATIONS:
#   1. NUNCA altere uma migration existente (ela já pode ter rodado no banco
#      dos usuários). Sempre ADICIONE uma nova no final.
#   2. Cada migration é uma lista de comandos SQL.
#   3. O número da versão é a posição na lista (começando em 1).
#   4. Se precisar de lógica Python, use uma função (ver migration 10).
#
# Exemplo: Para adicionar uma coluna "quarto" na tabela hospedes,
# adicione um novo item no final da lista:
#   ["ALTER TABLE hospedes ADD COLUMN quarto TEXT"],
# =============================================================================

MIGRATIONS = [
    # -------------------------------------------------------------------------
    # Versão 1: Tabelas iniciais do sistema
    # -------------------------------------------------------------------------
    [
        """CREATE TABLE IF NOT EXISTS hospedes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            documento TEXT UNIQUE NOT NULL
        )""",
        "CREATE TABLE IF NOT EXISTS categorias (nome TEXT PRIMARY KEY)",
        """CREATE TABLE IF NOT EXISTS historico_zebra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT,
            tipo TEXT,
            valor REAL,
            categoria TEXT,
            data_acao TEXT,
            data_vencimento TEXT,
            obs TEXT,
            FOREIGN KEY (documento) REFERENCES hospedes (documento)
        )""",
        "CREATE TABLE IF NOT EXISTS configs (chave TEXT PRIMARY KEY, valor INTEGER)",
        "CREATE TABLE IF NOT EXISTS anotacoes (documento TEXT PRIMARY KEY, texto TEXT)",
        """CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT,
            is_admin INTEGER,
            can_change_dates INTEGER,
            salt TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS logs_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            usuario TEXT,
            acao TEXT,
            detalhes TEXT,
            maquina TEXT
        )""",
        # Configs padrão
        "INSERT OR IGNORE INTO configs VALUES ('validade_meses', 6)",
        "INSERT OR IGNORE INTO configs VALUES ('alerta_dias', 30)",
        "INSERT OR IGNORE INTO configs VALUES ('tema', 0)",
    ],
    # -------------------------------------------------------------------------
    # Versão 2: Adiciona coluna 'usuario' no histórico
    # (Antes não sabíamos quem fez cada movimentação)
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE historico_zebra ADD COLUMN usuario TEXT",
    ],
    # -------------------------------------------------------------------------
    # Versão 3: Adiciona contato dos hóspedes (telefone e email)
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE hospedes ADD COLUMN telefone TEXT",
        "ALTER TABLE hospedes ADD COLUMN email TEXT",
    ],
    # -------------------------------------------------------------------------
    # Versão 4: Adiciona coluna quarto no histórico
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE historico_zebra ADD COLUMN quarto TEXT",
    ],
    # -------------------------------------------------------------------------
    # Versão 5: Módulo de compras
    # -------------------------------------------------------------------------
    [
        """CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_compra TEXT,
            produto TEXT,
            quantidade REAL,
            valor_unitario REAL,
            valor_total REAL,
            usuario TEXT,
            obs TEXT,
            lista_id INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS listas_compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_criacao TEXT,
            status TEXT DEFAULT 'ABERTA',
            usuario TEXT,
            obs TEXT
        )""",
        "CREATE TABLE IF NOT EXISTS produtos (nome TEXT PRIMARY KEY)",
    ],
    # -------------------------------------------------------------------------
    # Versão 6: Módulo de funcionários e agenda
    # -------------------------------------------------------------------------
    [
        "CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL)",
        """CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            funcionario_id INTEGER,
            obs TEXT,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
        )""",
    ],
    # -------------------------------------------------------------------------
    # Versão 7: Permissão de gerenciar produtos + índices de performance
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE usuarios ADD COLUMN can_manage_products INTEGER DEFAULT 0",
        # Índices aceleram buscas em tabelas grandes.
        # Pense neles como o índice de um livro: em vez de ler página por
        # página, você vai direto ao capítulo certo.
        "CREATE INDEX IF NOT EXISTS idx_hospedes_nome ON hospedes(nome)",
        "CREATE INDEX IF NOT EXISTS idx_historico_doc ON historico_zebra(documento)",
        "CREATE INDEX IF NOT EXISTS idx_compras_prod ON compras(produto)",
        "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)",
    ],
    # -------------------------------------------------------------------------
    # Versão 8: Controle de acesso por módulo
    # Permite que o admin defina quais módulos cada usuário pode acessar.
    # DEFAULT 1 = acesso liberado, para não quebrar usuários existentes.
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE usuarios ADD COLUMN can_access_hospedes INTEGER DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN can_access_financeiro INTEGER DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN can_access_compras INTEGER DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN can_access_dash INTEGER DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN can_access_relatorios INTEGER DEFAULT 1",
    ],
    # -------------------------------------------------------------------------
    # Versão 9: Acesso ao módulo de treinamento
    # DEFAULT 1 = acesso liberado, para não quebrar usuários existentes.
    # -------------------------------------------------------------------------
    [
        "ALTER TABLE usuarios ADD COLUMN can_access_treinamento INTEGER DEFAULT 1",
    ],
]


class Database:
    """
    Gerencia a conexão com o banco de dados SQLite.

    Uso básico:
        db = Database()              # Conecta ao banco padrão
        db = Database(":memory:")    # Banco na memória (para testes!)
        db.conn                      # Acessa a conexão diretamente
        db.cursor                    # Acessa o cursor diretamente
    """

    def __init__(self, db_name: str = "hotel.db"):
        """
        Inicializa a conexão com o banco.

        Args:
            db_name: Nome do arquivo do banco.
                     Use ":memory:" para testes (banco temporário na RAM).
        """
        # Define onde o banco será salvo
        if db_name == ":memory:":
            # Banco na memória — perfeito para testes!
            # Desaparece quando o programa fecha.
            self.db_name = db_name
            self.base_dir = "."
        else:
            # Banco em arquivo — dados persistem entre execuções.
            # Salvamos em APPDATA (Windows) ou HOME (Linux) para evitar
            # problemas de permissão se o app estiver em Program Files.
            app_data: str = (
                (os.environ.get("APPDATA") or os.path.expanduser("~")) if os.name == "nt" else os.path.expanduser("~")
            )
            self.base_dir = os.path.join(app_data, "SistemaHotelSantos")
            os.makedirs(self.base_dir, exist_ok=True)
            self.db_name = os.path.join(self.base_dir, db_name)

        # Conecta ao banco
        self.conn: sqlite3.Connection = sqlite3.connect(
            self.db_name,
            check_same_thread=False,  # Permite acesso de múltiplas threads
        )
        self.conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
        self.conn.text_factory = str
        self.cursor: sqlite3.Cursor = self.conn.cursor()

        # Roda as migrations pendentes
        self._aplicar_migrations()

    # =========================================================================
    # SISTEMA DE MIGRATIONS
    # =========================================================================

    def _get_versao_banco(self) -> int:
        """
        Lê a versão atual do banco de dados.

        O SQLite guarda um número inteiro chamado "user_version" dentro
        do próprio arquivo .db. Usamos ele como contador de migrations.

        Retorna:
            int: Número da última migration aplicada (0 = banco novo)
        """
        self.cursor.execute("PRAGMA user_version")
        return self.cursor.fetchone()[0]

    def _set_versao_banco(self, versao: int) -> None:
        """
        Salva a versão atual no banco.

        NOTA: PRAGMA não aceita parâmetros com ?, por isso usamos f-string.
        Isso é seguro aqui porque 'versao' é sempre um int controlado por nós.
        """
        self.cursor.execute(f"PRAGMA user_version = {versao}")

    def _aplicar_migrations(self) -> None:
        """
        Aplica todas as migrations pendentes.

        Exemplo prático:
            - O banco está na versão 3 (já rodou migrations 1, 2 e 3)
            - Existem 7 migrations na lista
            - Este método roda migrations 4, 5, 6 e 7
            - Salva a versão como 7
        """
        versao_atual = self._get_versao_banco()
        total_migrations = len(MIGRATIONS)

        if versao_atual >= total_migrations:
            # Banco já está atualizado — nada a fazer
            return

        print(f"📦 Banco na versão {versao_atual}, atualizando para {total_migrations}...")

        for i in range(versao_atual, total_migrations):
            numero_migration = i + 1  # Migrations começam em 1 (humano-friendly)
            comandos = MIGRATIONS[i]

            print(f"   ▶ Aplicando migration {numero_migration}...")

            try:
                with self.conn:  # Transação: se falhar, desfaz tudo
                    for sql in comandos:
                        self.cursor.execute(sql)

                # Salva a versão DEPOIS de aplicar com sucesso
                self._set_versao_banco(numero_migration)

            except Exception as e:
                print(f"   ❌ ERRO na migration {numero_migration}: {e}")
                # Em caso de erro, para aqui. As migrations seguintes
                # podem depender desta, então é melhor parar.
                raise RuntimeError(
                    f"Falha na migration {numero_migration}: {e}\n"
                    f"O banco pode estar em estado inconsistente. "
                    f"Restaure um backup ou entre em contato com o suporte."
                ) from e

        print(f"✅ Banco atualizado para versão {total_migrations}")

    # =========================================================================
    # SEED DATA (dados iniciais)
    # =========================================================================

    def popular_dados_iniciais(self, hash_func) -> None:
        """
        Popula o banco com dados iniciais (categorias padrão, usuário admin).

        Chamado DEPOIS das migrations. Separado porque precisa de lógica
        Python (hash de senha) que não cabe em SQL puro.

        Args:
            hash_func: Função que recebe (senha, salt) e retorna o hash.
                       Passamos como argumento para não criar dependência
                       circular entre database.py e models.py.
        """
        import secrets

        with self.conn:
            # Categorias padrão (só se a tabela estiver vazia)
            self.cursor.execute("SELECT 1 FROM categorias LIMIT 1")
            if not self.cursor.fetchone():
                self.cursor.executemany(
                    "INSERT INTO categorias VALUES (?)", [("Remarcacao",), ("Cancelamento",), ("Cortesia",), ("Uso",)]
                )

            # Usuário admin padrão (só se não existir)
            self.cursor.execute("SELECT 1 FROM usuarios WHERE username = 'gabriel'")
            if not self.cursor.fetchone():
                salt = secrets.token_hex(16)
                pass_hash = hash_func("132032", salt)
                self.cursor.execute(
                    "INSERT INTO usuarios (username, password, is_admin, "
                    "can_change_dates, can_manage_products, salt) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("gabriel", pass_hash, 1, 1, 1, salt),
                )

    # =========================================================================
    # BACKUP E MANUTENÇÃO
    # =========================================================================

    def fazer_backup(self) -> str:
        """
        Cria uma cópia do banco de dados.

        O backup é salvo na pasta 'backups/' dentro do diretório do app.
        Mantém no máximo 20 backups (apaga os mais antigos automaticamente).

        Retorna:
            str: Caminho completo do arquivo de backup criado.
        """
        backup_dir = os.path.join(self.base_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = os.path.join(backup_dir, f"backup_{timestamp}.db")
        shutil.copy2(self.db_name, destino)

        # Rotação: mantém só os 20 mais recentes
        try:
            arquivos = sorted(
                [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")], key=os.path.getmtime
            )
            while len(arquivos) > 20:
                os.remove(arquivos.pop(0))
        except Exception:
            pass  # Se falhar a rotação, pelo menos o backup foi feito

        return destino

    def restaurar_backup(self, arquivo_backup: str) -> None:
        """
        Restaura o banco a partir de um arquivo de backup.

        CUIDADO: Isso substitui TODOS os dados atuais!

        Args:
            arquivo_backup: Caminho do arquivo .db de backup.
        """
        if not os.path.exists(arquivo_backup):
            raise FileNotFoundError("Arquivo de backup não encontrado.")

        # Fecha a conexão atual
        self.conn.close()

        # Substitui o banco
        shutil.copy2(arquivo_backup, self.db_name)

        # Reconecta
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.text_factory = str
        self.cursor = self.conn.cursor()

        # Roda migrations (caso o backup seja de uma versão antiga)
        self._aplicar_migrations()

    def otimizar(self) -> None:
        """
        Executa VACUUM — compacta o banco removendo espaço não utilizado.

        Pense nisso como "desfragmentar" o banco. Útil após excluir
        muitos registros.
        """
        # VACUUM precisa rodar fora de uma transação
        old_isolation = self.conn.isolation_level
        self.conn.isolation_level = None
        try:
            self.conn.execute("VACUUM")
        finally:
            self.conn.isolation_level = old_isolation

    def fechar(self) -> None:
        """Fecha a conexão com o banco de dados."""
        self.conn.close()
