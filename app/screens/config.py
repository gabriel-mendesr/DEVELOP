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

from tkinter import filedialog, messagebox

import customtkinter as ctk

from .base import TelaBase


class TelaConfig(TelaBase):
    """
    Tela de configurações e administração do sistema.
    """

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()

        self.criar_titulo("⚙️ Configurações", "Ajustes do sistema" + (" — Administrador" if self.is_admin else ""))

        abas = ctk.CTkTabview(self.master)
        abas.pack(fill="both", expand=True, padx=15, pady=10)

        # Aba Geral: sempre visível
        self._montar_aba_geral(abas.add("🔧 Geral"))

        # Aba Categorias: sempre visível (gerenciar categorias de movimentação)
        self._montar_aba_categorias(abas.add("🏷️ Categorias"))

        # Abas restritas a admin
        if self.is_admin:
            self._montar_aba_usuarios(abas.add("👤 Usuários"))
            self._montar_aba_banco(abas.add("💾 Banco de Dados"))
            self._montar_aba_logs(abas.add("📋 Auditoria"))

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
        self._var_tema = ctk.StringVar(value="Claro" if tema_atual == 1 else "Escuro")
        ctk.CTkOptionMenu(
            frame_tema, variable=self._var_tema, values=["Escuro", "Claro"], width=150, font=ctk.CTkFont(size=13)
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            frame_tema, text="⚠️ Reinicie o app para aplicar.", font=ctk.CTkFont(size=11), text_color="#ff9800"
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

        tema_val = 1 if self._var_tema.get() == "Claro" else 0

        self.core.set_config("validade_meses", validade, self.username)
        self.core.set_config("alerta_dias", alerta, self.username)
        self.core.set_config("tema", tema_val, self.username)

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
            ("username", 160),
            ("is_admin", 80),
            ("can_change_dates", 140),
            ("can_manage_products", 160),
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

        for user in self.core.get_usuarios():
            self._tree_users.insert(
                "",
                "end",
                iid=user["username"],
                values=(
                    user["username"],
                    "✅ Admin" if user["is_admin"] else "—",
                    "✅ Sim" if user.get("can_change_dates") else "—",
                    "✅ Sim" if user.get("can_manage_products") else "—",
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

        janela = ctk.CTkToplevel(self.master)
        janela.title(titulo)
        janela.geometry("420x340")
        janela.grab_set()

        frame = ctk.CTkFrame(janela)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Usuário:", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        entry_user = ctk.CTkEntry(frame, width=200)
        entry_user.grid(row=0, column=1, padx=10, pady=8)

        ctk.CTkLabel(frame, text="Senha:", anchor="w").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        entry_senha = ctk.CTkEntry(frame, width=200, show="*")
        entry_senha.grid(row=1, column=1, padx=10, pady=8)

        if modo_edicao:
            entry_user.insert(0, username)
            entry_user.configure(state="disabled")
            ctk.CTkLabel(
                frame, text="(deixe em branco para manter)", font=ctk.CTkFont(size=11), text_color="#aaaaaa"
            ).grid(row=1, column=2, padx=5, sticky="w")

        # Checkboxes de permissões
        var_admin = ctk.BooleanVar()
        var_datas = ctk.BooleanVar()
        var_produtos = ctk.BooleanVar()

        ctk.CTkCheckBox(frame, text="Administrador", variable=var_admin).grid(
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w"
        )
        ctk.CTkCheckBox(frame, text="Pode alterar datas", variable=var_datas).grid(
            row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w"
        )
        ctk.CTkCheckBox(frame, text="Pode gerenciar produtos", variable=var_produtos).grid(
            row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w"
        )

        # Frame de botões com botão de excluir (se edição)
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
            # Se editando sem senha, mantém a existente (implementação simplificada)
            if modo_edicao and not senha:
                messagebox.showinfo("Info", "Senha não alterada.", parent=janela)
            else:
                self.core.salvar_usuario(
                    user, senha, var_admin.get(), var_datas.get(), var_produtos.get(), self.username
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
    # ABA AUDITORIA (só admin)
    # =========================================================================

    def _montar_aba_logs(self, aba: ctk.CTkFrame):
        """Exibe o log de auditoria das ações do sistema."""

        frame_topo = ctk.CTkFrame(aba, fg_color="transparent")
        frame_topo.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_topo, text="Últimas 100 ações do sistema", font=ctk.CTkFont(size=13)).pack(side="left")

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
            command=lambda: self._carregar_logs(),
            width=120,
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
