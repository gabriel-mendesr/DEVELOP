"""
Tela de Compras — Sistema Hotel Santos

RESPONSABILIDADE DESTA TELA:
  - Criar e gerenciar listas de compras
  - Adicionar itens às listas
  - Visualizar listas abertas e fechadas
  - Gerenciar produtos predefinidos (catálogo)
  - Calcular totais por lista

ESTRUTURA VISUAL:
  ┌──────────────────────────────────────────────────┐
  │  🛒 Compras                    [+ Nova Lista]    │
  ├──────────────────────────────────────────────────┤
  │  Listas:                                         │
  │  ┌──────────────────────────────────────────┐   │
  │  │ #1  Lista de Janeiro  Aberta  R$ 234,50  │   │  ← clique para abrir
  │  │ #2  Lista de Fevereiro  Aberta  R$ 89,00 │   │
  │  └──────────────────────────────────────────┘   │
  ├──────────────────────────────────────────────────┤
  │  [Adicionar Item] [Fechar Lista] [Produtos ⚙️]   │
  └──────────────────────────────────────────────────┘
"""

from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from .base import TelaBase


class TelaCompras(TelaBase):
    """
    Tela de gerenciamento de listas de compras.

    Estado interno desta tela:
        _lista_id_selecionada: ID da lista atualmente selecionada
                               (None = nenhuma lista selecionada)
    """

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()

        # Estado: qual lista está selecionada no momento
        self._lista_id_selecionada: int | None = None

        self.criar_titulo("🛒 Compras", "Listas de compras e controle de estoque")
        self._criar_layout_principal()

    # =========================================================================
    # LAYOUT PRINCIPAL
    # =========================================================================

    def _criar_layout_principal(self):
        """
        Cria o layout em dois painéis lado a lado:
          - Painel esquerdo: lista de todas as listas de compras
          - Painel direito: itens da lista selecionada

        CONCEITO: LAYOUT EM DOIS PAINÉIS
        Usamos pack com side="left" para colocar os frames lado a lado.
        O frame da direita tem expand=True para ocupar o espaço restante.
        """
        # Frame principal que contém os dois painéis
        frame_principal = ctk.CTkFrame(self.master, fg_color="transparent")
        frame_principal.pack(fill="both", expand=True, padx=15, pady=5)

        # === Painel Esquerdo: Listas ===
        frame_esq = ctk.CTkFrame(
            frame_principal, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), width=280, corner_radius=10
        )
        # fill="y" → ocupa toda a altura, mas não expande horizontalmente
        frame_esq.pack(side="left", fill="y", padx=(0, 10))
        frame_esq.pack_propagate(False)  # Mantém a largura fixa em 280px

        self._montar_painel_listas(frame_esq)

        # === Painel Direito: Itens da Lista ===
        self._frame_dir = ctk.CTkFrame(
            frame_principal, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10
        )
        # fill="both" + expand=True → ocupa todo o espaço restante
        self._frame_dir.pack(side="left", fill="both", expand=True)

        self._mostrar_painel_vazio()

    # =========================================================================
    # PAINEL ESQUERDO: LISTAS
    # =========================================================================

    def _montar_painel_listas(self, frame: ctk.CTkFrame):
        """Monta o painel com todas as listas de compras."""

        # Cabeçalho do painel
        frame_cab = ctk.CTkFrame(frame, fg_color="transparent")
        frame_cab.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(frame_cab, text="Listas", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")

        ctk.CTkButton(
            frame_cab, text="+ Nova", command=self._criar_nova_lista, width=70, height=28, font=ctk.CTkFont(size=12)
        ).pack(side="right")

        # Lista scrollável de listas de compras
        # Usamos CTkScrollableFrame para scroll automático
        self._frame_lista_listas = ctk.CTkScrollableFrame(frame, fg_color="transparent", label_text="")
        self._frame_lista_listas.pack(fill="both", expand=True, padx=5, pady=5)

        self._carregar_listas()

    def _carregar_listas(self):
        """Carrega e exibe todas as listas de compras."""
        # Limpa os botões anteriores
        for widget in self._frame_lista_listas.winfo_children():
            widget.destroy()

        listas = self.core.get_listas_resumo()

        if not listas:
            ctk.CTkLabel(
                self._frame_lista_listas,
                text="Nenhuma lista criada.\nClique em '+ Nova' para começar.",
                font=ctk.CTkFont(size=12),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
                justify="center",
            ).pack(pady=20)
            return

        for lista in listas:
            self._criar_card_lista(lista)

    def _criar_card_lista(self, lista: dict):
        """
        Cria um card clicável para uma lista de compras.

        CONCEITO: CLOSURES EM LOOPS
        Cuidado ao criar lambdas dentro de loops!
        O código abaixo NÃO funciona corretamente:
            command=lambda: self._selecionar_lista(lista['id'])  # ERRADO!
        Porque 'lista' mudará na próxima iteração, e todas as lambdas
        acabarão apontando para o último valor de 'lista'.

        A forma CORRETA é capturar o valor no momento da criação:
            command=lambda lid=lista['id']: self._selecionar_lista(lid)
        O parâmetro padrão 'lid=lista["id"]' captura o valor atual.
        """
        # Destaca a lista selecionada
        selecionada = lista.get("id") == self._lista_id_selecionada
        cor_fundo = "#1f6aa5" if selecionada else self.colors.get("bg_card", "#3a3a3a")

        card = ctk.CTkFrame(
            self._frame_lista_listas,
            fg_color=cor_fundo,
            corner_radius=8,
            cursor="hand2",  # Cursor de mãozinha (indica que é clicável)
        )
        card.pack(fill="x", padx=5, pady=3)

        # Linha 1: ID + status
        linha1 = ctk.CTkFrame(card, fg_color="transparent")
        linha1.pack(fill="x", padx=10, pady=(8, 2))

        status_emoji = "✅" if lista.get("status") == "FECHADA" else "📋"
        ctk.CTkLabel(
            linha1, text=f"{status_emoji} Lista #{lista.get('id')}", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        status_txt = lista.get("status", "ABERTA")
        cor_status = "#4caf50" if status_txt == "ABERTA" else "#aaaaaa"
        ctk.CTkLabel(linha1, text=status_txt, font=ctk.CTkFont(size=11), text_color=cor_status).pack(side="right")

        # Linha 2: Observação e data
        obs = lista.get("obs") or lista.get("data_criacao", "")
        if obs:
            ctk.CTkLabel(
                card, text=obs[:35], font=ctk.CTkFont(size=12), text_color=self.colors.get("text_secondary", "#aaaaaa")
            ).pack(anchor="w", padx=10)

        # Linha 3: Total da lista
        total = lista.get("total", 0.0) or 0.0
        total_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ctk.CTkLabel(
            card, text=f"Total: {total_fmt}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#4caf50"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Torna o card inteiro clicável
        # Capturamos lista['id'] no parâmetro padrão para evitar o problema de closures
        lista_id = lista.get("id")
        for widget in [card, linha1] + list(card.winfo_children()):
            widget.bind("<Button-1>", lambda e, lid=lista_id: self._selecionar_lista(lid))

    def _selecionar_lista(self, lista_id: int):
        """Seleciona uma lista e mostra seus itens no painel direito."""
        self._lista_id_selecionada = lista_id

        # Recarrega o painel de listas para atualizar o destaque visual
        self._carregar_listas()

        # Mostra os itens da lista selecionada no painel direito
        self._mostrar_itens_lista(lista_id)

    # =========================================================================
    # PAINEL DIREITO: ITENS DA LISTA
    # =========================================================================

    def _mostrar_painel_vazio(self):
        """Exibe mensagem quando nenhuma lista está selecionada."""
        for widget in self._frame_dir.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self._frame_dir,
            text="👈 Selecione uma lista para ver os itens",
            font=ctk.CTkFont(size=14),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _mostrar_itens_lista(self, lista_id: int):
        """Exibe os itens de uma lista no painel direito."""
        for widget in self._frame_dir.winfo_children():
            widget.destroy()

        # Cabeçalho com botões de ação
        frame_topo = ctk.CTkFrame(self._frame_dir, fg_color="transparent")
        frame_topo.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_topo, text=f"Lista #{lista_id}", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        # Botão de adicionar item
        ctk.CTkButton(
            frame_topo,
            text="+ Adicionar Item",
            command=lambda: self._abrir_form_item(lista_id),
            width=150,
            font=ctk.CTkFont(size=13),
        ).pack(side="right", padx=5)

        # Botão de fechar lista (só admin)
        if self.is_admin:
            ctk.CTkButton(
                frame_topo,
                text="🔒 Fechar Lista",
                command=lambda: self._fechar_lista(lista_id),
                width=140,
                fg_color="#4a4a4a",
                hover_color="#333333",
                font=ctk.CTkFont(size=13),
            ).pack(side="right", padx=5)

        # Tabela de itens
        colunas = [
            ("data_compra", 100),
            ("produto", 180),
            ("quantidade", 90),
            ("valor_unit", 110),
            ("valor_total", 110),
            ("usuario", 100),
        ]
        self._tree_itens, _ = self.criar_tabela(self._frame_dir, colunas)

        # Rodapé com total da lista
        self._frame_total = ctk.CTkFrame(
            self._frame_dir, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=8
        )
        self._frame_total.pack(fill="x", padx=10, pady=(5, 10))

        self._lbl_total_lista = ctk.CTkLabel(
            self._frame_total, text="Total: R$ 0,00", font=ctk.CTkFont(size=15, weight="bold"), text_color="#4caf50"
        )
        self._lbl_total_lista.pack(side="right", padx=20, pady=8)

        # Carrega os itens
        self._carregar_itens_lista(lista_id)

    def _carregar_itens_lista(self, lista_id: int):
        """Carrega os itens de uma lista na tabela."""
        for item in self._tree_itens.get_children():
            self._tree_itens.delete(item)

        itens = self.core.get_itens_lista(lista_id)
        total = 0.0

        for item in itens:
            vunit_fmt = f"R$ {item['valor_unitario']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            vtotal_fmt = f"R$ {item['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            self._tree_itens.insert(
                "",
                "end",
                iid=item["id"],
                values=(
                    item["data_compra"],
                    item["produto"],
                    item["quantidade"],
                    vunit_fmt,
                    vtotal_fmt,
                    item.get("usuario", ""),
                ),
            )
            total += item["valor_total"]

        # Atualiza total
        total_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self._lbl_total_lista.configure(text=f"Total da Lista: {total_fmt}")

    # =========================================================================
    # FORMULÁRIOS
    # =========================================================================

    def _criar_nova_lista(self):
        """Cria uma nova lista de compras."""
        janela = ctk.CTkToplevel(self.master)
        janela.title("Nova Lista de Compras")
        janela.geometry("350x180")
        janela.transient(self.master)
        janela.lift()
        janela.after(100, lambda: [janela.grab_set(), janela.focus_force()])

        frame = ctk.CTkFrame(janela)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Descrição:", anchor="w").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        entry_obs = ctk.CTkEntry(frame, placeholder_text="Ex: Compras de Março", width=200)
        entry_obs.grid(row=0, column=1, padx=10, pady=10)

        frame_btns = ctk.CTkFrame(janela, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(0, 15))

        def _confirmar():
            obs = entry_obs.get().strip()
            lista_id = self.core.criar_lista_compras(self.username, obs)
            janela.destroy()
            self._carregar_listas()
            self._selecionar_lista(lista_id)  # Já seleciona a nova lista

        ctk.CTkButton(frame_btns, text="✅ Criar Lista", command=_confirmar, width=130).pack(side="right", padx=5)
        ctk.CTkButton(
            frame_btns, text="Cancelar", command=janela.destroy, width=90, fg_color="#4a4a4a", hover_color="#333333"
        ).pack(side="right", padx=5)

    def _abrir_form_item(self, lista_id: int):
        """Janela para adicionar um item à lista."""
        janela = ctk.CTkToplevel(self.master)
        janela.title("Adicionar Item")
        janela.geometry("400x300")
        janela.transient(self.master)
        janela.lift()
        janela.after(100, lambda: [janela.grab_set(), janela.focus_force()])

        frame = ctk.CTkFrame(janela)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(1, weight=1)

        # Data
        ctk.CTkLabel(frame, text="Data:", anchor="w").grid(row=0, column=0, padx=10, pady=7, sticky="w")
        entry_data = ctk.CTkEntry(frame, width=200)
        entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        entry_data.grid(row=0, column=1, padx=10, pady=7)

        # Produto (com sugestões dos produtos predefinidos)
        ctk.CTkLabel(frame, text="Produto:", anchor="w").grid(row=1, column=0, padx=10, pady=7, sticky="w")

        # Busca produtos predefinidos para o combobox
        produtos = self.core.get_produtos_predefinidos()

        if produtos:
            var_produto = ctk.StringVar()
            # CTkComboBox = dropdown com opção de digitar livremente
            combo_produto = ctk.CTkComboBox(frame, variable=var_produto, values=produtos, width=200)
            combo_produto.grid(row=1, column=1, padx=10, pady=7)
            entry_produto = var_produto  # Atalho para ler o valor depois
        else:
            entry_prod = ctk.CTkEntry(frame, placeholder_text="Ex: Arroz 5kg", width=200)
            entry_prod.grid(row=1, column=1, padx=10, pady=7)
            entry_produto = entry_prod

        # Quantidade
        ctk.CTkLabel(frame, text="Quantidade:", anchor="w").grid(row=2, column=0, padx=10, pady=7, sticky="w")
        entry_qtd = ctk.CTkEntry(frame, placeholder_text="Ex: 2", width=200)
        entry_qtd.insert(0, "1")
        entry_qtd.grid(row=2, column=1, padx=10, pady=7)

        # Valor unitário
        ctk.CTkLabel(frame, text="Valor Unit. (R$):", anchor="w").grid(row=3, column=0, padx=10, pady=7, sticky="w")
        entry_valor = ctk.CTkEntry(frame, placeholder_text="Ex: 12,90", width=200)
        entry_valor.grid(row=3, column=1, padx=10, pady=7)

        frame_btns = ctk.CTkFrame(janela, fg_color="transparent")
        frame_btns.pack(fill="x", padx=20, pady=(0, 15))

        def _confirmar():
            produto = (entry_produto.get() if isinstance(entry_produto, ctk.StringVar) else entry_produto.get()).strip()
            if not produto:
                messagebox.showerror("Obrigatório", "Produto é obrigatório.", parent=janela)
                return
            try:
                self.core.adicionar_compra(
                    data_compra=entry_data.get().strip(),
                    produto=produto,
                    qtd=entry_qtd.get().strip(),
                    valor_unit=entry_valor.get().strip(),
                    lista_id=lista_id,
                    usuario=self.username,
                )
                janela.destroy()
                self._carregar_itens_lista(lista_id)
                self._carregar_listas()  # Atualiza total no painel esquerdo
            except (ValueError, Exception) as e:
                messagebox.showerror("Erro", str(e), parent=janela)

        ctk.CTkButton(frame_btns, text="✅ Adicionar", command=_confirmar, width=130).pack(side="right", padx=5)
        ctk.CTkButton(
            frame_btns, text="Cancelar", command=janela.destroy, width=90, fg_color="#4a4a4a", hover_color="#333333"
        ).pack(side="right", padx=5)

    def _fechar_lista(self, lista_id: int):
        """Marca uma lista como fechada (finalizada)."""
        if self.confirmar(f"Fechar a lista #{lista_id}?\nItens não poderão mais ser adicionados."):
            try:
                self.core.fechar_lista_compras(lista_id, self.username)
                self._carregar_listas()
                self._mostrar_painel_vazio()
                self._lista_id_selecionada = None
                messagebox.showinfo("Sucesso", "Lista fechada.")
            except Exception as e:
                self.mostrar_erro(str(e))
