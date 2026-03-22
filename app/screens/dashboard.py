"""
Tela Dashboard — Sistema Hotel Santos

RESPONSABILIDADE DESTA TELA:
  - Visão geral do hotel em tempo real
  - Cards com totalizadores (saldo, vencidos, multas...)
  - Gráfico de movimentações dos últimos 6 meses
  - Gráfico de distribuição por categoria
  - Lista de hóspedes com crédito vencendo em breve

SOBRE MATPLOTLIB COM TKINTER:
  Matplotlib é uma biblioteca de gráficos Python.
  Para integrar com tkinter/customtkinter, usamos:
  1. FigureCanvasTkAgg: "encapsula" o gráfico matplotlib num widget tkinter
  2. Figure: a "tela" do matplotlib onde desenhamos os gráficos

  Fluxo:
    fig = Figure(figsize=(7, 3))     # Cria o "papel"
    ax = fig.add_subplot(111)        # Adiciona um eixo (área de plot)
    ax.bar(x, y)                     # Desenha o gráfico
    canvas = FigureCanvasTkAgg(fig, master=frame)  # Integra com tkinter
    canvas.get_tk_widget().pack()    # Exibe na tela
"""

from tkinter import ttk

import customtkinter as ctk

from .base import TelaBase


class TelaDashboard(TelaBase):
    """
    Tela de dashboard com visão geral do hotel.
    """

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()

        self.criar_titulo("📊 Dashboard", "Visão geral do sistema")

        # Área scrollável (o dashboard pode ser alto)
        scroll = ctk.CTkScrollableFrame(self.master, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        # Monta as seções na ordem
        self._criar_cards_resumo(scroll)
        self._criar_secao_graficos(scroll)
        self._criar_tabela_alertas(scroll)

    # =========================================================================
    # SEÇÃO 1: CARDS DE RESUMO
    # =========================================================================

    def _criar_cards_resumo(self, parent: ctk.CTkScrollableFrame):
        """
        Cria os cards de totalizadores no topo do dashboard.

        Os cards são dispostos em grade (2 linhas × 3 colunas).
        Cada card mostra um indicador-chave do hotel.
        """
        # Busca todos os dados de uma vez (1 consulta ao banco)
        total_saldo, total_vencido, a_vencer, n_hospedes, total_multas = self.core.get_dados_dash()

        # Configuração dos cards: (emoji + título, valor, cor)
        cards = [
            ("💰  Saldo em Circulação", total_saldo, True, "#1f6aa5"),
            ("⛔  Crédito Vencido", total_vencido, True, "#c62828"),
            ("⏳  A Vencer em Breve", a_vencer, True, "#e65100"),
            ("👥  Total de Hóspedes", n_hospedes, False, "#2e7d32"),
            ("⚠️  Total em Multas", total_multas, True, "#7b1fa2"),
        ]

        # Frame grade para os cards
        frame_cards = ctk.CTkFrame(parent, fg_color="transparent")
        frame_cards.pack(fill="x", pady=(10, 5))

        # Configura colunas para serem iguais e expansíveis
        for col in range(3):
            frame_cards.columnconfigure(col, weight=1)

        for i, (titulo, valor, e_moeda, cor) in enumerate(cards):
            linha = i // 3  # Divisão inteira: 0//3=0, 1//3=0, 3//3=1...
            coluna = i % 3  # Resto: 0%3=0, 1%3=1, 2%3=2, 3%3=0...

            self._criar_card(frame_cards, titulo, valor, e_moeda, cor, linha, coluna)

    def _criar_card(self, parent, titulo: str, valor, e_moeda: bool, cor: str, linha: int, coluna: int):
        """
        Cria um único card de indicador.

        Args:
            e_moeda: Se True, formata como R$ 1.234,56; se False, mostra o número puro.
        """
        card = ctk.CTkFrame(parent, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=12)
        card.grid(row=linha, column=coluna, padx=8, pady=6, sticky="ew")

        # Título do card (cinza, menor)
        ctk.CTkLabel(
            card,
            text=titulo,
            font=ctk.CTkFont(size=12),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
            anchor="w",
        ).pack(padx=15, pady=(15, 3), anchor="w")

        # Valor principal (colorido, grande)
        if e_moeda:
            valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            valor_fmt = str(int(valor))

        ctk.CTkLabel(card, text=valor_fmt, font=ctk.CTkFont(size=24, weight="bold"), text_color=cor, anchor="w").pack(
            padx=15, pady=(0, 15), anchor="w"
        )

    # =========================================================================
    # SEÇÃO 2: GRÁFICOS
    # =========================================================================

    def _criar_secao_graficos(self, parent: ctk.CTkScrollableFrame):
        """
        Cria a seção com dois gráficos lado a lado.

        Usamos um try/except aqui porque matplotlib pode não estar
        instalado em todos os ambientes. Se não estiver, mostramos
        um aviso amigável em vez de travar o app.
        """
        try:
            import matplotlib

            matplotlib.use("TkAgg")  # Backend para integração com Tkinter
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            ctk.CTkLabel(
                parent,
                text="⚠️ Matplotlib não instalado. Gráficos indisponíveis.\nInstale com: pip install matplotlib",
                font=ctk.CTkFont(size=13),
                text_color="#ff9800",
            ).pack(pady=20)
            return

        # Frame que contém os dois gráficos
        frame_graficos = ctk.CTkFrame(parent, fg_color="transparent")
        frame_graficos.pack(fill="x", pady=10)
        frame_graficos.columnconfigure(0, weight=3)  # Gráfico mensal (maior)
        frame_graficos.columnconfigure(1, weight=2)  # Gráfico categorias (menor)

        # Cores do tema (para o matplotlib combinar com o app)
        bg_color = self.colors.get("bg_secondary", "#2b2b2b")
        text_color = self.colors.get("text", "#ffffff")

        # === Gráfico 1: Movimentações Mensais (barras) ===
        frame_g1 = ctk.CTkFrame(frame_graficos, fg_color=bg_color, corner_radius=10)
        frame_g1.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")

        ctk.CTkLabel(
            frame_g1, text="Movimentações Mensais (últimos 6 meses)", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(10, 0))

        self._plotar_grafico_mensal(frame_g1, FigureCanvasTkAgg, Figure, bg_color, text_color)

        # === Gráfico 2: Distribuição por Categoria (pizza) ===
        frame_g2 = ctk.CTkFrame(frame_graficos, fg_color=bg_color, corner_radius=10)
        frame_g2.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")

        ctk.CTkLabel(frame_g2, text="Entradas por Categoria", font=ctk.CTkFont(size=13, weight="bold")).pack(
            pady=(10, 0)
        )

        self._plotar_grafico_categorias(frame_g2, FigureCanvasTkAgg, Figure, bg_color, text_color)

    def _plotar_grafico_mensal(self, frame, FigureCanvasTkAgg, Figure, bg, fg):
        """Plota o gráfico de barras de movimentações mensais."""
        meses, entradas, saidas = self.core.get_dados_grafico_mensal()

        # Cria a figura matplotlib
        fig = Figure(figsize=(6, 3), dpi=90, facecolor=bg)
        ax = fig.add_subplot(111, facecolor=bg)

        # Posições no eixo X
        x = list(range(len(meses)))
        largura = 0.35  # Largura das barras

        # Barras de entradas e saídas lado a lado
        ax.bar([i - largura / 2 for i in x], entradas, width=largura, label="Entradas", color="#4caf50", alpha=0.85)
        ax.bar([i + largura / 2 for i in x], saidas, width=largura, label="Saídas", color="#ef5350", alpha=0.85)

        # Configurações visuais
        ax.set_xticks(x)
        ax.set_xticklabels(meses, color=fg, fontsize=9)
        ax.tick_params(colors=fg, labelsize=9)
        ax.legend(facecolor=bg, labelcolor=fg, fontsize=9)
        ax.spines["bottom"].set_color("#555555")
        ax.spines["left"].set_color("#555555")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.set_tick_params(labelcolor=fg)
        fig.tight_layout()

        # Integra com tkinter
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(5, 10))

    def _plotar_grafico_categorias(self, frame, FigureCanvasTkAgg, Figure, bg, fg):
        """Plota o gráfico de pizza de distribuição por categoria."""
        dados = self.core.get_dados_grafico_categorias()

        if not dados:
            ctk.CTkLabel(frame, text="Sem dados ainda", text_color="#888888").pack(pady=30)
            return

        labels = [d[0] for d in dados]
        valores = [d[1] for d in dados]

        # Paleta de cores para as fatias
        cores = ["#1f6aa5", "#4caf50", "#ff9800", "#e91e63", "#9c27b0", "#00bcd4", "#8bc34a", "#ff5722"]

        fig = Figure(figsize=(4, 3), dpi=90, facecolor=bg)
        ax = fig.add_subplot(111, facecolor=bg)

        wedges, texts, autotexts = ax.pie(
            valores,
            labels=labels,
            autopct="%1.0f%%",
            colors=cores[: len(labels)],
            textprops={"color": fg, "fontsize": 9},
            startangle=90,
        )

        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(8)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # =========================================================================
    # SEÇÃO 3: ALERTAS DE VENCIMENTO
    # =========================================================================

    def _criar_tabela_alertas(self, parent: ctk.CTkScrollableFrame):
        """
        Cria a tabela de hóspedes com crédito vencendo em breve.

        Usa o get_hospedes_vencendo_em_breve() do core, que já
        filtra baseado na config 'alerta_dias'.
        """
        # Cabeçalho da seção
        frame_cab = ctk.CTkFrame(parent, fg_color="transparent")
        frame_cab.pack(fill="x", pady=(10, 5))

        alerta_dias = self.core.get_config("alerta_dias")

        ctk.CTkLabel(
            frame_cab,
            text=f"⏳ Créditos Vencendo em {alerta_dias} dias",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ff9800",
        ).pack(side="left")

        # Busca hóspedes em alerta
        hospedes_alerta = self.core.get_hospedes_vencendo_em_breve()

        if not hospedes_alerta:
            ctk.CTkLabel(
                parent, text="✅ Nenhum crédito vencendo em breve.", font=ctk.CTkFont(size=13), text_color="#4caf50"
            ).pack(pady=10, anchor="w")
            return

        # Frame da tabela
        frame_tabela = ctk.CTkFrame(parent, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_tabela.pack(fill="x", pady=(5, 15))

        # Cria manualmente (tabela simples, sem scroll)
        # Cabeçalho
        frame_header = ctk.CTkFrame(frame_tabela, fg_color="#1f6aa5", corner_radius=0)
        frame_header.pack(fill="x", padx=0, pady=0)

        for col_txt, col_w in [("Nome", 300), ("Vencimento", 120), ("Saldo", 120)]:
            ctk.CTkLabel(frame_header, text=col_txt, font=ctk.CTkFont(size=13, weight="bold"), width=col_w).pack(
                side="left", padx=10, pady=6
            )

        # Linhas
        for nome, venc, saldo in hospedes_alerta:
            linha = ctk.CTkFrame(frame_tabela, fg_color="transparent")
            linha.pack(fill="x", padx=0)

            saldo_fmt = f"R$ {float(saldo):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            ctk.CTkLabel(linha, text=nome, width=300, anchor="w", font=ctk.CTkFont(size=12)).pack(
                side="left", padx=10, pady=5
            )
            ctk.CTkLabel(linha, text=venc, width=120, anchor="w", font=ctk.CTkFont(size=12), text_color="#ff9800").pack(
                side="left", padx=10
            )
            ctk.CTkLabel(linha, text=saldo_fmt, width=120, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(
                side="left", padx=10
            )

            # Separador entre linhas
            ttk.Separator(frame_tabela, orient="horizontal").pack(fill="x", padx=10)
