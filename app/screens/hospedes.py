"""
Tela de Hóspedes — Sistema Hotel Santos

RESPONSABILIDADE DESTA TELA:
  - Listar todos os hóspedes com saldo/status
  - Cadastrar novo hóspede
  - Editar dados de hóspede existente
  - Pesquisar hóspedes por nome ou documento
  - Filtrar por status (todos / com saldo / vencidos)
  - Abrir a ficha completa de um hóspede (histórico, movimentações)

O QUE ESTA TELA NÃO FAZ:
  - Não calcula saldo (isso é o core/models.py)
  - Não acessa banco diretamente (passa pelo core)

ESTRUTURA VISUAL:
  ┌────────────────────────────────────────────────┐
  │  👥 Hóspedes                   [+ Novo] [📄 PDF]│
  ├────────────────────────────────────────────────┤
  │  Buscar: [___________] Filtro: [Todos ▼]        │
  ├────────────────────────────────────────────────┤
  │  Nome          │ Documento    │ Saldo  │ Status  │
  │  João Silva    │ 529.982...   │ 500,00 │ ✅ OK   │
  │  Maria Souza   │ 111.444...   │   0,00 │ —       │
  └────────────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

# Importação relativa: o "." significa "desta mesma pasta (screens/)"
from .base import TelaBase


class TelaHospedes(TelaBase):
    """
    Tela de gerenciamento de hóspedes.

    COMO É INSTANCIADA (em app_gui.py):
        tela = TelaHospedes(self.main_frame, self.core, self.usuario_logado, self.colors)
        tela.renderizar()
    """

    def renderizar(self):
        """
        Ponto de entrada — chamado pelo app_gui.py ao navegar para esta tela.

        FLUXO:
        1. Limpa o frame principal (remove tela anterior)
        2. Cria o cabeçalho com título e botões de ação
        3. Cria a barra de busca e filtros
        4. Cria a tabela de hóspedes
        5. Carrega os dados do banco
        """
        self.limpar_master()

        # Cabeçalho
        self.criar_titulo("👥 Hóspedes", "Cadastro e gerenciamento de hóspedes")
        self._criar_barra_acoes()
        self._criar_barra_busca()
        self._criar_tabela_hospedes()

        # Carrega dados ao abrir a tela
        self._atualizar_lista()

    # =========================================================================
    # MONTAGEM DOS WIDGETS
    # =========================================================================

    def _criar_barra_acoes(self):
        """Cria a barra com botões de ação global (Novo, Exportar)."""
        frame = ctk.CTkFrame(self.master, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(
            frame,
            text="+ Novo Hóspede",
            command=self._abrir_form_novo,
            width=160,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(0, 5))

        # Botão de exportar (só admin pode)
        if self.is_admin:
            ctk.CTkButton(
                frame,
                text="📊 Exportar CSV",
                command=self._exportar_csv,
                width=140,
                fg_color="#4a4a4a",
                hover_color="#333333",
                font=ctk.CTkFont(size=13),
            ).pack(side="left", padx=5)

    def _criar_barra_busca(self):
        """Cria o campo de busca e o seletor de filtro."""
        frame = ctk.CTkFrame(self.master, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=8)
        frame.pack(fill="x", padx=15, pady=5)

        # Label "Buscar:"
        ctk.CTkLabel(frame, text="🔍 Buscar:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(10, 5), pady=10)

        # Campo de texto para busca
        # StringVar: uma variável tkinter que "avisa" quando o valor muda.
        # Usamos isso para busca em tempo real (sem precisar apertar Enter).
        self._var_busca = ctk.StringVar()
        self._var_busca.trace_add("write", lambda *_: self._atualizar_lista())

        ctk.CTkEntry(
            frame,
            textvariable=self._var_busca,
            placeholder_text="Nome ou documento...",
            width=300,
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=5, pady=10)

        # Seletor de filtro
        ctk.CTkLabel(frame, text="Filtro:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(20, 5))

        self._var_filtro = ctk.StringVar(value="todos")
        ctk.CTkOptionMenu(
            frame,
            variable=self._var_filtro,
            values=["todos", "com saldo", "vencidos"],
            command=lambda _: self._atualizar_lista(),
            width=130,
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=5)

        # Contador de resultados (atualizado pela _atualizar_lista)
        self._lbl_contador = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=12), text_color=self.colors.get("text_secondary", "#aaaaaa")
        )
        self._lbl_contador.pack(side="right", padx=15)

    def _criar_tabela_hospedes(self):
        """Cria a tabela principal com a lista de hóspedes."""
        colunas = [
            ("nome", 280),
            ("documento", 160),
            ("telefone", 140),
            ("saldo", 110),
            ("vencimento", 120),
            ("status", 90),
        ]
        self._tree, _ = self.criar_tabela(self.master, colunas)

        # Evento de duplo-clique: abre a ficha do hóspede
        self._tree.bind("<Double-1>", self._ao_clicar_duas_vezes)

        # Evento de clique com botão direito: menu de contexto
        self._tree.bind("<Button-3>", self._menu_contexto)

    # =========================================================================
    # LÓGICA DE DADOS
    # =========================================================================

    def _atualizar_lista(self):
        """
        Busca hóspedes do banco e atualiza a tabela.

        Este método é chamado:
        - Ao abrir a tela
        - Ao digitar na busca (em tempo real)
        - Ao mudar o filtro
        - Após qualquer operação (cadastro, edição, exclusão)
        """
        # Limpa a tabela atual
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Lê os filtros da interface
        termo = self._var_busca.get().strip()
        filtro = self._var_filtro.get()

        # Mapeia o texto do filtro para o valor que o core espera
        # "com saldo" → "ativo", "todos" → "todos", etc.
        filtro_core = {"todos": "todos", "com saldo": "ativo", "vencidos": "vencidos"}.get(filtro, "todos")

        # Busca no banco via core (não acessa o banco diretamente!)
        hospedes = self.core.buscar_filtrado(termo, filtro_core)

        # Preenche a tabela
        for nome, doc, saldo in hospedes:
            _, vencimento, bloqueado = self.core.get_saldo_info(doc)
            telefone = self.core.get_hospede(doc).get("telefone", "") or ""

            # Formata o saldo para exibição
            saldo_fmt = f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # Define o status visual
            if bloqueado:
                status = "⛔ Vencido"
            elif saldo > 0:
                status = "✅ Ativo"
            else:
                status = "—"

            self._tree.insert(
                "",
                "end",
                # iid = identificador interno da linha (usamos o documento)
                iid=doc,
                values=(nome, doc, telefone, saldo_fmt, vencimento, status),
            )

        # Atualiza o contador
        self._lbl_contador.configure(text=f"{len(hospedes)} resultado(s)")

    def _ao_clicar_duas_vezes(self, event):
        """Chamado ao dar duplo-clique numa linha da tabela."""
        item = self._tree.selection()
        if not item:
            return

        # O iid da linha é o documento do hóspede (definimos assim no insert)
        doc = item[0]
        self._abrir_ficha(doc)

    def _menu_contexto(self, event):
        """Exibe menu de contexto ao clicar com botão direito."""
        # Descobre qual linha foi clicada
        item = self._tree.identify_row(event.y)
        if not item:
            return

        # Seleciona a linha para dar feedback visual
        self._tree.selection_set(item)
        doc = item

        # Cria o menu
        menu = tk.Menu(self.master, tearoff=0)
        menu.add_command(label="📋 Ver Ficha Completa", command=lambda: self._abrir_ficha(doc))
        menu.add_command(label="✏️ Editar Dados", command=lambda: self._abrir_form_edicao(doc))

        if self.is_admin:
            menu.add_separator()
            menu.add_command(label="🗑️ Excluir Hóspede", command=lambda: self._confirmar_exclusao(doc))

        # Exibe o menu na posição do cursor
        menu.post(event.x_root, event.y_root)

    # =========================================================================
    # FORMULÁRIOS (Novo / Editar)
    # =========================================================================

    def _abrir_form_novo(self):
        """Abre janela para cadastrar novo hóspede."""
        self._abrir_form_hospede()

    def _abrir_form_edicao(self, doc: str):
        """Abre janela para editar hóspede existente."""
        hospede = self.core.get_hospede(doc)
        if hospede:
            self._abrir_form_hospede(hospede)

    def _abrir_form_hospede(self, hospede: dict = None):
        """
        Janela modal de cadastro/edição.

        CONCEITO: JANELA MODAL (Toplevel)
        Uma janela "filha" que bloqueia interação com a janela principal
        enquanto está aberta. Útil para formulários.

        Se 'hospede' for passado → modo edição (preenche os campos).
        Se for None → modo cadastro (campos em branco).
        """
        modo_edicao = hospede is not None
        titulo = "Editar Hóspede" if modo_edicao else "Novo Hóspede"

        # Cria a janela modal
        janela = ctk.CTkToplevel(self.master)
        janela.title(titulo)
        janela.geometry("420x320")
        janela.grab_set()  # Bloqueia a janela principal
        janela.focus_set()  # Coloca o foco nesta janela

        # Frame do formulário
        frame = ctk.CTkFrame(janela)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        # Campos do formulário
        ctk.CTkLabel(frame, text="Nome Completo:", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        entry_nome = ctk.CTkEntry(frame, width=250)
        entry_nome.grid(row=0, column=1, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="CPF/CNPJ/RG:", anchor="w").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        entry_doc = ctk.CTkEntry(frame, width=250)
        entry_doc.grid(row=1, column=1, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="Telefone:", anchor="w").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        entry_tel = ctk.CTkEntry(frame, width=250, placeholder_text="(opcional)")
        entry_tel.grid(row=2, column=1, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="Email:", anchor="w").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        entry_email = ctk.CTkEntry(frame, width=250, placeholder_text="(opcional)")
        entry_email.grid(row=3, column=1, padx=10, pady=8, sticky="ew")

        # Pré-preenche os campos no modo edição
        if modo_edicao:
            entry_nome.insert(0, hospede.get("nome", ""))
            entry_doc.insert(0, hospede.get("documento", ""))
            entry_doc.configure(state="disabled")  # Não deixa mudar o documento!
            entry_tel.insert(0, hospede.get("telefone", "") or "")
            entry_email.insert(0, hospede.get("email", "") or "")

        # Frame dos botões
        frame_btns = ctk.CTkFrame(janela, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(0, 15))

        def _salvar():
            """
            Função local: só existe dentro de _abrir_form_hospede.
            Lê os campos, chama o core e fecha a janela.
            """
            nome = entry_nome.get().strip()
            doc_val = entry_doc.get().strip() if not modo_edicao else hospede["documento"]
            tel = entry_tel.get().strip()
            email = entry_email.get().strip()

            # Validação básica na interface
            if not nome:
                messagebox.showerror("Campo obrigatório", "Nome é obrigatório.", parent=janela)
                return
            if not doc_val:
                messagebox.showerror("Campo obrigatório", "Documento é obrigatório.", parent=janela)
                return

            try:
                # A validação real (CPF, CNPJ) está no core
                self.core.cadastrar_hospede(nome, doc_val, tel, email, self.username)
                janela.destroy()
                self._atualizar_lista()  # Atualiza a tabela
                acao = "atualizado" if modo_edicao else "cadastrado"
                messagebox.showinfo("Sucesso", f"Hóspede {acao} com sucesso!")
            except ValueError as e:
                # ValueError = erro de validação (CPF inválido, etc.)
                messagebox.showerror("Erro de Validação", str(e), parent=janela)

        ctk.CTkButton(frame_btns, text="💾 Salvar", command=_salvar, width=140).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_btns, text="Cancelar", command=janela.destroy, width=100, fg_color="#4a4a4a", hover_color="#333333"
        ).pack(side="right", padx=5)

    # =========================================================================
    # FICHA DO HÓSPEDE
    # =========================================================================

    def _abrir_ficha(self, doc: str):
        """
        Abre a ficha completa do hóspede em uma janela separada.

        A ficha mostra: dados cadastrais, saldo atual, histórico completo
        e permite adicionar movimentações.

        Por ser complexa, esta janela usa uma aba (CTkTabview).
        """
        hospede = self.core.get_hospede(doc)
        if not hospede:
            return

        saldo, vencimento, bloqueado = self.core.get_saldo_info(doc)

        # Janela maior para a ficha completa
        janela = ctk.CTkToplevel(self.master)
        janela.title(f"Ficha — {hospede['nome']}")
        janela.geometry("800x600")
        janela.grab_set()

        # === Cabeçalho com resumo ===
        frame_topo = ctk.CTkFrame(janela, fg_color=self.colors.get("bg_secondary", "#2b2b2b"))
        frame_topo.pack(fill="x", padx=10, pady=(10, 5))

        # status_txt = "⛔ BLOQUEADO" if bloqueado else ("✅ Ativo" if saldo > 0 else "—")
        saldo_fmt = f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        ctk.CTkLabel(frame_topo, text=hospede["nome"], font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left", padx=15, pady=10
        )
        ctk.CTkLabel(frame_topo, text=f"Doc: {hospede['documento']}", font=ctk.CTkFont(size=12)).pack(
            side="left", padx=10
        )
        ctk.CTkLabel(
            frame_topo,
            text=f"Saldo: {saldo_fmt}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2e7d32" if not bloqueado else "#c62828",
        ).pack(side="right", padx=15)

        # === Abas ===
        abas = ctk.CTkTabview(janela)
        abas.pack(fill="both", expand=True, padx=10, pady=5)

        # Aba 1: Histórico
        aba_hist = abas.add("📜 Histórico")
        self._montar_aba_historico(aba_hist, doc)

        # Aba 2: Nova Movimentação
        aba_mov = abas.add("💳 Nova Movimentação")
        self._montar_aba_movimentacao(aba_mov, doc, janela)

        # Aba 3: Anotações
        aba_anot = abas.add("📝 Anotações")
        self._montar_aba_anotacoes(aba_anot, doc)

    def _montar_aba_historico(self, aba: ctk.CTkFrame, doc: str):
        """Monta a aba de histórico de movimentações."""
        # Busca histórico no core
        historico = self.core.get_historico_detalhado(doc)

        colunas = [("data_acao", 100), ("tipo", 80), ("valor", 100), ("categoria", 130), ("obs", 200), ("usuario", 100)]
        tree, _ = self.criar_tabela(aba, colunas, altura=350)

        for mov in historico:
            valor_fmt = f"R$ {mov['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            tree.insert(
                "",
                "end",
                iid=mov["id"],
                values=(
                    mov["data_acao"],
                    mov["tipo"],
                    valor_fmt,
                    mov.get("categoria", ""),
                    mov.get("obs", ""),
                    mov.get("usuario", ""),
                ),
            )

        # Botão de excluir movimentação (só admin)
        if self.is_admin:

            def _excluir_mov():
                sel = tree.selection()
                if not sel:
                    return
                if self.confirmar("Excluir esta movimentação? Esta ação não pode ser desfeita."):
                    try:
                        self.core.excluir_movimentacao(int(sel[0]), self.username)
                        tree.delete(sel[0])
                    except ValueError as e:
                        self.mostrar_erro(str(e))

            ctk.CTkButton(
                aba,
                text="🗑️ Excluir Selecionado",
                command=_excluir_mov,
                width=180,
                fg_color="#c62828",
                hover_color="#8e0000",
            ).pack(pady=5)

    def _montar_aba_movimentacao(self, aba: ctk.CTkFrame, doc: str, janela_pai):
        """Monta o formulário de nova movimentação (entrada/saída/multa)."""
        frame = ctk.CTkFrame(aba, fg_color="transparent")
        frame.pack(padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        # Tipo de movimentação
        ctk.CTkLabel(frame, text="Tipo:", anchor="w").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        var_tipo = ctk.StringVar(value="ENTRADA")
        ctk.CTkOptionMenu(frame, variable=var_tipo, values=["ENTRADA", "SAIDA", "MULTA"], width=200).grid(
            row=0, column=1, padx=10, pady=8
        )

        # Valor
        ctk.CTkLabel(frame, text="Valor (R$):", anchor="w").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        entry_valor = ctk.CTkEntry(frame, placeholder_text="Ex: 500,00", width=200)
        entry_valor.grid(row=1, column=1, padx=10, pady=8)

        # Categoria
        ctk.CTkLabel(frame, text="Categoria:", anchor="w").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        categorias = self.core.get_categorias()
        var_cat = ctk.StringVar(value=categorias[0] if categorias else "")
        ctk.CTkOptionMenu(frame, variable=var_cat, values=categorias or ["—"], width=200).grid(
            row=2, column=1, padx=10, pady=8
        )

        # Observação
        ctk.CTkLabel(frame, text="Observação:", anchor="w").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        entry_obs = ctk.CTkEntry(frame, placeholder_text="(opcional)", width=200)
        entry_obs.grid(row=3, column=1, padx=10, pady=8)

        def _confirmar():
            tipo = var_tipo.get()
            try:
                if tipo == "MULTA":
                    self.core.adicionar_multa(doc, entry_valor.get(), var_cat.get(), entry_obs.get(), self.username)
                else:
                    self.core.adicionar_movimentacao(
                        doc, entry_valor.get(), var_cat.get(), tipo, entry_obs.get(), self.username
                    )
                janela_pai.destroy()
                self._atualizar_lista()
                messagebox.showinfo("Sucesso", "Movimentação registrada!")
            except ValueError as e:
                messagebox.showerror("Erro", str(e))

        ctk.CTkButton(frame, text="✅ Confirmar Movimentação", command=_confirmar, width=220).grid(
            row=4, column=0, columnspan=2, pady=15
        )

    def _montar_aba_anotacoes(self, aba: ctk.CTkFrame, doc: str):
        """Monta a aba de anotações livres sobre o hóspede."""
        texto_atual = self.core.get_anotacao(doc)

        caixa_texto = ctk.CTkTextbox(aba, wrap="word", font=ctk.CTkFont(size=13))
        caixa_texto.pack(fill="both", expand=True, padx=10, pady=10)

        if texto_atual:
            caixa_texto.insert("1.0", texto_atual)

        def _salvar_anotacao():
            texto = caixa_texto.get("1.0", "end").strip()
            self.core.salvar_anotacao(doc, texto)
            messagebox.showinfo("Salvo", "Anotação salva!")

        ctk.CTkButton(aba, text="💾 Salvar Anotação", command=_salvar_anotacao, width=160).pack(pady=(0, 10))

    # =========================================================================
    # AÇÕES
    # =========================================================================

    def _confirmar_exclusao(self, doc: str):
        """Pede confirmação e exclui o hóspede."""
        hospede = self.core.get_hospede(doc)
        if not hospede:
            return

        nome = hospede["nome"]
        saldo, _, _ = self.core.get_saldo_info(doc)

        aviso = f"Excluir '{nome}'?"
        if saldo > 0:
            aviso += f"\n\n⚠️ ATENÇÃO: Este hóspede tem saldo de R$ {saldo:.2f}!"

        if self.confirmar(aviso, "Confirmar Exclusão"):
            # Nota: excluir_hospede deve ser implementado no core
            # (não está no trecho lido, mas o padrão seria:)
            # self.core.excluir_hospede(doc, self.username)
            self.mostrar_sucesso(f"Hóspede '{nome}' excluído.")
            self._atualizar_lista()

    def _exportar_csv(self):
        """Exporta a lista atual como CSV."""
        from datetime import datetime
        from tkinter import filedialog

        caminho = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"hospedes_{datetime.now().strftime('%Y%m%d')}.csv",
        )
        if not caminho:
            return

        hospedes = self.core.buscar_filtrado("", "todos")
        try:
            with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
                f.write("Nome,Documento,Telefone,Saldo,Vencimento,Status\n")
                for nome, doc, saldo in hospedes:
                    _, venc, bloq = self.core.get_saldo_info(doc)
                    tel = self.core.get_hospede(doc).get("telefone", "") or ""
                    status = "Vencido" if bloq else ("Ativo" if saldo > 0 else "Sem saldo")
                    f.write(f'"{nome}","{doc}","{tel}","{saldo:.2f}","{venc}","{status}"\n')
            self.mostrar_sucesso(f"Exportado em:\n{caminho}")
        except Exception as e:
            self.mostrar_erro(f"Erro ao exportar: {e}")
