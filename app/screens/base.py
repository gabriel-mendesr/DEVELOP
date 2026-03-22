"""
Tela Base — Sistema Hotel Santos

O QUE É UMA CLASSE BASE?
-------------------------
É uma classe que outras classes "herdam". Pense nisso como um formulário
padrão do hotel: todas as telas têm as mesmas seções iniciais
(cabeçalho, rodapé), mas cada uma preenche o meio de forma diferente.

Em Python, herança funciona assim:
    class TelaHospedes(TelaBase):  # ← TelaHospedes "é um tipo de" TelaBase
        ...

Com isso, TelaHospedes ganha AUTOMATICAMENTE todos os métodos de TelaBase.
Não precisamos reescrever o mesmo código em cada tela.

O QUE VAI NESTA CLASSE BASE?
- Método para mostrar mensagens de erro/sucesso
- Método para criar campos de formulário padronizados
- Método para criar tabelas (Treeview) padronizadas
- Limpeza de frame ao trocar de tela
- Referências ao core e ao usuário logado

O QUE NÃO VAI AQUI:
- Lógica de negócio (isso fica no core/models.py)
- Widgets específicos de cada tela
"""

from collections.abc import Callable
from tkinter import messagebox, ttk

import customtkinter as ctk


class TelaBase:
    """
    Classe base para todas as telas do sistema.

    COMO USAR:
        class MinhaTelaFilha(TelaBase):
            def __init__(self, master, core, usuario, colors):
                super().__init__(master, core, usuario, colors)
                # Seus widgets aqui
                self._montar_tela()

            def _montar_tela(self):
                # Construção da tela específica
                ...

    ATRIBUTOS DISPONÍVEIS PARA AS CLASSES FILHAS:
        self.master   → frame pai (onde renderizar os widgets)
        self.core     → SistemaCreditos (toda a lógica de negócio)
        self.usuario  → dict com dados do usuário logado
        self.colors   → dict com as cores do tema atual
        self.is_admin → bool: True se o usuário logado é admin
    """

    def __init__(self, master: ctk.CTkFrame, core, usuario: dict, colors: dict):
        """
        Args:
            master:  Frame pai onde a tela será renderizada.
            core:    Instância de SistemaCreditos (models.py).
            usuario: Dict com dados do usuário logado (username, is_admin...).
            colors:  Dict de cores do tema atual.
        """
        self.master = master
        self.core = core
        self.usuario = usuario
        self.colors = colors

        # Atalhos úteis
        self.username = usuario.get("username", "Sistema")
        self.is_admin = bool(usuario.get("is_admin", 0))

    # =========================================================================
    # UTILITÁRIOS DE INTERFACE — usados pelas telas filhas
    # =========================================================================

    def limpar_master(self):
        """
        Remove todos os widgets do frame pai.

        Por que isso é necessário?
        Quando o usuário troca de tela (ex: de Hóspedes para Financeiro),
        precisamos apagar os widgets da tela anterior antes de mostrar a nova.
        """
        for widget in self.master.winfo_children():
            widget.destroy()

    def mostrar_erro(self, mensagem: str, titulo: str = "Erro"):
        """Exibe um popup de erro padronizado."""
        messagebox.showerror(titulo, mensagem)

    def mostrar_sucesso(self, mensagem: str, titulo: str = "Sucesso"):
        """Exibe um popup de sucesso padronizado."""
        messagebox.showinfo(titulo, mensagem)

    def confirmar(self, mensagem: str, titulo: str = "Confirmar") -> bool:
        """
        Exibe um popup de confirmação (Sim/Não).

        Retorna:
            True se o usuário clicou em "Sim", False caso contrário.

        Uso típico:
            if self.confirmar("Deseja excluir este hóspede?"):
                self.core.excluir_hospede(doc)
        """
        return messagebox.askyesno(titulo, mensagem)

    def criar_campo_label(
        self, parent: ctk.CTkFrame, texto: str, row: int, col: int = 0, pady: int = 5
    ) -> ctk.CTkLabel:
        """
        Cria um label de formulário padronizado.

        Uso típico:
            self.criar_campo_label(frame, "Nome:", row=0)
            self.entry_nome = ctk.CTkEntry(frame)
            self.entry_nome.grid(row=0, column=1, padx=5, pady=5)
        """
        label = ctk.CTkLabel(parent, text=texto, anchor="w", font=ctk.CTkFont(size=13))
        label.grid(row=row, column=col, padx=(10, 5), pady=pady, sticky="w")
        return label

    def criar_entry(
        self, parent: ctk.CTkFrame, placeholder: str = "", width: int = 220, row: int = 0, col: int = 1, pady: int = 5
    ) -> ctk.CTkEntry:
        """
        Cria um campo de texto padronizado.

        Combina com criar_campo_label para montar formulários rapidamente.
        """
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, width=width, font=ctk.CTkFont(size=13))
        entry.grid(row=row, column=col, padx=(5, 10), pady=pady, sticky="ew")
        return entry

    def criar_tabela(
        self, parent: ctk.CTkFrame, colunas: list[tuple[str, int]], altura: int = 400
    ) -> tuple[ttk.Treeview, ttk.Scrollbar]:
        """
        Cria uma tabela (Treeview) com scrollbar padronizada.

        Args:
            parent:  Frame pai onde a tabela será inserida.
            colunas: Lista de tuplas (id_coluna, largura_em_pixels).
                     A primeira coluna também é o cabeçalho (capitalized).
                     Ex: [("nome", 200), ("documento", 150), ("saldo", 100)]
            altura:  Altura em pixels da tabela.

        Retorna:
            (tree, scrollbar) — guarde o tree para inserir/ler dados depois.

        Exemplo de uso:
            tree, _ = self.criar_tabela(
                frame,
                colunas=[("nome", 250), ("documento", 150), ("saldo", 100)]
            )
            # Inserir linha:
            tree.insert("", "end", values=("João Silva", "123.456.789-00", "500,00"))
            # Ler linha selecionada:
            item = tree.selection()
            if item:
                valores = tree.item(item[0])['values']
        """
        # Frame contentor (para colocar tree + scrollbar lado a lado)
        frame_tabela = ctk.CTkFrame(parent, fg_color="transparent")
        frame_tabela.pack(fill="both", expand=True, padx=10, pady=5)

        # Configura estilo da tabela (para combinar com o tema)
        style = ttk.Style()
        bg = self.colors.get("bg_secondary", "#2b2b2b")
        fg = self.colors.get("text", "#ffffff")
        sel = self.colors.get("accent", "#1f6aa5")

        style.configure(
            "Hotel.Treeview",
            background=bg,
            foreground=fg,
            rowheight=28,
            fieldbackground=bg,
            borderwidth=0,
            font=("Segoe UI", 12),
        )
        style.configure(
            "Hotel.Treeview.Heading", background=sel, foreground="white", relief="flat", font=("Segoe UI", 12, "bold")
        )
        style.map("Hotel.Treeview", background=[("selected", sel)])

        # Extrai apenas os IDs das colunas
        ids_colunas = [col[0] for col in colunas]

        # Cria o Treeview
        tree = ttk.Treeview(frame_tabela, columns=ids_colunas, show="headings", style="Hotel.Treeview")

        # Configura cada coluna
        for col_id, largura in colunas:
            # O cabeçalho é o ID com a primeira letra maiúscula
            # "nome" → "Nome", "valor_total" → "Valor_total"
            cabecalho = col_id.replace("_", " ").title()
            tree.heading(col_id, text=cabecalho)
            tree.column(col_id, width=largura, minwidth=50)

        # Scrollbar vertical
        scrollbar = ttk.Scrollbar(frame_tabela, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Posiciona tabela e scrollbar
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return tree, scrollbar

    def criar_btn(
        self,
        parent,
        texto: str,
        comando: Callable,
        cor: str = "blue",
        largura: int = 140,
        linha: int = 0,
        coluna: int = 0,
        padx: int = 5,
        pady: int = 5,
    ) -> ctk.CTkButton:
        """
        Cria um botão padronizado.

        Args:
            cor: "blue" (padrão), "green" (confirmar), "red" (excluir),
                 "gray" (cancelar/neutro)
        """
        # Mapeamento de cor semântica → cor real
        cores_map = {
            "blue": ("#1f6aa5", "#144870"),
            "green": ("#2e7d32", "#1b5e20"),
            "red": ("#c62828", "#8e0000"),
            "gray": ("#4a4a4a", "#333333"),
        }
        fg, hover = cores_map.get(cor, cores_map["blue"])

        btn = ctk.CTkButton(
            parent,
            text=texto,
            command=comando,
            width=largura,
            fg_color=fg,
            hover_color=hover,
            font=ctk.CTkFont(size=13),
        )
        btn.grid(row=linha, column=coluna, padx=padx, pady=pady, sticky="ew")
        return btn

    def criar_titulo(self, texto: str, subtitulo: str = "") -> ctk.CTkFrame:
        """
        Cria o cabeçalho padrão da tela com título e subtítulo opcional.

        Retorna o frame do cabeçalho (caso precise referenciar depois).
        """
        frame_header = ctk.CTkFrame(self.master, fg_color=self.colors.get("bg_secondary", "#2b2b2b"), corner_radius=10)
        frame_header.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            frame_header,
            text=texto,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.colors.get("accent", "#1f6aa5"),
        ).pack(side="left", padx=15, pady=10)

        if subtitulo:
            ctk.CTkLabel(
                frame_header,
                text=subtitulo,
                font=ctk.CTkFont(size=13),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
            ).pack(side="left", padx=5)

        return frame_header

    def formatar_moeda(self, valor: float) -> str:
        """
        Formata um float como moeda brasileira.

        Exemplos:
            1500.5  → "R$ 1.500,50"
            0.0     → "R$ 0,00"
        """
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
