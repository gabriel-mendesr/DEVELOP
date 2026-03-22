"""
Tela Financeiro — Sistema Hotel Santos

RESPONSABILIDADE DESTA TELA:
  - Histórico global de movimentações (todos os hóspedes)
  - Lista de hóspedes com multas pendentes
  - Registrar pagamento de multa
  - Filtrar histórico por tipo, data ou hóspede

ESTRUTURA VISUAL:
  ┌─────────────────────────────────────────────────┐
  │  💰 Financeiro                                   │
  ├─────────────────────────────────────────────────┤
  │  [Histórico Global] [Multas Pendentes]           │
  ├─────────────────────────────────────────────────┤
  │  Buscar: [_______]  Tipo: [Todos ▼]  [Filtrar]  │
  ├─────────────────────────────────────────────────┤
  │  Data    │ Hóspede  │ Tipo  │ Valor  │ Categoria │
  │  ...     │ ...      │ ...   │ ...    │ ...       │
  └─────────────────────────────────────────────────┘
"""

from tkinter import messagebox

import customtkinter as ctk

from .base import TelaBase


class TelaFinanceiro(TelaBase):
    """
    Tela de relatórios e controle financeiro.

    Diferente da TelaHospedes (que foca num hóspede por vez),
    esta tela mostra o financeiro GLOBAL do hotel.
    """

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()

        self.criar_titulo("💰 Financeiro", "Histórico global e controle de multas")
        self._criar_abas()

    # =========================================================================
    # ABAS PRINCIPAIS
    # =========================================================================

    def _criar_abas(self):
        """
        Cria as abas da tela usando CTkTabview.

        CTkTabview é como um caderno com abas — cada aba é um frame separado.
        """
        abas = ctk.CTkTabview(self.master)
        abas.pack(fill="both", expand=True, padx=15, pady=10)

        # Aba 1: Histórico Global
        aba_hist = abas.add("📜 Histórico Global")
        self._montar_aba_historico(aba_hist)

        # Aba 2: Multas Pendentes
        aba_multas = abas.add("⚠️ Multas Pendentes")
        self._montar_aba_multas(aba_multas)

        # Aba 3: Resumo do Período
        aba_resumo = abas.add("📊 Resumo")
        self._montar_aba_resumo(aba_resumo)

    # =========================================================================
    # ABA 1: HISTÓRICO GLOBAL
    # =========================================================================

    def _montar_aba_historico(self, aba: ctk.CTkFrame):
        """Monta a aba com histórico de todas as movimentações."""

        # --- Barra de filtros ---
        frame_filtros = ctk.CTkFrame(aba, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=8)
        frame_filtros.pack(fill="x", padx=5, pady=(5, 10))

        # Busca por nome
        ctk.CTkLabel(frame_filtros, text="🔍", font=ctk.CTkFont(size=14)).pack(side="left", padx=(10, 2), pady=8)
        self._var_busca_fin = ctk.StringVar()
        ctk.CTkEntry(
            frame_filtros,
            textvariable=self._var_busca_fin,
            placeholder_text="Buscar por hóspede...",
            width=220,
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=5, pady=8)

        # Filtro de tipo
        ctk.CTkLabel(frame_filtros, text="Tipo:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(15, 5))
        self._var_tipo_hist = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(
            frame_filtros,
            variable=self._var_tipo_hist,
            values=["Todos", "ENTRADA", "SAIDA", "MULTA", "PAGAMENTO_MULTA"],
            width=160,
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=5, pady=8)

        # Botão de filtrar
        ctk.CTkButton(
            frame_filtros, text="Filtrar", command=self._filtrar_historico, width=90, font=ctk.CTkFont(size=13)
        ).pack(side="left", padx=10)

        # Contador
        self._lbl_contador_fin = ctk.CTkLabel(
            frame_filtros, text="", font=ctk.CTkFont(size=12), text_color=self.colors.get("text_secondary", "#aaaaaa")
        )
        self._lbl_contador_fin.pack(side="right", padx=15)

        # --- Tabela ---
        colunas = [
            ("data_acao", 100),
            ("nome", 200),
            ("documento", 140),
            ("tipo", 90),
            ("valor", 110),
            ("categoria", 130),
            ("usuario", 100),
        ]
        self._tree_hist, _ = self.criar_tabela(aba, colunas)

        # Salva referência ao frame da aba para poder recarregar
        self._aba_hist = aba

        # Carrega dados ao montar
        self._filtrar_historico()

    def _filtrar_historico(self):
        """Aplica os filtros e atualiza a tabela de histórico."""
        for item in self._tree_hist.get_children():
            self._tree_hist.delete(item)

        filtro_texto = self._var_busca_fin.get().strip()
        filtro_tipo = self._var_tipo_hist.get()

        # Monta o tuple de tipos para o core
        if filtro_tipo == "Todos":
            tipos = None  # None = sem filtro de tipo
        else:
            tipos = (filtro_tipo,)

        # Busca no core
        historico = self.core.get_historico_global(filtro=filtro_texto, limite=200, tipos=tipos)

        # Preenche a tabela
        for mov in historico:
            valor_fmt = f"R$ {mov['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # Coloração por tipo (via tag)
            tag = {"ENTRADA": "entrada", "SAIDA": "saida", "MULTA": "multa", "PAGAMENTO_MULTA": "pagamento"}.get(
                mov["tipo"], ""
            )

            self._tree_hist.insert(
                "",
                "end",
                values=(
                    mov["data_acao"],
                    mov["nome"],
                    mov["documento"],
                    mov["tipo"],
                    valor_fmt,
                    mov.get("categoria", ""),
                    mov.get("usuario", ""),
                ),
                tags=(tag,),
            )

        # Configura as cores das tags
        self._tree_hist.tag_configure("entrada", foreground="#4caf50")
        self._tree_hist.tag_configure("saida", foreground="#ef5350")
        self._tree_hist.tag_configure("multa", foreground="#ff9800")
        self._tree_hist.tag_configure("pagamento", foreground="#29b6f6")

        # Atualiza contador
        self._lbl_contador_fin.configure(text=f"{len(historico)} registro(s)")

    # =========================================================================
    # ABA 2: MULTAS PENDENTES
    # =========================================================================

    def _montar_aba_multas(self, aba: ctk.CTkFrame):
        """Monta a aba de hóspedes com multas pendentes."""

        # Botão de recarregar
        ctk.CTkButton(
            aba,
            text="🔄 Recarregar",
            command=lambda: self._carregar_multas(),
            width=140,
            fg_color="#4a4a4a",
            hover_color="#333333",
            font=ctk.CTkFont(size=13),
        ).pack(anchor="e", padx=10, pady=(10, 5))

        # Tabela de devedores
        colunas = [
            ("nome", 250),
            ("documento", 160),
            ("telefone", 130),
            ("divida", 120),
        ]
        self._tree_multas, _ = self.criar_tabela(aba, colunas)

        # Duplo clique → registrar pagamento
        self._tree_multas.bind("<Double-1>", self._ao_clicar_multa)

        # Instrução
        ctk.CTkLabel(
            aba,
            text="💡 Dê duplo-clique num hóspede para registrar pagamento de multa.",
            font=ctk.CTkFont(size=12),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).pack(pady=(5, 0))

        # Salva referência para recarregar
        self._aba_multas_frame = aba
        self._carregar_multas()

    def _carregar_multas(self):
        """Carrega a lista de devedores de multas."""
        for item in self._tree_multas.get_children():
            self._tree_multas.delete(item)

        devedores = self.core.get_devedores_multas()
        for nome, doc, tel, divida in devedores:
            divida_fmt = f"R$ {divida:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            self._tree_multas.insert("", "end", iid=doc, values=(nome, doc, tel or "", divida_fmt))

    def _ao_clicar_multa(self, event):
        """Abre janela de pagamento ao dar duplo-clique numa multa."""
        item = self._tree_multas.selection()
        if not item:
            return
        doc = item[0]
        hospede = self.core.get_hospede(doc)
        divida = self.core.get_divida_multas(doc)
        self._abrir_form_pagamento_multa(doc, hospede["nome"], divida)

    def _abrir_form_pagamento_multa(self, doc: str, nome: str, divida: float):
        """Janela modal para registrar pagamento de multa."""
        janela = ctk.CTkToplevel(self.master)
        janela.title(f"Pagar Multa — {nome}")
        janela.geometry("380x260")
        janela.grab_set()

        divida_fmt = f"R$ {divida:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        frame = ctk.CTkFrame(janela)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Hóspede:", anchor="w").grid(row=0, column=0, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(frame, text=nome, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=10, pady=6, sticky="w"
        )

        ctk.CTkLabel(frame, text="Dívida total:", anchor="w").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(frame, text=divida_fmt, text_color="#ff9800", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=1, padx=10, pady=6, sticky="w"
        )

        ctk.CTkLabel(frame, text="Valor a pagar:", anchor="w").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        entry_valor = ctk.CTkEntry(frame, placeholder_text="Ex: 50,00", width=180)
        entry_valor.grid(row=2, column=1, padx=10, pady=6)

        ctk.CTkLabel(frame, text="Forma pagamento:", anchor="w").grid(row=3, column=0, padx=10, pady=6, sticky="w")
        var_forma = ctk.StringVar(value="Dinheiro")
        ctk.CTkOptionMenu(
            frame, variable=var_forma, values=["Dinheiro", "PIX", "Cartão", "Transferência"], width=180
        ).grid(row=3, column=1, padx=10, pady=6)

        frame_btns = ctk.CTkFrame(janela, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(0, 15))

        def _pagar():
            try:
                self.core.pagar_multa(doc, entry_valor.get(), var_forma.get(), "", self.username)
                janela.destroy()
                self._carregar_multas()
                messagebox.showinfo("Sucesso", "Pagamento registrado!")
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=janela)

        ctk.CTkButton(frame_btns, text="✅ Confirmar Pagamento", command=_pagar, width=190).pack(side="right", padx=5)
        ctk.CTkButton(
            frame_btns, text="Cancelar", command=janela.destroy, width=90, fg_color="#4a4a4a", hover_color="#333333"
        ).pack(side="right", padx=5)

    # =========================================================================
    # ABA 3: RESUMO DO PERÍODO
    # =========================================================================

    def _montar_aba_resumo(self, aba: ctk.CTkFrame):
        """
        Monta cards de resumo financeiro.

        Usa os dados do get_dados_dash() do core para mostrar
        totalizadores em formato de "cards".
        """
        # Busca dados do core
        total_saldo, total_vencido, a_vencer, n_hospedes, total_multas = self.core.get_dados_dash()

        # Grid de 2 colunas de cards
        frame_cards = ctk.CTkFrame(aba, fg_color="transparent")
        frame_cards.pack(padx=20, pady=20)

        dados_cards = [
            ("💰 Saldo Total em Circulação", total_saldo, "#1f6aa5"),
            ("⛔ Total Vencido", total_vencido, "#c62828"),
            ("⏳ A Vencer em Breve", a_vencer, "#ff9800"),
            ("⚠️ Total de Multas", total_multas, "#e65100"),
            ("👥 Total de Hóspedes", n_hospedes, "#2e7d32"),
        ]

        for i, (titulo, valor, cor) in enumerate(dados_cards):
            linha = i // 2
            coluna = i % 2

            card = ctk.CTkFrame(
                frame_cards,
                fg_color=self.colors.get("bg_secondary", "#2b2b2b"),
                corner_radius=12,
                width=280,
                height=100,
            )
            card.grid(row=linha, column=coluna, padx=10, pady=10, sticky="ew")
            card.grid_propagate(False)

            ctk.CTkLabel(
                card, text=titulo, font=ctk.CTkFont(size=13), text_color=self.colors.get("text_secondary", "#aaaaaa")
            ).pack(padx=15, pady=(15, 0), anchor="w")

            # Formata número: se for float, usa moeda; se for int, usa inteiro
            if isinstance(valor, float):
                val_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_fmt = str(valor)

            ctk.CTkLabel(card, text=val_fmt, font=ctk.CTkFont(size=22, weight="bold"), text_color=cor).pack(
                padx=15, pady=(0, 15), anchor="w"
            )
