"""
Tela de Configurações — Sistema Hotel Santos

RESPONSABILIDADE DESTA TELA:
  - Ajustes gerais do sistema (validade de crédito, dias de alerta, tema)
  - Gerenciamento de usuários (criar, editar, excluir) — só admin
  - Gerenciamento de categorias de movimentação
  - Backup e restauração do banco
  - Visualização do log de auditoria
  - Informações sobre o sistema (versão, empresa)

APENAS ADMINS TÊM ACESSO COMPLETO:
  Usuários comuns podem ver configurações gerais mas não
  alterar usuários nem fazer backup.
"""

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .base import TelaBase


class TelaConfig(TelaBase):
    """
    Tela de configurações e administração do sistema.
    """

    def __init__(self, master, core, usuario, colors, logger=None):
        super().__init__(master, core, usuario, colors)
        self._logger = logger

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()

        self.criar_titulo("⚙️ Configurações", "Ajustes do sistema" + (" — Administrador" if self.is_admin else ""))

        abas = ctk.CTkTabview(self.master)
        abas.pack(fill="both", expand=True, padx=15, pady=10)

        # Abas sempre visíveis
        self._montar_aba_geral(abas.add("🔧 Geral"))
        self._montar_aba_categorias(abas.add("🏷️ Categorias"))
        self._montar_aba_produtos(abas.add("📦 Produtos"))
        self._montar_aba_notificacoes(abas.add("🔔 Notificações"))

        # Abas restritas a admin
        if self.is_admin:
            self._montar_aba_usuarios(abas.add("👤 Usuários"))
            self._montar_aba_banco(abas.add("💾 Banco de Dados"))

        # Aba Sobre: sempre visível
        self._montar_aba_sobre(abas.add("ℹ️ Sobre"))

    # =========================================================================
    # ABA GERAL
    # =========================================================================

    def _montar_aba_geral(self, aba: ctk.CTkFrame):
        """Configurações gerais: validade, alerta, tema."""
        frame = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        # === Seção de Créditos ===
        self._criar_secao_titulo(frame, "💳 Créditos")

        frame_cred = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_cred.pack(fill="x", padx=10, pady=(5, 15))
        frame_cred.columnconfigure(1, weight=1)

        # Validade dos créditos
        ctk.CTkLabel(frame_cred, text="Validade dos créditos (meses):", anchor="w").grid(
            row=0, column=0, padx=15, pady=10, sticky="w"
        )

        validade_atual = self.core.get_config("validade_meses")
        self._spin_validade = ctk.CTkEntry(frame_cred, width=80)
        self._spin_validade.insert(0, str(validade_atual))
        self._spin_validade.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(
            frame_cred,
            text="Após quantos meses o crédito vence?",
            font=ctk.CTkFont(size=11),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
            anchor="w",
        ).grid(row=0, column=2, padx=5, pady=10, sticky="w")

        # Dias de alerta
        ctk.CTkLabel(frame_cred, text="Alerta de vencimento (dias):", anchor="w").grid(
            row=1, column=0, padx=15, pady=10, sticky="w"
        )

        alerta_atual = self.core.get_config("alerta_dias")
        self._spin_alerta = ctk.CTkEntry(frame_cred, width=80)
        self._spin_alerta.insert(0, str(alerta_atual))
        self._spin_alerta.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(
            frame_cred,
            text="Alertar quantos dias antes do vencimento?",
            font=ctk.CTkFont(size=11),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
            anchor="w",
        ).grid(row=1, column=2, padx=5, pady=10, sticky="w")

        # === Seção de Aparência ===
        self._criar_secao_titulo(frame, "🎨 Aparência")

        frame_tema = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_tema.pack(fill="x", padx=10, pady=(5, 15))

        ctk.CTkLabel(frame_tema, text="Tema:", anchor="w", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=15, pady=12
        )

        tema_atual = self.core.get_config("tema")
        # tema == 1 → Dark ("Escuro"), tema == 0 → Light ("Claro")
        self._var_tema = ctk.StringVar(value="Escuro" if tema_atual == 1 else "Claro")
        ctk.CTkOptionMenu(
            frame_tema, variable=self._var_tema, values=["Claro", "Escuro"], width=150, font=ctk.CTkFont(size=13)
        ).pack(side="left", padx=10)

        # === Botão Salvar ===
        ctk.CTkButton(
            frame,
            text="💾 Salvar Configurações",
            command=self._salvar_config_geral,
            width=200,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=15, anchor="w", padx=10)

    def _salvar_config_geral(self):
        """Lê os campos e salva as configurações."""
        try:
            validade = int(self._spin_validade.get())
            alerta = int(self._spin_alerta.get())
        except ValueError:
            self.mostrar_erro("Os campos devem ser números inteiros.")
            return

        if validade < 1 or validade > 120:
            self.mostrar_erro("Validade deve ser entre 1 e 120 meses.")
            return

        if alerta < 1 or alerta > 365:
            self.mostrar_erro("Alerta deve ser entre 1 e 365 dias.")
            return

        tema_val = 1 if self._var_tema.get() == "Escuro" else 0

        self.core.set_config("validade_meses", validade, self.username)
        self.core.set_config("alerta_dias", alerta, self.username)
        self.core.set_config("tema", tema_val, self.username)

        # Aplica o tema imediatamente (sem precisar reiniciar)
        ctk.set_appearance_mode("Dark" if tema_val == 1 else "Light")

        self.mostrar_sucesso("Configurações salvas!")

    # =========================================================================
    # ABA CATEGORIAS
    # =========================================================================

    def _montar_aba_categorias(self, aba: ctk.CTkFrame):
        """Gerenciamento das categorias de movimentação financeira."""

        # Barra de ações
        frame_acoes = ctk.CTkFrame(aba, fg_color="transparent")
        frame_acoes.pack(fill="x", padx=10, pady=10)

        self._entry_nova_cat = ctk.CTkEntry(
            frame_acoes, placeholder_text="Nova categoria...", width=220, font=ctk.CTkFont(size=13)
        )
        self._entry_nova_cat.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            frame_acoes, text="+ Adicionar", command=self._adicionar_categoria, width=120, font=ctk.CTkFont(size=13)
        ).pack(side="left")

        # Lista de categorias
        frame_lista = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        frame_lista.pack(fill="both", expand=True, padx=10)
        self._frame_lista_cats = frame_lista

        self._carregar_categorias()

    def _carregar_categorias(self):
        """Carrega e exibe as categorias."""
        for widget in self._frame_lista_cats.winfo_children():
            widget.destroy()

        categorias = self.core.get_categorias()

        if not categorias:
            ctk.CTkLabel(self._frame_lista_cats, text="Nenhuma categoria cadastrada.", text_color="#aaaaaa").pack(
                pady=20
            )
            return

        for cat in categorias:
            linha = ctk.CTkFrame(
                self._frame_lista_cats, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=6
            )
            linha.pack(fill="x", pady=2)

            ctk.CTkLabel(linha, text=cat, font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=15, pady=8)

            # Botão excluir (fica à direita)
            ctk.CTkButton(
                linha,
                text="✕",
                command=lambda c=cat: self._remover_categoria(c),
                width=32,
                height=28,
                fg_color="#c62828",
                hover_color="#8e0000",
                font=ctk.CTkFont(size=12),
            ).pack(side="right", padx=8, pady=4)

    def _adicionar_categoria(self):
        nome = self._entry_nova_cat.get().strip()
        if not nome:
            return
        self.core.adicionar_categoria(nome)
        self._entry_nova_cat.delete(0, "end")
        self._carregar_categorias()

    def _remover_categoria(self, nome: str):
        if self.confirmar(f"Remover categoria '{nome}'?"):
            self.core.remover_categoria(nome)
            self._carregar_categorias()

    # =========================================================================
    # ABA USUÁRIOS (só admin)
    # =========================================================================

    def _montar_aba_usuarios(self, aba: ctk.CTkFrame):
        """Gerenciamento de usuários do sistema."""

        # Barra de ações
        ctk.CTkButton(
            aba, text="+ Novo Usuário", command=self._abrir_form_usuario, width=150, font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=10, pady=10)

        # Tabela de usuários
        colunas = [
            ("username", 130),
            ("is_admin", 70),
            ("can_change_dates", 110),
            ("can_manage_products", 120),
            ("hospedes", 80),
            ("financeiro", 80),
            ("compras", 80),
            ("dashboard", 85),
            ("relatorios", 85),
        ]
        self._tree_users, _ = self.criar_tabela(aba, colunas)
        self._tree_users.bind("<Double-1>", lambda e: self._ao_clicar_usuario())

        ctk.CTkLabel(
            aba,
            text="💡 Duplo-clique para editar. O usuário 'gabriel' não pode ser excluído.",
            font=ctk.CTkFont(size=11),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).pack(pady=(3, 0))

        self._carregar_usuarios()

    def _carregar_usuarios(self):
        """Carrega lista de usuários na tabela."""
        for item in self._tree_users.get_children():
            self._tree_users.delete(item)

        def _check(val, default=1):
            return "✅" if val else "—"

        for user in self.core.get_usuarios():
            self._tree_users.insert(
                "",
                "end",
                iid=user["username"],
                values=(
                    user["username"],
                    "✅" if user["is_admin"] else "—",
                    _check(user.get("can_change_dates")),
                    _check(user.get("can_manage_products")),
                    _check(user.get("can_access_hospedes", 1)),
                    _check(user.get("can_access_financeiro", 1)),
                    _check(user.get("can_access_compras", 1)),
                    _check(user.get("can_access_dash", 1)),
                    _check(user.get("can_access_relatorios", 1)),
                ),
            )

    def _ao_clicar_usuario(self):
        sel = self._tree_users.selection()
        if sel:
            self._abrir_form_usuario(username=sel[0])

    def _abrir_form_usuario(self, username: str = None):
        """Janela para criar ou editar usuário."""
        modo_edicao = username is not None
        titulo = f"Editar Usuário: {username}" if modo_edicao else "Novo Usuário"

        # Dados do usuário existente (para pré-preencher checkboxes)
        dados_existentes: dict = {}
        if modo_edicao:
            for u in self.core.get_usuarios():
                if u["username"] == username:
                    dados_existentes = u
                    break

        janela = ctk.CTkToplevel(self.master)
        janela.title(titulo)
        janela.geometry("420x520")
        janela.transient(self.master)
        janela.lift()
        janela.after(100, lambda: [janela.grab_set(), janela.focus_force()])

        scroll = ctk.CTkScrollableFrame(janela)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        scroll.columnconfigure(1, weight=1)

        ctk.CTkLabel(scroll, text="Usuário:", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        entry_user = ctk.CTkEntry(scroll, width=200)
        entry_user.grid(row=0, column=1, padx=10, pady=8)

        ctk.CTkLabel(scroll, text="Senha:", anchor="w").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        entry_senha = ctk.CTkEntry(scroll, width=200, show="*")
        entry_senha.grid(row=1, column=1, padx=10, pady=8)

        if modo_edicao:
            entry_user.insert(0, username)
            entry_user.configure(state="disabled")
            ctk.CTkLabel(scroll, text="(em branco = manter)", font=ctk.CTkFont(size=11), text_color="#aaaaaa").grid(
                row=1, column=2, padx=5, sticky="w"
            )

        # === Permissões gerais ===
        ctk.CTkLabel(scroll, text="Permissões:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, columnspan=2, padx=10, pady=(12, 2), sticky="w"
        )

        var_admin = ctk.BooleanVar(value=bool(dados_existentes.get("is_admin", 0)))
        var_datas = ctk.BooleanVar(value=bool(dados_existentes.get("can_change_dates", 0)))
        var_produtos = ctk.BooleanVar(value=bool(dados_existentes.get("can_manage_products", 0)))

        ctk.CTkCheckBox(scroll, text="Administrador", variable=var_admin).grid(
            row=3, column=0, columnspan=2, padx=10, pady=4, sticky="w"
        )
        ctk.CTkCheckBox(scroll, text="Pode alterar datas", variable=var_datas).grid(
            row=4, column=0, columnspan=2, padx=10, pady=4, sticky="w"
        )
        ctk.CTkCheckBox(scroll, text="Pode gerenciar produtos", variable=var_produtos).grid(
            row=5, column=0, columnspan=2, padx=10, pady=4, sticky="w"
        )

        # === Acesso a módulos ===
        ctk.CTkLabel(scroll, text="Acesso a módulos:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=6, column=0, columnspan=2, padx=10, pady=(12, 2), sticky="w"
        )

        modulos_vars = {
            "can_access_hospedes": ctk.BooleanVar(value=bool(dados_existentes.get("can_access_hospedes", 1))),
            "can_access_financeiro": ctk.BooleanVar(value=bool(dados_existentes.get("can_access_financeiro", 1))),
            "can_access_compras": ctk.BooleanVar(value=bool(dados_existentes.get("can_access_compras", 1))),
            "can_access_dash": ctk.BooleanVar(value=bool(dados_existentes.get("can_access_dash", 1))),
            "can_access_relatorios": ctk.BooleanVar(value=bool(dados_existentes.get("can_access_relatorios", 1))),
        }
        modulos_labels = {
            "can_access_hospedes": "👥 Hóspedes",
            "can_access_financeiro": "💰 Financeiro",
            "can_access_compras": "🛒 Compras",
            "can_access_dash": "📊 Dashboard",
            "can_access_relatorios": "📄 Relatórios",
        }

        for row_idx, (key, var) in enumerate(modulos_vars.items(), start=7):
            ctk.CTkCheckBox(scroll, text=modulos_labels[key], variable=var).grid(
                row=row_idx, column=0, columnspan=2, padx=10, pady=4, sticky="w"
            )

        # Frame de botões
        frame_btns = ctk.CTkFrame(janela, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(0, 15))

        def _salvar():
            user = entry_user.get().strip()
            senha = entry_senha.get().strip()
            if not user:
                messagebox.showerror("Obrigatório", "Usuário é obrigatório.", parent=janela)
                return
            if not modo_edicao and not senha:
                messagebox.showerror("Obrigatório", "Senha é obrigatória para novos usuários.", parent=janela)
                return
            if modo_edicao and not senha:
                messagebox.showinfo("Info", "Senha não alterada.", parent=janela)
            else:
                self.core.salvar_usuario(
                    user,
                    senha,
                    var_admin.get(),
                    var_datas.get(),
                    var_produtos.get(),
                    modulos_vars["can_access_hospedes"].get(),
                    modulos_vars["can_access_financeiro"].get(),
                    modulos_vars["can_access_compras"].get(),
                    modulos_vars["can_access_dash"].get(),
                    modulos_vars["can_access_relatorios"].get(),
                    self.username,
                )
            janela.destroy()
            self._carregar_usuarios()

        ctk.CTkButton(frame_btns, text="💾 Salvar", command=_salvar, width=100).pack(side="right", padx=5)

        if modo_edicao and username != "gabriel":

            def _excluir():
                if self.confirmar(f"Excluir usuário '{username}'?"):
                    self.core.excluir_usuario(username, self.username)
                    janela.destroy()
                    self._carregar_usuarios()

            ctk.CTkButton(
                frame_btns, text="🗑️ Excluir", command=_excluir, width=90, fg_color="#c62828", hover_color="#8e0000"
            ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_btns, text="Cancelar", command=janela.destroy, width=90, fg_color="#4a4a4a", hover_color="#333333"
        ).pack(side="right", padx=5)

    # =========================================================================
    # ABA BANCO DE DADOS (só admin)
    # =========================================================================

    def _montar_aba_banco(self, aba: ctk.CTkFrame):
        """Backup, restauração e otimização do banco."""

        frame = ctk.CTkFrame(aba, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # === Backup ===
        self._criar_secao_titulo(frame, "📦 Backup")

        frame_bkp = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_bkp.pack(fill="x", pady=(5, 15))

        ctk.CTkLabel(
            frame_bkp,
            text="Cria uma cópia de segurança do banco de dados.\nOs últimos 20 backups são mantidos automaticamente.",
            font=ctk.CTkFont(size=12),
            justify="left",
        ).pack(padx=15, pady=(10, 5), anchor="w")

        ctk.CTkButton(frame_bkp, text="💾 Fazer Backup Agora", command=self._fazer_backup, width=200).pack(
            padx=15, pady=(5, 10), anchor="w"
        )

        # === Restauração ===
        self._criar_secao_titulo(frame, "♻️ Restaurar Backup")

        frame_rest = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_rest.pack(fill="x", pady=(5, 15))

        ctk.CTkLabel(
            frame_rest,
            text="⚠️ ATENÇÃO: Restaurar um backup apaga TODOS os dados atuais!",
            font=ctk.CTkFont(size=12),
            text_color="#ff9800",
        ).pack(padx=15, pady=(10, 5), anchor="w")

        ctk.CTkButton(
            frame_rest,
            text="📂 Escolher Arquivo de Backup",
            command=self._restaurar_backup,
            width=240,
            fg_color="#c62828",
            hover_color="#8e0000",
        ).pack(padx=15, pady=(5, 10), anchor="w")

        # === Otimização ===
        self._criar_secao_titulo(frame, "🔧 Manutenção")

        frame_manut = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_manut.pack(fill="x", pady=(5, 15))

        ctk.CTkLabel(
            frame_manut,
            text="VACUUM: Remove espaço desperdiçado no banco.\nEquivalente a desfragmentar um HD.",
            font=ctk.CTkFont(size=12),
            justify="left",
        ).pack(padx=15, pady=(10, 5), anchor="w")

        ctk.CTkButton(
            frame_manut,
            text="🔧 Otimizar Banco",
            command=self._otimizar_banco,
            width=180,
            fg_color="#4a4a4a",
            hover_color="#333333",
        ).pack(padx=15, pady=(5, 10), anchor="w")

    def _fazer_backup(self):
        try:
            caminho = self.core.db.fazer_backup()
            self.mostrar_sucesso(f"Backup salvo em:\n{caminho}")
        except Exception as e:
            self.mostrar_erro(f"Erro ao fazer backup: {e}")

    def _restaurar_backup(self):
        arquivo = filedialog.askopenfilename(
            title="Selecionar Backup", filetypes=[("Banco SQLite", "*.db"), ("Todos", "*.*")]
        )
        if not arquivo:
            return
        if self.confirmar(
            "⚠️ ATENÇÃO!\n\nTodos os dados atuais serão SUBSTITUÍDOS pelo backup.\n\nContinuar?", "Confirmar Restauração"
        ):
            try:
                self.core.db.restaurar_backup(arquivo)
                self.mostrar_sucesso("Backup restaurado! Reinicie o aplicativo.")
            except Exception as e:
                self.mostrar_erro(f"Erro ao restaurar: {e}")

    def _otimizar_banco(self):
        try:
            self.core.db.otimizar()
            self.mostrar_sucesso("Banco otimizado com sucesso!")
        except Exception as e:
            self.mostrar_erro(f"Erro: {e}")

    # =========================================================================
    # ABA PRODUTOS
    # =========================================================================

    def _montar_aba_produtos(self, aba: ctk.CTkFrame):
        """Gerenciamento dos produtos predefinidos (catálogo para compras)."""
        can_manage = self.is_admin or bool(self.usuario.get("can_manage_products", 0))

        frame_acoes = ctk.CTkFrame(aba, fg_color="transparent")
        frame_acoes.pack(fill="x", padx=10, pady=10)

        self._entry_novo_prod = ctk.CTkEntry(
            frame_acoes, placeholder_text="Novo produto...", width=220, font=ctk.CTkFont(size=13)
        )
        self._entry_novo_prod.pack(side="left", padx=(0, 10))

        if can_manage:
            ctk.CTkButton(
                frame_acoes, text="+ Adicionar", command=self._adicionar_produto, width=120, font=ctk.CTkFont(size=13)
            ).pack(side="left")
        else:
            ctk.CTkLabel(
                frame_acoes,
                text="Somente leitura — você não tem permissão para gerenciar produtos.",
                font=ctk.CTkFont(size=11),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
            ).pack(side="left", padx=10)

        frame_lista = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        frame_lista.pack(fill="both", expand=True, padx=10)
        self._frame_lista_prods = frame_lista

        self._can_manage_produtos = can_manage
        self._carregar_produtos()

    def _carregar_produtos(self):
        for widget in self._frame_lista_prods.winfo_children():
            widget.destroy()

        produtos = self.core.get_produtos_predefinidos()
        if not produtos:
            ctk.CTkLabel(self._frame_lista_prods, text="Nenhum produto cadastrado.", text_color="#aaaaaa").pack(pady=20)
            return

        for prod in produtos:
            linha = ctk.CTkFrame(
                self._frame_lista_prods, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=6
            )
            linha.pack(fill="x", pady=2)
            ctk.CTkLabel(linha, text=prod, font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=15, pady=8)
            if self._can_manage_produtos:
                ctk.CTkButton(
                    linha,
                    text="✕",
                    command=lambda p=prod: self._remover_produto(p),
                    width=32,
                    height=28,
                    fg_color="#c62828",
                    hover_color="#8e0000",
                    font=ctk.CTkFont(size=12),
                ).pack(side="right", padx=8, pady=4)

    def _adicionar_produto(self):
        nome = self._entry_novo_prod.get().strip()
        if not nome:
            return
        self.core.adicionar_produto_predefinido(nome)
        self._entry_novo_prod.delete(0, "end")
        self._carregar_produtos()

    def _remover_produto(self, nome: str):
        if self.confirmar(f"Remover produto '{nome}'?"):
            self.core.remover_produto_predefinido(nome)
            self._carregar_produtos()

    # =========================================================================
    # ABA NOTIFICAÇÕES
    # =========================================================================

    def _montar_aba_notificacoes(self, aba: ctk.CTkFrame):
        """Logs de auditoria e arquivos de diagnóstico (visível a todos)."""
        frame_topo = ctk.CTkFrame(aba, fg_color="transparent")
        frame_topo.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_topo, text="Últimas 100 ações do sistema", font=ctk.CTkFont(size=13)).pack(side="left")

        if self._logger:
            ctk.CTkButton(
                frame_topo,
                text="📋 Exportar Diagnóstico",
                command=self._exportar_diagnostico,
                width=180,
                fg_color="#0d9488",
                hover_color="#0f766e",
                font=ctk.CTkFont(size=12),
            ).pack(side="right", padx=5)

        if self.is_admin:
            ctk.CTkButton(
                frame_topo,
                text="🗑️ Limpar Logs",
                command=self._limpar_logs,
                width=130,
                fg_color="#c62828",
                hover_color="#8e0000",
                font=ctk.CTkFont(size=12),
            ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_topo,
            text="🔄 Recarregar",
            command=self._carregar_logs,
            width=110,
            fg_color="#4a4a4a",
            hover_color="#333333",
            font=ctk.CTkFont(size=12),
        ).pack(side="right", padx=5)

        colunas = [
            ("data_hora", 140),
            ("usuario", 100),
            ("acao", 160),
            ("detalhes", 300),
            ("maquina", 120),
        ]
        self._tree_logs, _ = self.criar_tabela(aba, colunas)
        self._carregar_logs()

        # Arquivos de log (se logger disponível)
        if self._logger and hasattr(self._logger, "log_dir"):
            log_dir: Path = self._logger.log_dir
            if log_dir.exists():
                log_files = sorted(log_dir.glob("*.log"), reverse=True)[:5]
                if log_files:
                    ctk.CTkLabel(
                        aba,
                        text=f"📁 Arquivos de log recentes ({log_dir})",
                        font=ctk.CTkFont(size=11),
                        text_color=self.colors.get("text_secondary", "#aaaaaa"),
                    ).pack(anchor="w", padx=12, pady=(4, 2))
                    for f in log_files:
                        ctk.CTkLabel(
                            aba,
                            text=f"  • {f.name}  ({f.stat().st_size / 1024:.1f} KB)",
                            font=ctk.CTkFont(size=11),
                            text_color=self.colors.get("text_secondary", "#aaaaaa"),
                        ).pack(anchor="w", padx=20)

    def _carregar_logs(self):
        for item in self._tree_logs.get_children():
            self._tree_logs.delete(item)
        for log in self.core.get_logs():
            self._tree_logs.insert(
                "",
                "end",
                values=(log["data_hora"], log["usuario"], log["acao"], log.get("detalhes", ""), log.get("maquina", "")),
            )

    def _limpar_logs(self):
        if self.confirmar("Limpar TODOS os logs de auditoria? Esta ação não pode ser desfeita."):
            self.core.limpar_logs_auditoria(self.username)
            self._carregar_logs()
            self.mostrar_sucesso("Logs limpos.")

    def _exportar_diagnostico(self):
        try:
            caminho = self._logger.exportar_diagnostico()
            self.mostrar_sucesso(f"Diagnóstico exportado:\n{caminho}")
        except Exception as e:
            self.mostrar_erro(f"Erro ao exportar diagnóstico:\n{e}")

    # =========================================================================
    # ABA SOBRE
    # =========================================================================

    def _montar_aba_sobre(self, aba: ctk.CTkFrame):
        """Informações sobre o sistema e a empresa."""
        frame = ctk.CTkFrame(aba, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=30, pady=30)

        info_empresa = self.core.empresa
        versao = self.core.versao_atual

        # Logo/nome grande
        ctk.CTkLabel(
            frame,
            text="🏨 HOTEL SANTOS",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.colors.get("accent", "#1f6aa5"),
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            frame,
            text=f"Sistema de Gestão — Versão {versao}",
            font=ctk.CTkFont(size=14),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).pack(pady=(0, 20))

        # Informações da empresa
        separador_frame = ctk.CTkFrame(frame, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        separador_frame.pack(fill="x")

        for chave, valor in [
            ("Razão Social", info_empresa.get("razao", "")),
            ("CNPJ", info_empresa.get("cnpj", "")),
            ("Endereço", info_empresa.get("endereco", "")),
            ("Contato", info_empresa.get("contato", "")),
            ("E-mail", info_empresa.get("email", "")),
        ]:
            linha = ctk.CTkFrame(separador_frame, fg_color="transparent")
            linha.pack(fill="x", padx=15, pady=5)
            ctk.CTkLabel(
                linha,
                text=f"{chave}:",
                width=100,
                anchor="w",
                font=ctk.CTkFont(size=13),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
            ).pack(side="left")
            ctk.CTkLabel(linha, text=valor, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")

    # =========================================================================
    # UTILITÁRIO INTERNO
    # =========================================================================

    def _criar_secao_titulo(self, parent, texto: str):
        """Título de seção dentro de uma aba (não confundir com criar_titulo da base)."""
        ctk.CTkLabel(parent, text=texto, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(
            fill="x", padx=10, pady=(15, 2)
        )
