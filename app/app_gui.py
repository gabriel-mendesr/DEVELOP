import sys
import os

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, Listbox, StringVar
from sistema_clientes import SistemaCreditos
from datetime import datetime
import webbrowser
from urllib.parse import quote
import threading
import traceback

from update_manager import UpdateManager
try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None

def resource_path(relative_path: str) -> str:
    """ Obtém o caminho absoluto para recursos, funcionando para dev e PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class AppHotelLTS(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # --- Declaração de Atributos de Instância para Type Hinting ---
        self.core: SistemaCreditos
        self.update_manager: UpdateManager
        self.colors: dict[str, str]
        self.current_user: dict | None = None
        self.search_job: str | None = None
        self.current_screen_function: callable | None = None
        self.current_screen_args: tuple = ()
        self.current_screen_kwargs: dict = {}

        # Widgets da UI principal
        self.sidebar: ctk.CTkFrame
        self.main_frame: ctk.CTkFrame
        self.btn_update: ctk.CTkButton
        self.btn_sair: ctk.CTkButton

        # Widgets da tela de Hóspedes
        self.ent_busca: ctk.CTkEntry
        self.tree_h: ttk.Treeview
        self.menu_hospede: ctk.CTkFrame

        # Widgets da tela de Histórico
        self.tree_z: ttk.Treeview

        # Widgets da tela Financeiro
        self.ent_busca_lanc: ctk.CTkEntry
        self.tree_l: ttk.Treeview
        self.menu_lanc: ctk.CTkFrame

        # Widgets da tela de Compras
        self.tree_listas: ttk.Treeview
        self.frame_detalhes: ctk.CTkFrame
        self.lbl_titulo_lista: ctk.CTkLabel
        self.frame_acoes_lista: ctk.CTkFrame
        self.btn_fechar_lista: ctk.CTkButton
        self.btn_imprimir_lista: ctk.CTkButton
        self.frame_add_item: ctk.CTkFrame
        self.lista_produtos_cache: list[str] = []
        self.e_prod_compras: ctk.CTkEntry
        self.lb_sugestoes: Listbox
        self.e_qtd_compras: ctk.CTkEntry
        self.e_val_compras: ctk.CTkEntry
        self.tree_itens: ttk.Treeview
        self.lista_selecionada_id: int | None = None
        self.lista_selecionada_status: str | None = None

        # Widgets da tela de Calendário
        self.calendario: Calendar | None = None
        self.combo_funcionarios: ctk.CTkComboBox | None = None
        self.e_obs_agenda: ctk.CTkEntry | None = None
        self.tree_tarefas_dia: ttk.Treeview | None = None
        self.lbl_data_selecionada: ctk.CTkLabel | None = None
        self.funcionarios_cache: list[dict] = []
        # --- Fim da Declaração ---

        # Carrega o core e o tema PREVIAMENTE para evitar conflito de cores (Treeview vs CTk)
        self.core = SistemaCreditos()
        self.update_manager = UpdateManager()
        saved_theme = self.core.get_config('tema')
        ctk.set_appearance_mode("Dark" if saved_theme == 1 else "Light")
        ctk.set_default_color_theme("green")

        self.title(f"Hotel Santos - Gestao de Creditos v{self.core.versao_atual}")
        self.geometry("1200x850")
        self.minsize(1024, 768) # Garante um tamanho mínimo para não quebrar o layout
        
        # Tenta iniciar maximizado (funciona no Windows, ignora se falhar em outros OS)
        try: self.after(0, lambda: self.state('zoomed'))
        except: pass

        # --- PALETA DE CORES FOSCAS (MATTE) & SINGULARES ---
        self.colors = {
            # Cores de Ação Genéricas (Matte)
            "sucesso": "#059669",       # Emerald 600 (Substituto do verde neon)
            "sucesso_hover": "#047857", # Emerald 700
            "perigo": "#dc2626",        # Red 600
            "perigo_hover": "#b91c1c",  # Red 700
            "aviso": "#d97706",         # Amber 600
            
            # Cores Singulares por Módulo
            "hospedes": "#7c3aed",       # Violet 600 (Roxo Vibrante)
            "hospedes_hover": "#6d28d9", # Violet 700
            "financeiro": "#16a34a",     # Green 600 (Verde Vibrante)
            "financeiro_hover": "#15803d", # Green 700
            "compras": "#ea580c",        # Orange 600 (Laranja Vibrante)
            "compras_hover": "#c2410c",  # Orange 700
            "calendario": "#db2777",     # Pink 600 (Rosa Vibrante)
            "calendario_hover": "#be185d", # Pink 700
            "dashboard": "#2563eb",      # Blue 600 (Azul Vibrante)
            "dashboard_hover": "#1d4ed8", # Blue 700
            "ajustes": "#0d9488",        # Teal 600 (Turquesa Vibrante)
            "ajustes_hover": "#0f766e",  # Teal 700
            
            # UI Base
            "branco": "#f8fafc",        # Slate 50
            "sidebar_bg": "#1e293b",    # Slate 800 (Azul acinzentado escuro)
            "sidebar_txt": "#e2e8f0"    # Slate 200
        }
        self.setup_custom_styles()
        # Configuração do Ícone da Janela
        # Tenta carregar o ícone usando o caminho seguro
        try:
            self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass # Se falhar (ex: linux ou arquivo faltando), segue sem ícone

        # Protocolo para fechar o app sem erros de terminal
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=self.colors["sidebar_bg"])
        # Sidebar começa oculta até o login
        self.sidebar.pack_propagate(False)
        
        ctk.CTkLabel(self.sidebar, text="H-SANTOS", font=("Arial", 22, "bold"), text_color=self.colors["sucesso"]).pack(pady=30)
        
        btn_opts = {"height": 40, "anchor": "w", "fg_color": "transparent", "text_color": self.colors["sidebar_txt"]}
        
        ctk.CTkButton(self.sidebar, text="🏠 Home", command=self.tela_home, hover_color=self.colors["ajustes_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="👥 Hóspedes", command=self.tela_hospedes, hover_color=self.colors["hospedes_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="💰 Financeiro", command=self.tela_financeiro, hover_color=self.colors["financeiro_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="🛒 Compras", command=self.tela_compras, hover_color=self.colors["compras_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="📅 Calendário", command=self.tela_calendario, hover_color=self.colors["calendario_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="📊 Dashboard", command=self.tela_dash, hover_color=self.colors["dashboard_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        ctk.CTkButton(self.sidebar, text="⚙️ Ajustes", command=self.tela_config, hover_color=self.colors["ajustes_hover"], **btn_opts).pack(pady=5, fill="x", padx=10)
        
        # Botão de Logout no final da sidebar
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(expand=True, fill="y")
        
        # Botão de Atualização (Inicia oculto)
        self.btn_update = ctk.CTkButton(self.sidebar, text="⬇️ Atualização", fg_color=self.colors["aviso"], 
                                        hover_color="#b45309", text_color="#ffffff", anchor="center")
        # Não fazemos pack aqui, apenas quando houver update

        self.btn_sair = ctk.CTkButton(self.sidebar, text=" 🚪 Sair", command=self.logout, hover_color=self.colors["perigo_hover"], **btn_opts)
        self.btn_sair.pack(pady=20, fill="x", padx=10)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        self.tela_login()

    # =========================================================================
    # 1. SETUP & CORE (Estilos, Configurações Globais)
    # =========================================================================
    def setup_custom_styles(self) -> None:
        style = ttk.Style()
        # Tenta usar o tema 'clam', que é mais moderno e customizável
        try:
            style.theme_use("clam")
        except:
            pass # Usa o tema padrão se 'clam' não estiver disponível

        is_dark = ctk.get_appearance_mode() == "Dark"
        
        # Cores para tema claro e escuro
        bg_color = "#1f2937" if is_dark else "#ffffff" # Gray 800 vs White
        fg_color = "#f3f4f6" if is_dark else "#1f2937" # Gray 100 vs Gray 800
        field_bg = "#374151" if is_dark else "#f8fafc" # Gray 700 vs Slate 50
        header_bg = "#111827" if is_dark else "#e2e8f0" # Gray 900 vs Slate 200
        selected_fg = "#ffffff"

        style.configure("Treeview", 
                        background=bg_color, 
                        fieldbackground=field_bg, 
                        foreground=fg_color,
                        rowheight=35,
                        borderwidth=0)
        style.configure("Treeview.Heading", background=header_bg, foreground=fg_color, relief="flat", font=("Arial", 11, "bold"))
        style.map("Treeview", background=[("selected", self.colors["ajustes"])], foreground=[("selected", selected_fg)])

    def configurar_tags_tabela(self, tree: ttk.Treeview) -> None:
        """Aplica configurações de cores para linhas pares, ímpares e saídas, adaptando-se ao tema."""
        is_dark = ctk.get_appearance_mode() == "Dark"
        
        # Cores para tema claro e escuro
        if is_dark:
            # Acessa a cor do tema (índice 1 para Dark Mode)
            odd_bg = "#1f2937" # Gray 800
            even_bg = "#2d3748" # Gray 750
        else:
            odd_bg = "#f8fafc" # Slate 50
            even_bg = "#ffffff"
        
        tree.tag_configure('odd', background=odd_bg)
        tree.tag_configure('even', background=even_bg)
        tree.tag_configure('saida', foreground=self.colors["perigo"])
        tree.tag_configure('multa', foreground=self.colors["aviso"])
        tree.tag_configure('pagamento_multa', foreground=self.colors["sucesso"])
        tree.tag_configure('seta_subiu', foreground=self.colors["perigo"])
        tree.tag_configure('seta_desceu', foreground=self.colors["sucesso"])

    def on_closing(self) -> None:
        """Encerra o processo de forma limpa"""
        try:
            # Tenta realizar um backup automático silencioso ao fechar
            if hasattr(self, 'core'):
                self.core.fazer_backup()
        except:
            pass # Não impede o fechamento se o backup falhar
        self.quit()
        self.destroy()
        sys.exit()

    def limpar_tela(self) -> None:
        for w in self.main_frame.winfo_children(): w.destroy()
        # Reseta configurações de grid (importante pois a tela de histórico altera isso)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)
        self.main_frame.grid_rowconfigure(0, weight=1)

    # =========================================================================
    # 1.5. AUTO-UPDATE
    # =========================================================================
    def verificar_e_notificar_update(self) -> None:
        """Verifica se há atualizações em uma thread separada e notifica o usuário."""
        def _task():
            try:
                # Apenas verifica se estiver rodando o executável compilado
                if not getattr(sys, 'frozen', False):
                    print("INFO: Verificação de update pulada (rodando como script).")
                    return

                tem_update, nova_versao, url = self.update_manager.verificar_atualizacao()
                if tem_update:
                    # Agendamos a chamada do messagebox na thread principal
                    self.after(0, self.mostrar_botao_update, nova_versao, url)
            except Exception as e:
                print(f"Erro ao verificar atualização: {e}") # Log silencioso no console
        
        threading.Thread(target=_task, daemon=True).start()

    def mostrar_botao_update(self, nova_versao: str, url: str) -> None:
        """Exibe o botão de atualização na sidebar"""
        self.btn_update.configure(
            text=f"⬇️ Atualizar v{nova_versao}", 
            command=lambda: self.propor_atualizacao(nova_versao, url)
        )
        self.btn_update.pack(before=self.btn_sair, pady=10, fill="x", padx=10)

    def propor_atualizacao(self, nova_versao: str, url: str) -> None:
        """Mostra um messagebox para o usuário e inicia o download se aceito."""
        if messagebox.askyesno("Atualização Disponível", 
                               f"Uma nova versão ({nova_versao}) está disponível!\n"
                               "Deseja baixar e instalar agora?\n\n"
                               "O aplicativo será reiniciado."):
            self.iniciar_janela_de_progresso(url, nova_versao)

    def iniciar_janela_de_progresso(self, url: str, nova_versao: str) -> None:
        """Cria a janela de progresso e inicia o download."""
        janela_progresso = ctk.CTkToplevel(self)
        janela_progresso.title("Atualizando...")
        janela_progresso.geometry("400x150")
        janela_progresso.transient(self)
        janela_progresso.lift()
        janela_progresso.grab_set()
        janela_progresso.protocol("WM_DELETE_WINDOW", lambda: None) # Impede de fechar

        ctk.CTkLabel(janela_progresso, text="Baixando nova versão, por favor aguarde...", font=("Arial", 14)).pack(pady=20)
        
        progress_bar = ctk.CTkProgressBar(janela_progresso, width=350)
        progress_bar.pack(pady=10)
        progress_bar.set(0)

        lbl_status = ctk.CTkLabel(janela_progresso, text="Iniciando download...")
        lbl_status.pack(pady=5)

        def update_callback(progress, status=None):
            progress_bar.set(progress)
            if status == "finalizando":
                lbl_status.configure(text="Atualização baixada! Reiniciando o aplicativo...")
            else:
                lbl_status.configure(text=f"{int(progress * 100)}%")
        
        # A função aplicar_atualizacao já roda em uma thread e lida com erros
        self.update_manager.aplicar_atualizacao(url, nova_versao, progress_callback=lambda p, s=None: self.after(0, update_callback, p, s))

    def verificar_update_manual(self) -> None:
        """Verifica manualmente por atualizações e informa o usuário."""
        self.configure(cursor="watch")
        self.update_idletasks()

        def _task():
            try:
                # Apenas verifica se estiver rodando o executável compilado
                if not getattr(sys, 'frozen', False):
                    self.after(0, lambda: messagebox.showinfo("Aviso", "A verificação de atualização só funciona no aplicativo compilado (instalador)."))
                    return

                tem_update, nova_versao, url = self.update_manager.verificar_atualizacao()

                if tem_update:
                    # Agendamos a chamada do messagebox na thread principal
                    self.after(0, self.propor_atualizacao, nova_versao, url)
                else:
                    self.after(0, lambda: messagebox.showinfo("Atualização", "Você já está usando a versão mais recente."))
            
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", f"Não foi possível verificar por atualizações:\n{e}"))
            finally:
                # Garante que o cursor volte ao normal
                self.after(0, lambda: self.configure(cursor="arrow"))

        threading.Thread(target=_task, daemon=True).start()

    # =========================================================================
    # 2. AUTENTICAÇÃO
    # =========================================================================
    def logout(self) -> None:
        """Realiza o logout do usuário"""
        if messagebox.askyesno("Sair", "Tem certeza que deseja sair?"):
            self.current_user = None
            self.tela_login()

    def tela_login(self) -> None:
        self.limpar_tela()
        self.sidebar.pack_forget() # Garante que a sidebar esteja oculta
        
        f = ctk.CTkFrame(self.main_frame, width=300, height=350)
        f.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(f, text="LOGIN", font=("Arial", 20, "bold")).pack(pady=30)
        
        eu = ctk.CTkEntry(f, placeholder_text="Usuário", width=200); eu.pack(pady=10)
        ep = ctk.CTkEntry(f, placeholder_text="Senha", show="*", width=200); ep.pack(pady=10)
        
        def tentar_login(event: object | None = None) -> None:
            u = self.core.verificar_login(eu.get(), ep.get())
            if u:
                self.current_user = u
                # Repack para garantir que a sidebar fique à esquerda e o main preencha o resto
                self.main_frame.pack_forget()
                self.sidebar.pack(side="left", fill="y")
                self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
                self.tela_home()
                # Verifica atualizações 2 segundos após o login bem-sucedido
                self.after(2000, self.verificar_e_notificar_update)
            else:
                messagebox.showerror("Erro", "Credenciais inválidas")
                
        ep.bind("<Return>", tentar_login)
        
        ctk.CTkButton(f, text="Entrar", command=tentar_login, width=200, fg_color=self.colors["sucesso"], hover_color=self.colors["sucesso_hover"]).pack(pady=20)

    # =========================================================================
    # 3. NAVEGAÇÃO PRINCIPAL
    # =========================================================================
    def tela_home(self) -> None:
        self.current_screen_function = self.tela_home
        self.current_screen_args = ()
        self.current_screen_kwargs = {}

        self.limpar_tela()
        ctk.CTkLabel(self.main_frame, text="Controle de Créditos - Hotel Santos", font=("Arial", 28, "bold"), text_color=self.colors["sucesso"]).pack(pady=60)
        grid = ctk.CTkFrame(self.main_frame, fg_color="transparent"); grid.pack()
        
        # Definição de cores (Light, Dark) para melhor contraste e visual no modo escuro
        btns = [("👥 HÓSPEDES", self.tela_hospedes, (self.colors["hospedes"], self.colors["hospedes_hover"])),
                ("💰 FINANCEIRO", self.tela_financeiro, (self.colors["financeiro"], self.colors["financeiro_hover"])),
                ("🛒 COMPRAS", self.tela_compras, (self.colors["compras"], self.colors["compras_hover"])),
                ("📅 CALENDÁRIO", self.tela_calendario, (self.colors["calendario"], self.colors["calendario_hover"])),
                ("📊 DASHBOARD", self.tela_dash, (self.colors["dashboard"], self.colors["dashboard_hover"])),
                ("⚙️ AJUSTES", self.tela_config, (self.colors["ajustes"], self.colors["ajustes_hover"]))]

        for i, (t, c, col) in enumerate(btns):
            ctk.CTkButton(grid, text=t, width=250, height=90, command=c, fg_color=col, font=("Arial", 14, "bold")).grid(row=i//2, column=i%2, padx=20, pady=20)

    # =========================================================================
    # 4. MÓDULO HÓSPEDES (Listagem e Busca)
    # =========================================================================
    def tela_hospedes(self, filtro: str = "todos") -> None:
        self.current_screen_function = self.tela_hospedes
        self.current_screen_args = ()
        self.current_screen_kwargs = {'filtro': filtro}

        self.limpar_tela()
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent"); nav.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkLabel(nav, text="LISTAGEM DE HÓSPEDES", font=("Arial", 18, "bold"), text_color=self.colors["hospedes"]).pack(side="left", padx=20)
        ctk.CTkButton(nav, text="+ Novo Hóspede", width=120, fg_color=self.colors["hospedes"], hover_color=self.colors["hospedes_hover"], command=self.janela_cadastro_hospede).pack(side="right")

        self.ent_busca = ctk.CTkEntry(self.main_frame, placeholder_text="Pesquisar por nome ou documento...", width=500)
        self.ent_busca.pack(pady=10)
        self.ent_busca.bind("<KeyRelease>", lambda e: self.agendar_busca(filtro))

        self.tree_h = ttk.Treeview(self.main_frame, columns=("N", "D", "S"), show='headings')
        for c, t in [("N", "Nome Completo"), ("D", "CPF ou CNPJ"), ("S", "Saldo Disponível (R$)")]: 
            self.tree_h.heading(c, text=t); self.tree_h.column(c, anchor="center")
        self.configurar_tags_tabela(self.tree_h)
        self.tree_h.pack(expand=True, fill="both", padx=15, pady=10)
        self.tree_h.bind("<Double-1>", self.preparar_historico)

        # Menu de contexto (clique direito)
        self.menu_hospede = ctk.CTkFrame(self, width=150, height=100, border_width=1)
        ctk.CTkButton(self.menu_hospede, text="Ver Histórico Financeiro", command=self.preparar_historico, fg_color="transparent", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"], anchor="w").pack(fill="x")
        ctk.CTkButton(self.menu_hospede, text="Editar Cadastro", command=self.preparar_edicao_hospede, fg_color="transparent", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"], anchor="w").pack(fill="x")

        def show_menu(event: object) -> None:
            selection = self.tree_h.identify_row(event.y)
            if selection:
                self.tree_h.selection_set(selection)
                self.menu_hospede.place(x=event.x_root - self.winfo_x(), y=event.y_root - self.winfo_y())
                self.menu_hospede.lift()

        self.tree_h.bind("<Button-3>", show_menu)
        self.bind("<Button-1>", lambda e: self.menu_hospede.place_forget())
        self.atualizar_lista_hospedes(filtro)

    def agendar_busca(self, filtro: str) -> None:
        """Aguarda 500ms após a última tecla antes de buscar (Debounce)"""
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(500, lambda: self.atualizar_lista_hospedes(filtro))

    def atualizar_lista_hospedes(self, filtro: str) -> None:
        self.tree_h.delete(*self.tree_h.get_children())
        for i, h in enumerate(self.core.buscar_filtrado(self.ent_busca.get(), filtro)):
            # Usamos o documento como iid para garantir que o valor exato (string) seja preservado
            tag = 'odd' if i % 2 != 0 else 'even'
            self.tree_h.insert("", "end", iid=h[1], values=(h[0], h[1], f"{h[2]:.2f}"), tags=(tag,))

    def preparar_historico(self, event: object | None = None) -> None:
        self.menu_hospede.place_forget()
        sel = self.tree_h.selection()
        if sel:
            doc = sel[0]  # O iid agora é o documento exato, sem risco de conversão numérica
            n = self.tree_h.item(doc)['values'][0]
            self.tela_historico(n, str(doc))

    def preparar_edicao_hospede(self, event: object | None = None) -> None:
        self.menu_hospede.place_forget()
        sel = self.tree_h.selection()
        if sel:
            doc = sel[0]
            self.janela_cadastro_hospede(doc_to_edit=str(doc))

    # =========================================================================
    # 5. MÓDULO HISTÓRICO & FINANCEIRO (Detalhes do Cliente)
    # =========================================================================
    def tela_historico(self, nome: str, doc: str) -> None:
        self.current_screen_function = self.tela_historico
        self.current_screen_args = (nome, doc)
        self.current_screen_kwargs = {}

        self.limpar_tela()
        self.main_frame.columnconfigure(0, weight=3); self.main_frame.columnconfigure(1, weight=1)
        f_esq = ctk.CTkFrame(self.main_frame, fg_color="transparent"); f_esq.grid(row=0, column=0, sticky="nsew", padx=10)
        top = ctk.CTkFrame(f_esq, fg_color="transparent"); top.pack(fill="x", pady=5)
        ctk.CTkButton(top, text="← Voltar", width=80, command=self.tela_hospedes).pack(side="left")
        ctk.CTkButton(top, text="💬 WhatsApp", fg_color="#25D366", hover_color="#128C7E", width=100, command=lambda: self.enviar_whatsapp(nome, str(doc))).pack(side="right", padx=5)
        ctk.CTkButton(top, text=" Extrato", fg_color="#2c3e50", width=80, command=lambda: self.emitir_extrato(nome, doc)).pack(side="right", padx=5)
        ctk.CTkButton(top, text="📄 Ticket Multas", fg_color="#c0392b", width=80, command=lambda: self.emitir_extrato_multas(nome, doc)).pack(side="right", padx=5)
        ctk.CTkButton(top, text="📄 PDF Voucher", fg_color=self.colors["sucesso"], width=100, command=lambda: self.emitir_voucher(nome, doc)).pack(side="right", padx=5)
        ctk.CTkLabel(f_esq, text=f"Histórico Financeiro: {nome}", font=("Arial", 20, "bold")).pack(pady=10)

        form = ctk.CTkFrame(f_esq, fg_color="transparent"); form.pack(fill="x", pady=5)
        ctk.CTkButton(form, text="Adicionar Crédito", fg_color=self.colors["sucesso"], command=lambda: self.janela_add_credito(doc, nome)).pack(side="left", padx=5)
        ctk.CTkButton(form, text="Utilizar Crédito", fg_color=self.colors["perigo"], command=lambda: self.janela_usar_credito(doc, nome)).pack(side="left", padx=5)
        ctk.CTkButton(form, text="Lançar Multa", fg_color=self.colors["aviso"], text_color="white", command=lambda: self.janela_add_multa(doc, nome)).pack(side="left", padx=5)
        ctk.CTkButton(form, text="Pagar Multa", fg_color="#27ae60", command=lambda: self.janela_pagar_multa(doc, nome)).pack(side="left", padx=5)

        # Adicionada coluna ID (invisível ou primeira) para permitir edição correta
        self.tree_z = ttk.Treeview(f_esq, columns=("ID", "T", "V", "D", "C", "U"), show='headings', height=10)
        self.tree_z.heading("ID", text="#"); self.tree_z.column("ID", width=40, anchor="center")
        for c, t in [("T","Tipo"),("V","Valor"),("D","Data"),("C","Categoria"), ("U", "Resp.")]: 
            self.tree_z.heading(c, text=t); self.tree_z.column(c, anchor="center")
        self.tree_z.pack(expand=True, fill="both")
        self.configurar_tags_tabela(self.tree_z)
        
        # RESTAURADO: Clique direito para editar data
        self.tree_z.bind("<Button-3>", lambda e: self.janela_calendario_vencimento(e, doc, nome))
        
        hist = self.core.get_historico_detalhado(doc)
        for i, m in enumerate(hist):
            data_br = datetime.strptime(m['data_acao'], "%Y-%m-%d").strftime("%d/%m/%Y")
            user_resp = m['usuario'] if m['usuario'] else "Sistema"
            
            tags = ['odd' if i % 2 != 0 else 'even']
            if m['tipo'] == 'SAIDA': tags.append('saida')
            if m['tipo'] == 'MULTA': tags.append('multa')
            if m['tipo'] == 'PAGAMENTO_MULTA': tags.append('pagamento_multa')

            self.tree_z.insert("", "end", values=(m['id'], m['tipo'], f"{m['valor']:.2f}", data_br, m['categoria'], user_resp), tags=tags)

        f_dir = ctk.CTkFrame(self.main_frame, fg_color="transparent"); f_dir.grid(row=0, column=1, sticky="nsew", padx=10)
        s, v, b = self.core.get_saldo_info(doc)
        divida = self.core.get_divida_multas(doc)
        
        info_cards = [("Saldo de Crédito", f"R$ {s:.2f}", self.colors["sucesso"]), 
                      ("Vencimento Próximo", v, self.colors["perigo"] if b else self.colors["aviso"]),
                      ("Dívida (Multas)", f"R$ {divida:.2f}", self.colors["aviso"] if divida > 0 else "gray")]

        for t, val, col in info_cards:
            c = ctk.CTkFrame(f_dir, border_width=1); c.pack(fill="x", pady=5, ipady=10)
            ctk.CTkLabel(c, text=t, font=("Arial", 11)).pack()
            ctk.CTkLabel(c, text=val, font=("Arial", 16, "bold"), text_color=col).pack()

        p = ctk.CTkFrame(f_dir, fg_color="#fef9c3", border_width=1, border_color="#facc15")
        p.pack(fill="both", expand=True, pady=10)
        ctk.CTkLabel(p, text="📌 NOTAS GERAIS", text_color="#854d0e", font=("Arial", 12, "bold")).pack(pady=5)
        txt = ctk.CTkTextbox(p, fg_color="transparent", text_color="black"); txt.pack(fill="both", expand=True, padx=5)
        txt.insert("1.0", self.core.get_anotacao(doc))
        ctk.CTkButton(p, text="Salvar Notas", width=100, fg_color=self.colors["aviso"], text_color="white", command=lambda: self.core.salvar_anotacao(doc, txt.get("1.0","end-1c"))).pack(pady=5)

    def enviar_whatsapp(self, nome: str, doc: str) -> None:
        s, v, b = self.core.get_saldo_info(doc)
        if s <= 0:
            messagebox.showwarning("Aviso", "Cliente sem saldo para enviar.")
            return

        hospede = self.core.get_hospede(doc)
        fone = hospede['telefone'] if hospede and hospede['telefone'] else None

        if not fone:
            if messagebox.askyesno("Telefone não encontrado", "Este cliente não possui um telefone cadastrado. Deseja cadastrar/editar agora?"):
                self.janela_cadastro_hospede(doc_to_edit=doc)
            return

        # Limpa o número para conter apenas dígitos
        fone_limpo = "".join(filter(str.isdigit, fone))
        if not fone_limpo:
            messagebox.showerror("Erro", f"O número de telefone cadastrado ('{fone}') é inválido.")
            return

        msg = f"*HOTEL SANTOS - VOUCHER DE CRÉDITO*\n\nOlá {nome},\nSegue seu saldo atualizado:\n\n💰 *Valor:* R$ {s:.2f}\n📅 *Validade:* {v}\n\nUtilize este crédito em sua próxima hospedagem!"
        link = f"https://web.whatsapp.com/send?phone=55{fone_limpo}&text={quote(msg)}"
        webbrowser.open(link)

    def emitir_voucher(self, nome: str, doc: str) -> None:
        """Gera o voucher em uma thread separada para não travar a interface"""
        self.configure(cursor="watch") # Muda cursor para 'carregando'
        def _task():
            try:
                f = self.core.gerar_pdf_voucher(nome, doc)
                # UI updates devem ser agendados na main thread
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Voucher gerado: {f}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow")) # Restaura cursor
        threading.Thread(target=_task, daemon=True).start()

    def emitir_extrato(self, nome: str, doc: str) -> None:
        self.configure(cursor="watch")
        def _task():
            try:
                f = self.core.gerar_pdf_extrato(nome, doc)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Extrato gerado: {f}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))
        threading.Thread(target=_task, daemon=True).start()

    def emitir_extrato_multas(self, nome: str, doc: str) -> None:
        self.configure(cursor="watch")
        def _task():
            try:
                f = self.core.gerar_pdf_multas(nome, doc)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Ticket de Multas gerado: {f}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))
        threading.Thread(target=_task, daemon=True).start()

    # =========================================================================
    # 6. MÓDULO DASHBOARD & RELATÓRIOS
    # =========================================================================
    def tela_dash(self) -> None:
        # Importação tardia (Lazy Import) para acelerar a abertura do App
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        # Aplica o tema do CustomTkinter ao Matplotlib para consistência visual
        if ctk.get_appearance_mode() == "Dark":
            plt.style.use('dark_background')
            plt.rcParams.update({
                "figure.facecolor": "#1f2937", # Match new bg
                "axes.facecolor": "#1f2937",
                "text.color": "white",
                "axes.labelcolor": "white",
                "xtick.color": "white",
                "ytick.color": "white",
                "axes.edgecolor": "white",
                "legend.facecolor": "#343638",
            })
        else:
            # Reseta para o padrão do Matplotlib para o tema claro
            plt.style.use('default')
            plt.rcdefaults()

        self.current_screen_function = self.tela_dash
        self.current_screen_args = ()
        self.current_screen_kwargs = {}
        self.limpar_tela()
        t, v, av, q, total_multas = self.core.get_dados_dash()
        dias_config = self.core.get_config('alerta_dias')
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent"); nav.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkButton(nav, text="📥 Exportar Relatório CSV", fg_color=self.colors["dashboard"], width=180, command=lambda: [
            messagebox.showinfo("Exportado", f"Relatório salvo em:\n{self.core.exportar_csv()}")
        ]).pack(side="right")
        
        # Conteúdo em Frame Rolável para telas pequenas
        scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        cards = ctk.CTkFrame(scroll, fg_color="transparent"); cards.pack(fill="x", pady=10)
        lista_cards = [
            ("Saldo Total Geral", f"R$ {t:.2f}", self.colors["sucesso"]), 
            ("Total Vencidos", f"R$ {v:.2f}", self.colors["perigo"]), 
            (f"A Vencer ({dias_config} dias)", f"R$ {av:.2f}", self.colors["aviso"]),
            ("Base de Clientes", str(q), self.colors["dashboard"]),
            ("Total Multas", f"R$ {total_multas:.2f}", self.colors["perigo"])
        ]
        for tit, val, col in lista_cards:
            c = ctk.CTkFrame(cards, border_width=1); c.pack(side="left", expand=True, padx=5, fill="both", ipady=10)
            ctk.CTkLabel(c, text=tit, font=("Arial", 11)).pack()
            ctk.CTkLabel(c, text=val, font=("Arial", 18, "bold"), text_color=col).pack()

        # Gráfico de Barras (Entradas vs Saídas)
        meses, entradas, saidas = self.core.get_dados_grafico_mensal()
        if meses:
            f_bar = ctk.CTkFrame(scroll, fg_color="transparent")
            f_bar.pack(fill="x", padx=10, pady=5)
            
            fig_bar, ax_bar = plt.subplots(figsize=(8, 2.5), dpi=80)
            x = range(len(meses))
            width = 0.35
            
            ax_bar.bar([i - width/2 for i in x], entradas, width, label='Entradas', color=self.colors["sucesso"])
            ax_bar.bar([i + width/2 for i in x], saidas, width, label='Saídas', color=self.colors["perigo"])
            
            ax_bar.set_xticks(x); ax_bar.set_xticklabels(meses)
            ax_bar.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=2, frameon=False, fontsize='small')
            ax_bar.spines['top'].set_visible(False); ax_bar.spines['right'].set_visible(False)
            FigureCanvasTkAgg(fig_bar, master=f_bar).get_tk_widget().pack(fill="both", expand=True)

        inf = ctk.CTkFrame(scroll, fg_color="transparent"); inf.pack(fill="both", expand=True)
        gr = ctk.CTkFrame(inf); gr.pack(side="left", fill="both", expand=True, padx=5)
        dados_g = self.core.get_dados_grafico_categorias()
        if dados_g:
            fig, ax = plt.subplots(figsize=(4,3), dpi=85)
            ax.pie([x[1] for x in dados_g], labels=[x[0] for x in dados_g], autopct='%1.1f%%')
            FigureCanvasTkAgg(fig, master=gr).get_tk_widget().pack(pady=10, fill="both", expand=True)
        
        tab = ctk.CTkFrame(inf); tab.pack(side="right", fill="both", expand=True, padx=5)
        ctk.CTkLabel(tab, text=f"Detalhamento Alerta ({dias_config} dias)", font=("Arial", 12, "bold")).pack(pady=5)
        tv = ttk.Treeview(tab, columns=("H", "D", "V"), show='headings')
        for c, t_ in [("H","Hóspede"),("D","Vencimento"),("V","Saldo")]: tv.heading(c, text=t_); tv.column(c, anchor="center", width=100)
        tv.pack(fill="both", expand=True); [tv.insert("", "end", values=h) for h in self.core.get_hospedes_vencendo_em_breve()]

    # =========================================================================
    # MÓDULO COMPRAS
    # =========================================================================
    def tela_compras(self) -> None:
        self.current_screen_function = self.tela_compras
        self.current_screen_args = ()
        self.current_screen_kwargs = {}
        self.limpar_tela()

        # Navegação Superior
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent"); nav.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkLabel(nav, text="GESTÃO DE COMPRAS (ORDENS)", font=("Arial", 18, "bold"), text_color=self.colors["compras"]).pack(side="left", padx=20)

        # Layout Dividido: Esquerda (Listas) | Direita (Itens da Lista)
        paned = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=10, pady=5)
        
        # --- ESQUERDA: LISTAS DE COMPRAS ---
        frame_listas = ctk.CTkFrame(paned, width=350)
        frame_listas.pack(side="left", fill="y", padx=(0, 10))
        frame_listas.pack_propagate(False)

        ctk.CTkLabel(frame_listas, text="Minhas Listas / Ordens", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkButton(frame_listas, text="+ Nova Lista", fg_color=self.colors["compras"], hover_color=self.colors["compras_hover"], command=self.criar_nova_lista).pack(pady=5, padx=10, fill="x")

        # Treeview Listas
        cols_l = ("ID", "Data", "Status", "Total")
        self.tree_listas = ttk.Treeview(frame_listas, columns=cols_l, show='headings')
        self.tree_listas.heading("ID", text="#"); self.tree_listas.column("ID", width=40, anchor="center")
        self.tree_listas.heading("Data", text="Data"); self.tree_listas.column("Data", width=80, anchor="center")
        self.tree_listas.heading("Status", text="Status"); self.tree_listas.column("Status", width=80, anchor="center")
        self.tree_listas.heading("Total", text="Valor"); self.tree_listas.column("Total", width=80, anchor="e")
        self.tree_listas.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tree_listas.bind("<<TreeviewSelect>>", self.carregar_lista_selecionada)

        # --- DIREITA: DETALHES DA LISTA ---
        self.frame_detalhes = ctk.CTkFrame(paned)
        self.frame_detalhes.pack(side="right", fill="both", expand=True)
        
        # Header Detalhes
        self.lbl_titulo_lista = ctk.CTkLabel(self.frame_detalhes, text="Selecione uma lista para visualizar", font=("Arial", 16, "bold"))
        self.lbl_titulo_lista.pack(pady=10)
        
        self.frame_acoes_lista = ctk.CTkFrame(self.frame_detalhes, fg_color="transparent")
        self.frame_acoes_lista.pack(fill="x", padx=10)
        
        ctk.CTkButton(self.frame_acoes_lista, text="💬 WhatsApp", fg_color="#25D366", hover_color="#128C7E", width=120, command=self.enviar_lista_whatsapp).pack(side="right", padx=5)
        self.btn_fechar_lista = ctk.CTkButton(self.frame_acoes_lista, text="🔒 Fechar Lista", fg_color=self.colors["perigo"], width=120, command=self.fechar_lista_atual)
        self.btn_imprimir_lista = ctk.CTkButton(self.frame_acoes_lista, text="📄 Imprimir PDF", fg_color="#2c3e50", width=120, command=self.imprimir_lista_atual)
        # Botões iniciam ocultos

        # Formulário de Adição de Item (Só aparece se lista ABERTA)
        self.frame_add_item = ctk.CTkFrame(self.frame_detalhes, border_width=1, border_color="#555")
        
        ctk.CTkLabel(self.frame_add_item, text="Adicionar Item à Lista:", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        
        # Campos do formulário
        self.lista_produtos_cache = self.core.get_produtos_predefinidos()
        self.e_prod_compras = ctk.CTkEntry(self.frame_add_item, width=200, placeholder_text="Produto (Busca...)")
        self.e_prod_compras.grid(row=1, column=0, padx=5, pady=5)
        
        # Configuração da Busca (Copiada da versão anterior)
        bg_list = "#333333" if ctk.get_appearance_mode() == "Dark" else "#ffffff"
        fg_list = "#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000"
        self.lb_sugestoes = Listbox(self.main_frame, width=40, height=5, bg=bg_list, fg=fg_list, selectbackground=self.colors["compras"], selectforeground="white", borderwidth=1, relief="solid")
        
        def autocomplete_prod(event: object) -> None:
            if event.keysym in ['Down', 'Up', 'Return', 'Tab']: return
            typed = self.e_prod_compras.get()
            if not typed: self.lb_sugestoes.place_forget(); return
            filtered = [p for p in self.lista_produtos_cache if typed.lower() in p.lower()]
            if filtered:
                self.lb_sugestoes.delete(0, 'end')
                for item in filtered: self.lb_sugestoes.insert('end', item)
                self.lb_sugestoes.place(in_=self.e_prod_compras, x=0, rely=1.0, relwidth=1.0); self.lb_sugestoes.lift()
            else: self.lb_sugestoes.place_forget()

        def selecionar_sugestao(event: object | None = None) -> None:
            if self.lb_sugestoes.curselection():
                item = self.lb_sugestoes.get(self.lb_sugestoes.curselection())
                self.e_prod_compras.delete(0, 'end'); self.e_prod_compras.insert(0, item)
                self.lb_sugestoes.place_forget(); self.e_prod_compras.focus_set(); self.e_qtd_compras.focus_set()

        self.e_prod_compras.bind("<KeyRelease>", autocomplete_prod)
        self.lb_sugestoes.bind("<Return>", selecionar_sugestao); self.lb_sugestoes.bind("<Button-1>", selecionar_sugestao)

        self.e_qtd_compras = ctk.CTkEntry(self.frame_add_item, width=70, placeholder_text="Qtd")
        self.e_qtd_compras.grid(row=1, column=1, padx=5)
        
        self.e_val_compras = ctk.CTkEntry(self.frame_add_item, width=90, placeholder_text="Valor Unit.")
        self.e_val_compras.grid(row=1, column=2, padx=5)
        
        ctk.CTkButton(self.frame_add_item, text="Adicionar", width=80, fg_color=self.colors["compras"], hover_color=self.colors["compras_hover"], command=self.adicionar_item_lista).grid(row=1, column=3, padx=10)
        
        # Binds de Enter
        self.e_prod_compras.bind("<Return>", lambda e: selecionar_sugestao() if self.lb_sugestoes.winfo_ismapped() else self.adicionar_item_lista())
        self.e_qtd_compras.bind("<Return>", lambda e: self.adicionar_item_lista())
        self.e_val_compras.bind("<Return>", lambda e: self.adicionar_item_lista())

        # Treeview Itens
        cols_i = ("Prod", "Qtd", "Unit", "Total", "Var")
        self.tree_itens = ttk.Treeview(self.frame_detalhes, columns=cols_i, show='headings')
        self.tree_itens.heading("Prod", text="Produto"); self.tree_itens.column("Prod", width=200)
        self.tree_itens.heading("Qtd", text="Qtd"); self.tree_itens.column("Qtd", width=50, anchor="center")
        self.tree_itens.heading("Unit", text="Unit (R$)"); self.tree_itens.column("Unit", width=80, anchor="e")
        self.tree_itens.heading("Total", text="Total (R$)"); self.tree_itens.column("Total", width=80, anchor="e")
        self.tree_itens.heading("Var", text="Var"); self.tree_itens.column("Var", width=60, anchor="center")
        self.tree_itens.pack(fill="both", expand=True, padx=10, pady=10)
        self.configurar_tags_tabela(self.tree_itens)

        # Inicialização
        self.atualizar_lista_de_listas()

    def atualizar_lista_de_listas(self) -> None:
        self.tree_listas.delete(*self.tree_listas.get_children())
        listas = self.core.get_listas_resumo()
        for l in listas:
            data_br = datetime.strptime(l['data_criacao'], "%Y-%m-%d").strftime("%d/%m/%Y")
            total = l['total_valor'] if l['total_valor'] else 0.0
            self.tree_listas.insert("", "end", values=(l['id'], data_br, l['status'], f"R$ {total:.2f}"))

    def criar_nova_lista(self) -> None:
        try:
            if not self.current_user: return
            lid = self.core.criar_lista_compras(self.current_user['username'])
            self.atualizar_lista_de_listas()
            # Seleciona a nova lista automaticamente (último item, pois a query ordena DESC, mas treeview insere no fim por padrão, vamos achar pelo ID)
            # Como a query é DESC, o novo é o primeiro da lista de dados, então é o primeiro no treeview se inserirmos na ordem
            # Mas vamos simplificar: recarrega e seleciona o topo
            child_id = self.tree_listas.get_children()[0]
            self.tree_listas.selection_set(child_id)
            self.tree_listas.focus(child_id)
            self.carregar_lista_selecionada(None)
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def carregar_lista_selecionada(self, event: object | None) -> None:
        sel = self.tree_listas.selection()
        if not sel: return
        
        item = self.tree_listas.item(sel[0])
        lid, data, status, total = item['values']
        self.lista_selecionada_id = lid
        self.lista_selecionada_status = status
        
        self.lbl_titulo_lista.configure(text=f"Lista #{lid} - {status} ({data})")
        
        # Controle de Visibilidade dos Botões e Form
        if status == "ABERTA":
            self.frame_add_item.pack(fill="x", padx=10, pady=5, after=self.frame_acoes_lista)
            self.btn_fechar_lista.pack(side="left", padx=5)
            self.btn_imprimir_lista.pack(side="left", padx=5)
        else:
            self.frame_add_item.pack_forget()
            self.btn_fechar_lista.pack_forget()
            self.btn_imprimir_lista.pack(side="left", padx=5) # Imprimir sempre disponível
            
        self.atualizar_itens_lista()

    def atualizar_itens_lista(self) -> None:
        self.tree_itens.delete(*self.tree_itens.get_children())
        if not self.lista_selecionada_id: return
        
        itens = self.core.get_itens_lista(self.lista_selecionada_id)
        for i in itens:
            seta = "-"
            tag_seta = "even"
            if i.get('tendencia') == 'subiu': seta = "▲"; tag_seta = "seta_subiu"
            elif i.get('tendencia') == 'desceu': seta = "▼"; tag_seta = "seta_desceu"
            
            self.tree_itens.insert("", "end", values=(i['produto'], i['quantidade'], f"{i['valor_unitario']:.2f}", f"{i['valor_total']:.2f}", seta), tags=(tag_seta,))

    def adicionar_item_lista(self) -> None:
        if not self.lista_selecionada_id or self.lista_selecionada_status != "ABERTA": return
        
        if not self.current_user: return
        try:
            raw_prod = self.e_prod_compras.get()
            qtd = self.e_qtd_compras.get()
            val = self.e_val_compras.get()
            
            if not raw_prod or not qtd or not val: raise Exception("Preencha todos os campos.")
            
            prod_digitado = raw_prod.upper().strip()
            
            # Verifica se o produto já existe na lista atual para evitar duplicidade
            itens_atuais = self.core.get_itens_lista(self.lista_selecionada_id)
            if any(item['produto'] == prod_digitado for item in itens_atuais):
                raise Exception(f"O produto '{prod_digitado}' já está nesta lista.")

            # Validação de produto existente
            produtos_existentes = [p.upper() for p in self.lista_produtos_cache]
            if prod_digitado not in produtos_existentes:
                raise Exception("Produto não cadastrado! Cadastre-o primeiro em Ajustes.")

            # Adiciona
            self.core.adicionar_compra(
                datetime.now().strftime("%d/%m/%Y"), 
                prod_digitado, qtd, val, 
                usuario=self.current_user['username'], 
                lista_id=self.lista_selecionada_id
            )
            
            # Limpa e Atualiza
            self.e_prod_compras.delete(0, 'end'); self.e_qtd_compras.delete(0, 'end'); self.e_val_compras.delete(0, 'end')
            self.e_prod_compras.focus()
            self.lb_sugestoes.place_forget()
            
            self.atualizar_itens_lista()
            self.atualizar_lista_de_listas() # Para atualizar o total na esquerda
            
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def fechar_lista_atual(self) -> None:
        if not self.lista_selecionada_id: return
        if messagebox.askyesno("Confirmar", "Deseja fechar esta lista? Ela não poderá mais ser editada."):
            self.core.fechar_lista_compras(self.lista_selecionada_id)
            self.atualizar_lista_de_listas()
            # Recarrega a seleção para atualizar a UI (esconder form)
            # Precisamos achar o item no treeview novamente
            for item in self.tree_listas.get_children():
                if self.tree_listas.item(item)['values'][0] == self.lista_selecionada_id:
                    self.tree_listas.selection_set(item)
                    self.carregar_lista_selecionada(None)
                    break

    def imprimir_lista_atual(self) -> None:
        if not self.lista_selecionada_id: return
        self.configure(cursor="watch")
        def _task():
            try:
                f = self.core.gerar_pdf_lista(self.lista_selecionada_id)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"PDF Gerado: {f}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))
        threading.Thread(target=_task, daemon=True).start()

    def enviar_lista_whatsapp(self) -> None:
        if not self.lista_selecionada_id:
            messagebox.showwarning("Aviso", "Selecione uma lista primeiro.")
            return
        
        itens = self.core.get_itens_lista(self.lista_selecionada_id)
        if not itens:
            messagebox.showwarning("Aviso", "A lista está vazia.")
            return
            
        msg = f"*LISTA DE COMPRAS #{self.lista_selecionada_id}*\n\n"
        for i in itens:
            msg += f"- {i['quantidade']}x {i['produto']} (R$ {i['valor_unitario']:.2f})\n"
            
        link = f"https://web.whatsapp.com/send?text={quote(msg)}"
        webbrowser.open(link)

    def exportar_pdf_compras(self) -> None:
        self.configure(cursor="watch")
        def _task():
            try:
                f = self.core.gerar_pdf_compras()
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Relatório de Compras gerado: {f}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))
        threading.Thread(target=_task, daemon=True).start()

    # =========================================================================
    # MÓDULO CALENDÁRIO
    # =========================================================================
    def tela_calendario(self) -> None:
        if not Calendar:
            messagebox.showerror("Erro de Dependência", "A biblioteca 'tkcalendar' é necessária para este módulo.\n\nInstale com: pip install tkcalendar")
            return

        self.current_screen_function = self.tela_calendario
        self.current_screen_args = ()
        self.current_screen_kwargs = {}
        self.limpar_tela()

        # Navegação
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkLabel(nav, text="CALENDÁRIO DE FUNCIONÁRIOS", font=("Arial", 18, "bold"), text_color=self.colors["calendario"]).pack(side="left", padx=20)

        # Layout principal
        main_paned = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        main_paned.pack(fill="both", expand=True, padx=10, pady=5)

        # --- PAINEL ESQUERDO (Gerenciamento) ---
        left_frame = ctk.CTkFrame(main_paned, width=350)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)

        # --- PAINEL DIREITO (Calendário) ---
        right_frame = ctk.CTkFrame(main_paned)
        right_frame.pack(side="right", fill="both", expand=True)

        # --- Conteúdo do Painel Esquerdo ---
        # Botão de Adicionar Funcionário no TOPO
        add_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=5)
        
        def adicionar_func_action():
            dialog = ctk.CTkInputDialog(text="Nome do Funcionário:", title="Novo Funcionário")
            nome = dialog.get_input()
            if nome and self.current_user:
                try:
                    self.core.adicionar_funcionario(nome, self.current_user['username'])
                    self.refresh_lista_funcionarios()
                except Exception as e:
                    messagebox.showerror("Erro", str(e))

        ctk.CTkButton(add_frame, text="+ Novo Funcionário", command=adicionar_func_action, fg_color=self.colors["calendario"]).pack(fill="x")

        # Área de Tarefas do Dia
        ctk.CTkLabel(left_frame, text="Tarefas do Dia", font=("Arial", 14, "bold")).pack(pady=(15, 5))
        self.lbl_data_selecionada = ctk.CTkLabel(left_frame, text="Selecione uma data", text_color="gray")
        self.lbl_data_selecionada.pack(pady=5)

        # Inputs para nova tarefa
        self.combo_funcionarios = ctk.CTkComboBox(left_frame, width=250, values=["Nenhum"])
        self.combo_funcionarios.pack(pady=5)
        self.e_obs_agenda = ctk.CTkEntry(left_frame, width=250, placeholder_text="Tarefa / Turno")
        self.e_obs_agenda.pack(pady=5)
        ctk.CTkButton(left_frame, text="Adicionar Tarefa", fg_color=self.colors["sucesso"], command=self.agendar_funcionario_selecionado).pack(pady=5)

        # Lista de Tarefas do Dia (Interativo)
        self.tree_tarefas_dia = ttk.Treeview(left_frame, columns=("ID", "Func", "Obs"), show="headings", height=15)
        self.tree_tarefas_dia.heading("ID", text="#"); self.tree_tarefas_dia.column("ID", width=0, stretch=False) # Oculto
        self.tree_tarefas_dia.heading("Func", text="Funcionário"); self.tree_tarefas_dia.column("Func", width=120)
        self.tree_tarefas_dia.heading("Obs", text="Tarefa"); self.tree_tarefas_dia.column("Obs", width=150)
        self.tree_tarefas_dia.pack(fill="both", expand=True, padx=5, pady=10)
        
        # Botão de remover tarefa
        ctk.CTkButton(left_frame, text="Remover Tarefa Selecionada", fg_color=self.colors["perigo"], command=self.remover_agendamento_selecionado).pack(pady=10)

        # --- Conteúdo do Painel Direito ---
        is_dark = ctk.get_appearance_mode() == "Dark"
        cal_bg = "#1f2937" if is_dark else "#ffffff"
        cal_fg = "#f3f4f6" if is_dark else "#1f2937"
        cal_sel_bg = self.colors["calendario"]
        
        self.calendario = Calendar(right_frame, selectmode='day', date_pattern='dd/mm/yyyy',
                                   background=cal_bg, foreground=cal_fg,
                                   headersbackground=cal_bg, headersforeground=cal_fg,
                                   normalbackground=cal_bg, normalforeground=cal_fg,
                                   weekendbackground=cal_bg, weekendforeground=cal_fg,
                                   othermonthbackground="#374151" if is_dark else "#e5e7eb",
                                   othermonthwebackground="#374151" if is_dark else "#e5e7eb",
                                   selectbackground=cal_sel_bg,
                                   font=("Arial", 12),
                                   locale='pt_BR')
        self.calendario.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.calendario.bind("<<CalendarSelected>>", self.atualizar_data_selecionada_calendario)
        self.calendario.bind("<<CalendarMonthChanged>>", lambda e: self.refresh_eventos_calendario())

        # Inicialização
        self.refresh_lista_funcionarios()
        self.refresh_eventos_calendario()
        self.atualizar_data_selecionada_calendario(None) # Seta a data inicial

    def refresh_lista_funcionarios(self):
        if not self.combo_funcionarios: return
        
        # Busca
        self.funcionarios_cache = [dict(f) for f in self.core.get_funcionarios()]
        nomes_funcionarios = [f['nome'] for f in self.funcionarios_cache]
        
        self.combo_funcionarios.configure(values=["Nenhum"] + nomes_funcionarios)
        self.combo_funcionarios.set("Nenhum")

    def refresh_eventos_calendario(self):
        if not self.calendario: return
        
        # Limpa eventos antigos
        self.calendario.calevent_remove('all')
        
        # Busca novos eventos
        cal_date = self.calendario.get_date() # '2/3/2026'
        dt_obj = datetime.strptime(cal_date, '%d/%m/%Y')
        
        eventos = self.core.get_agenda_mes(dt_obj.year, dt_obj.month)
        # eventos é dict {data_iso: "Func1, Func2"}
        
        for data_iso, nomes in eventos.items():
            event_dt = datetime.strptime(data_iso, '%Y-%m-%d')
            self.calendario.calevent_create(event_dt, "Tarefas", 'func_agenda')
            
        self.calendario.tag_config('func_agenda', background=self.colors["calendario"], foreground='white')

    def atualizar_data_selecionada_calendario(self, event):
        if not self.calendario or not self.lbl_data_selecionada or not self.tree_tarefas_dia: return
        data_selecionada = self.calendario.get_date()
        self.lbl_data_selecionada.configure(text=f"Data: {data_selecionada}")
        
        # Limpa lista lateral
        self.tree_tarefas_dia.delete(*self.tree_tarefas_dia.get_children())
        
        # Busca tarefas do dia
        try:
            data_iso = datetime.strptime(data_selecionada, '%d/%m/%Y').strftime('%Y-%m-%d')
            tarefas = self.core.get_tarefas_dia(data_iso)
            for t in tarefas:
                self.tree_tarefas_dia.insert("", "end", values=(t['id'], t['nome'], t['obs']))
        except Exception as e:
            print(f"Erro ao buscar agendamento: {e}")

    def agendar_funcionario_selecionado(self):
        if not self.calendario or not self.combo_funcionarios or not self.e_obs_agenda or not self.current_user: return
        
        nome_func = self.combo_funcionarios.get()
        if nome_func == "Nenhum":
            messagebox.showwarning("Aviso", "Selecione um funcionário para agendar.")
            return
            
        # Encontra o ID do funcionário
        func_id = None
        for f in self.funcionarios_cache:
            if f['nome'] == nome_func:
                func_id = f['id']
                break
        
        if func_id is None:
            messagebox.showerror("Erro", "Funcionário não encontrado no cache.")
            return
            
        data_str = self.calendario.get_date()
        data_iso = datetime.strptime(data_str, '%d/%m/%Y').strftime('%Y-%m-%d')
        obs = self.e_obs_agenda.get()
        
        try:
            self.core.salvar_agendamento(data_iso, func_id, obs, self.current_user['username'])
            self.refresh_eventos_calendario()
            self.atualizar_data_selecionada_calendario(None) # Atualiza lista lateral
            self.e_obs_agenda.delete(0, 'end')
        except Exception as e:
            messagebox.showerror("Erro ao Agendar", str(e))

    def remover_agendamento_selecionado(self):
        if not self.tree_tarefas_dia or not self.current_user: return
        
        sel = self.tree_tarefas_dia.selection()
        if not sel: return
        
        item = self.tree_tarefas_dia.item(sel[0])
        agenda_id = item['values'][0]
        
        if messagebox.askyesno("Confirmar", "Deseja remover esta tarefa?"):
            try:
                self.core.remover_agendamento_id(agenda_id, self.current_user['username'])
                self.refresh_eventos_calendario()
                self.atualizar_data_selecionada_calendario(None)
            except Exception as e:
                messagebox.showerror("Erro ao Remover", str(e))

    # =========================================================================
    # 7. MÓDULO LANÇAMENTOS (Central)
    # =========================================================================
    def tela_financeiro(self) -> None:
        self.current_screen_function = self.tela_financeiro
        self.current_screen_args = ()
        self.current_screen_kwargs = {}

        self.limpar_tela()
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent"); nav.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkLabel(nav, text="CENTRAL FINANCEIRA", font=("Arial", 18, "bold"), text_color=self.colors["financeiro"]).pack(side="left", padx=20)

        def acao_exportar():
            dialog = ctk.CTkInputDialog(text="Digite o Mês/Ano (MM/AAAA) para filtrar\nou deixe vazio para exportar TUDO:", title="Exportar Relatório")
            mes = dialog.get_input()
            # Se o usuário cancelar (None), não faz nada. Se for vazio (""), exporta tudo.
            if mes is not None:
                arquivo = self.core.exportar_historico_financeiro_csv(mes.strip() if mes.strip() else None)
                messagebox.showinfo("Exportado", f"Relatório salvo em:\n{arquivo}")

        def acao_fechamento():
            dialog = ctk.CTkInputDialog(text="Digite a Data (DD/MM/AAAA) para o fechamento\n(Deixe vazio para HOJE):", title="Fechamento de Caixa")
            data_str = dialog.get_input()
            if data_str is not None:
                try:
                    data_iso = datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d") if data_str.strip() else datetime.now().strftime("%Y-%m-%d")
                    arquivo = self.core.gerar_pdf_fechamento(data_iso)
                    messagebox.showinfo("Sucesso", f"Relatório gerado:\n{arquivo}")
                except Exception as e: messagebox.showerror("Erro", str(e))

        ctk.CTkButton(nav, text="🖨️ Fechamento Dia", width=140, fg_color="#2c3e50", command=acao_fechamento).pack(side="right", padx=5)
        ctk.CTkButton(nav, text="📥 Exportar Extrato", width=160, fg_color=self.colors["financeiro"], command=acao_exportar).pack(side="right", padx=5)
        ctk.CTkButton(nav, text="+ Novo Lançamento", width=160, fg_color=self.colors["financeiro"], text_color="white", hover_color=self.colors["financeiro_hover"], command=self.janela_novo_lancamento_central).pack(side="right")

        # Sistema de Abas
        tabview = ctk.CTkTabview(self.main_frame)
        tabview.pack(fill="both", expand=True, padx=10, pady=5)
        tab_creditos = tabview.add("Extrato de Créditos")
        tab_multas_hist = tabview.add("Histórico de Multas")

        # --- ABA 1: EXTRATO DE CRÉDITOS ---
        self.ent_busca_lanc = ctk.CTkEntry(tab_creditos, placeholder_text="Filtrar por nome ou documento...", width=500)
        self.ent_busca_lanc.pack(pady=10)
        
        # Treeview
        self.tree_l = ttk.Treeview(tab_creditos, columns=("ID", "Data", "Nome", "Tipo", "Valor", "Categoria", "Usuario"), show='headings')
        self.tree_l.heading("ID", text="ID"); self.tree_l.column("ID", width=50, anchor="center")
        self.tree_l.heading("Data", text="Data"); self.tree_l.column("Data", width=100, anchor="center")
        self.tree_l.heading("Nome", text="Cliente"); self.tree_l.column("Nome", width=250)
        self.tree_l.heading("Tipo", text="Tipo"); self.tree_l.column("Tipo", width=100, anchor="center")
        self.tree_l.heading("Valor", text="Valor"); self.tree_l.column("Valor", width=100, anchor="center")
        self.tree_l.heading("Categoria", text="Cat/Motivo"); self.tree_l.column("Categoria", width=150)
        self.tree_l.heading("Usuario", text="Resp."); self.tree_l.column("Usuario", width=100, anchor="center")
        
        self.tree_l.pack(expand=True, fill="both", padx=15, pady=10)
        self.configurar_tags_tabela(self.tree_l)

        # Context Menu for Deletion
        self.menu_lanc = ctk.CTkFrame(self, width=150, height=50, border_width=1)
        ctk.CTkButton(self.menu_lanc, text="Excluir Lançamento", command=self.excluir_lancamento_selecionado, fg_color="transparent", text_color="red", anchor="w").pack(fill="x")
        
        def show_menu(event: object) -> None:
            selection = self.tree_l.identify_row(event.y)
            if selection:
                self.tree_l.selection_set(selection)
                self.menu_lanc.place(x=event.x_root - self.winfo_x(), y=event.y_root - self.winfo_y())
                self.menu_lanc.lift()

        self.tree_l.bind("<Button-3>", show_menu)
        self.bind("<Button-1>", lambda e: self.menu_lanc.place_forget())

        self.ent_busca_lanc.bind("<KeyRelease>", lambda e: self.atualizar_lista_lancamentos())
        self.atualizar_lista_lancamentos()

        # --- ABA 2: HISTÓRICO DE MULTAS ---
        ent_busca_multas = ctk.CTkEntry(tab_multas_hist, placeholder_text="Filtrar por nome ou documento...", width=500)
        ent_busca_multas.pack(pady=10)
        
        tree_m = ttk.Treeview(tab_multas_hist, columns=("ID", "Data", "Nome", "Tipo", "Valor", "Categoria", "Usuario"), show='headings')
        tree_m.heading("ID", text="ID"); tree_m.column("ID", width=50, anchor="center")
        tree_m.heading("Data", text="Data"); tree_m.column("Data", width=100, anchor="center")
        tree_m.heading("Nome", text="Cliente"); tree_m.column("Nome", width=250)
        tree_m.heading("Tipo", text="Tipo"); tree_m.column("Tipo", width=120, anchor="center")
        tree_m.heading("Valor", text="Valor"); tree_m.column("Valor", width=100, anchor="center")
        tree_m.heading("Categoria", text="Cat/Motivo"); tree_m.column("Categoria", width=150)
        tree_m.heading("Usuario", text="Resp."); tree_m.column("Usuario", width=100, anchor="center")
        
        tree_m.pack(expand=True, fill="both", padx=15, pady=10)
        self.configurar_tags_tabela(tree_m)

        def atualizar_lista_multas() -> None:
            tree_m.delete(*tree_m.get_children())
            filtro = ent_busca_multas.get()
            dados = self.core.get_historico_global(filtro, tipos=('MULTA', 'PAGAMENTO_MULTA'))
            for i, d in enumerate(dados):
                data_br = datetime.strptime(d['data_acao'], "%Y-%m-%d").strftime("%d/%m/%Y")
                tags = ['odd' if i % 2 != 0 else 'even']
                if d['tipo'] == 'MULTA': tags.append('multa')
                if d['tipo'] == 'PAGAMENTO_MULTA': tags.append('pagamento_multa')
                
                tree_m.insert("", "end", values=(d['id'], data_br, d['nome'], d['tipo'], f"{d['valor']:.2f}", d['categoria'], d['usuario']), tags=tags)

        ent_busca_multas.bind("<KeyRelease>", lambda e: atualizar_lista_multas())
        atualizar_lista_multas()


    def atualizar_lista_lancamentos(self) -> None:
        self.tree_l.delete(*self.tree_l.get_children())
        filtro = self.ent_busca_lanc.get()
        dados = self.core.get_historico_global(filtro, tipos=('ENTRADA', 'SAIDA'))
        for i, d in enumerate(dados):
            data_br = datetime.strptime(d['data_acao'], "%Y-%m-%d").strftime("%d/%m/%Y")
            tags = ['odd' if i % 2 != 0 else 'even']
            if d['tipo'] == 'SAIDA': tags.append('saida')
            if d['tipo'] == 'MULTA': tags.append('multa')
            if d['tipo'] == 'PAGAMENTO_MULTA': tags.append('pagamento_multa')
            
            self.tree_l.insert("", "end", values=(d['id'], data_br, d['nome'], d['tipo'], f"{d['valor']:.2f}", d['categoria'], d['usuario']), tags=tags)

    def excluir_lancamento_selecionado(self) -> None:
        self.menu_lanc.place_forget()
        if not self.current_user or not self.current_user['is_admin']:
            messagebox.showerror("Acesso Negado", "Apenas administradores podem excluir lançamentos.")
            return
        
        sel = self.tree_l.selection()
        if not sel: return
        item = self.tree_l.item(sel[0])
        id_mov = item['values'][0]
        
        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o lançamento ID {id_mov}?"):
            try:
                self.core.excluir_movimentacao(id_mov, self.current_user['username'])
                self.atualizar_lista_lancamentos()
                messagebox.showinfo("Sucesso", "Lançamento excluído.")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    # =========================================================================
    # 8. MÓDULO CONFIGURAÇÕES & ADMIN
    # =========================================================================
    def tela_config(self) -> None:
        self.current_screen_function = self.tela_config
        self.current_screen_args = ()
        self.current_screen_kwargs = {}

        self.limpar_tela()
        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent"); nav.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left") # type: ignore
        
        def toggle_theme():
            new_mode = "Dark" if ctk.get_appearance_mode() == "Light" else "Light"
            ctk.set_appearance_mode(new_mode)
            self.setup_custom_styles()
            self.core.set_config('tema', 1 if new_mode == "Dark" else 0, self.current_user['username'])
            
            # Força o redesenho completo da tela atual para aplicar todas as mudanças de estilo
            if self.current_screen_function:
                self.current_screen_function(*self.current_screen_args, **self.current_screen_kwargs)

        icon = "🌙" if ctk.get_appearance_mode() == "Light" else "☀️"
        btn_tema = ctk.CTkButton(nav, text=f"{icon} Tema", width=100, fg_color="#555", command=toggle_theme)
        btn_tema.pack(side="right")
        
        if self.current_user['is_admin'] or self.current_user.get('can_manage_products'):
            self.config_admin_view()
        else:
            self.config_user_view()

        # --- Frame de Versão e Atualização (Visível para todos) ---
        f_versao = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_versao.pack(side="bottom", fill="x", padx=10, pady=10)

        ctk.CTkLabel(f_versao, text=f"Versão do Sistema: {self.core.versao_atual}").pack(side="left", padx=10)
        ctk.CTkButton(f_versao, text="Verificar Atualizações", command=self.verificar_update_manual).pack(side="right", padx=10)

    def config_admin_view(self) -> None:
        # --- Sistema de Abas para melhor organização ---
        tabview = ctk.CTkTabview(self.main_frame, segmented_button_selected_color=self.colors["ajustes"])
        tabview.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Inicializa variáveis para evitar erro de referência (unbound variable)
        tab_sistema = tab_usuarios = tab_categorias = tab_auditoria = tab_produtos = None
        
        # Adiciona abas conforme permissão
        if self.current_user['is_admin']:
            tab_sistema = tabview.add("Sistema")
            tab_usuarios = tabview.add("Usuários")
            tab_categorias = tabview.add("Categorias")
            tab_auditoria = tabview.add("Auditoria")
        
        if self.current_user['is_admin'] or self.current_user.get('can_manage_products'):
            tab_produtos = tabview.add("Produtos")

        # --- ABA 1: SISTEMA (Configs, Backup) ---
        if self.current_user['is_admin']:
            f_grid = ctk.CTkFrame(tab_sistema, fg_color="transparent"); f_grid.pack(pady=10, padx=20, anchor="w")
            ctk.CTkLabel(f_grid, text="Validade (Meses):").grid(row=0, column=0, padx=5)
            ev = ctk.CTkEntry(f_grid, width=50); ev.insert(0, str(self.core.get_config('validade_meses'))); ev.grid(row=0, column=1, padx=5)
            
            ctk.CTkLabel(f_grid, text="Alerta (Dias):").grid(row=0, column=2, padx=5)
            ea = ctk.CTkComboBox(f_grid, values=["15", "30", "60", "90"], width=60)
            ea.set(str(self.core.get_config('alerta_dias'))); ea.grid(row=0, column=3, padx=5)
            
            ctk.CTkButton(tab_sistema, text="Salvar Configurações", height=30, fg_color=self.colors["ajustes"], command=lambda: [
                self.core.set_config('validade_meses', int(ev.get()), self.current_user['username']), 
                self.core.set_config('alerta_dias', int(ea.get()), self.current_user['username']), 
                messagebox.showinfo("Sucesso", "Configurações salvas!"),
                self.tela_dash()
            ]).pack(pady=10, padx=20, anchor="w")

            f_backup = ctk.CTkFrame(tab_sistema, fg_color="transparent"); f_backup.pack(pady=20, padx=20, anchor="w")
            ctk.CTkButton(f_backup, text="Fazer Backup do Banco", height=30, fg_color=self.colors["aviso"], command=lambda: [
                self.core.fazer_backup(),
                messagebox.showinfo("Backup", "Backup realizado com sucesso na pasta 'backups'!")
            ]).pack(side="left", padx=5)

            def restaurar():
                path = filedialog.askopenfilename(filetypes=[("Banco de Dados", "*.db")])
                if path:
                    if messagebox.askyesno("Confirmar", "Isso substituirá os dados atuais pelos do backup. Continuar?"):
                        try: self.core.restaurar_backup(path, self.current_user['username']); messagebox.showinfo("Sucesso", "Backup restaurado! Reinicie o sistema.")
                        except Exception as e: messagebox.showerror("Erro", str(e))
            ctk.CTkButton(f_backup, text="Restaurar Backup", height=30, fg_color=self.colors["perigo"], command=restaurar).pack(side="left", padx=5)
            
            ctk.CTkButton(f_backup, text="🧹 Otimizar Banco", height=30, fg_color="#2c3e50", command=lambda: [
                self.core.otimizar_banco(),
                messagebox.showinfo("Sucesso", "Banco de dados otimizado e compactado!")
            ]).pack(side="left", padx=5)

        # --- ABA 2: USUÁRIOS ---
        f_form = ctk.CTkFrame(tab_usuarios, fg_color="transparent"); f_form.pack(pady=10, fill="x", padx=10)
        eu_user = ctk.CTkEntry(f_form, placeholder_text="Usuário"); eu_user.pack(side="left", padx=5)
        eu_pass = ctk.CTkEntry(f_form, placeholder_text="Senha"); eu_pass.pack(side="left", padx=5)
        chk_admin = ctk.CTkCheckBox(f_form, text="Admin"); chk_admin.pack(side="left", padx=5)
        chk_dates = ctk.CTkCheckBox(f_form, text="Alterar Datas"); chk_dates.pack(side="left", padx=5)
        chk_products = ctk.CTkCheckBox(f_form, text="Gerir Produtos"); chk_products.pack(side="left", padx=5)
        
        tv_u = ttk.Treeview(tab_usuarios, columns=("U", "A", "D"), show='headings', height=8)
        tv_u.heading("U", text="Usuário"); tv_u.heading("A", text="Admin"); tv_u.heading("D", text="Pode Alterar Datas")
        tv_u.column("U", anchor="center"); tv_u.column("A", anchor="center"); tv_u.column("D", anchor="center")
        tv_u.pack(fill="both", expand=True, padx=10, pady=5)
        self.configurar_tags_tabela(tv_u)

        def refresh_users() -> None:
            tv_u.delete(*tv_u.get_children())
            for i, u in enumerate(self.core.get_usuarios()):
                tag = 'odd' if i % 2 != 0 else 'even'
                tv_u.insert("", "end", values=(u['username'], "Sim" if u['is_admin'] else "Não", "Sim" if u['can_change_dates'] else "Não"), tags=(tag,))

        def save_user(event=None):
            if not eu_user.get() or not eu_pass.get(): return
            self.core.salvar_usuario(eu_user.get(), eu_pass.get(), chk_admin.get(), chk_dates.get(), chk_products.get(), self.current_user['username'])
            refresh_users(); eu_user.delete(0, 'end'); eu_pass.delete(0, 'end')
            
        eu_pass.bind("<Return>", save_user)
        ctk.CTkButton(f_form, text="Salvar/Atualizar", command=save_user, fg_color=self.colors["ajustes"]).pack(side="left", padx=5)
        
        refresh_users()

        def del_user():
            sel = tv_u.selection()
            if not sel: return
            u = tv_u.item(sel[0])['values'][0]
            if u == 'gabriel': messagebox.showerror("Erro", "Não é possível excluir o superadmin."); return
            if messagebox.askyesno("Confirmar", f"Excluir {u}?"): self.core.excluir_usuario(u, self.current_user['username']); refresh_users()
        ctk.CTkButton(tab_usuarios, text="Excluir Selecionado", fg_color=self.colors["perigo"], command=del_user).pack(pady=10, anchor="e", padx=10)

        # --- ABA 3: CATEGORIAS ---
        if self.current_user['is_admin']:
            fc_top = ctk.CTkFrame(tab_categorias, fg_color="transparent"); fc_top.pack(fill="x", padx=10, pady=10)
            ec_cat = ctk.CTkEntry(fc_top, placeholder_text="Nova Categoria"); ec_cat.pack(side="left", padx=5, expand=True, fill="x")
            
            def add_c(event: object | None = None) -> None:
                self.core.adicionar_categoria(ec_cat.get()); ec_cat.delete(0, 'end'); refresh_c()
            ec_cat.bind("<Return>", add_c)
            ctk.CTkButton(fc_top, text="+", width=40, command=add_c, fg_color=self.colors["ajustes"]).pack(side="left")
            
            tv_c = ttk.Treeview(tab_categorias, columns=("C",), show="headings")
            tv_c.heading("C", text="Nome"); tv_c.pack(fill="x", padx=10, pady=5)
            self.configurar_tags_tabela(tv_c)

            def refresh_c() -> None:
                tv_c.delete(*tv_c.get_children())
                for i, c in enumerate(self.core.get_categorias()):
                    tag = 'odd' if i % 2 != 0 else 'even'
                    tv_c.insert("", "end", values=(c,), tags=(tag,))
            refresh_c()

            def del_c() -> None:
                if tv_c.selection(): self.core.remover_categoria(tv_c.item(tv_c.selection()[0])['values'][0]); refresh_c()
            ctk.CTkButton(tab_categorias, text="Remover Selecionada", height=25, fg_color=self.colors["perigo"], command=del_c).pack(pady=5, anchor="e", padx=10)

        # --- ABA PRODUTOS (NOVA) ---
        if self.current_user['is_admin'] or self.current_user.get('can_manage_products'):
            fp_top = ctk.CTkFrame(tab_produtos, fg_color="transparent"); fp_top.pack(fill="x", padx=10, pady=10)
            ep_prod = ctk.CTkEntry(fp_top, placeholder_text="Nome do Produto (Ex: Detergente 5L)"); ep_prod.pack(side="left", padx=5, expand=True, fill="x")
            
            def add_p(event: object | None = None) -> None:
                self.core.adicionar_produto_predefinido(ep_prod.get()); ep_prod.delete(0, 'end'); refresh_p()
            ep_prod.bind("<Return>", add_p)
            ctk.CTkButton(fp_top, text="+ Adicionar", width=100, command=add_p, fg_color=self.colors["ajustes"]).pack(side="left")
            
            tv_p = ttk.Treeview(tab_produtos, columns=("P",), show="headings")
            tv_p.heading("P", text="Produto"); tv_p.pack(fill="both", expand=True, padx=10, pady=5)
            self.configurar_tags_tabela(tv_p)

            def refresh_p() -> None:
                tv_p.delete(*tv_p.get_children())
                for i, p in enumerate(self.core.get_produtos_predefinidos()):
                    tag = 'odd' if i % 2 != 0 else 'even'
                    tv_p.insert("", "end", values=(p,), tags=(tag,))
            refresh_p()

            def del_p() -> None:
                if tv_p.selection(): self.core.remover_produto_predefinido(tv_p.item(tv_p.selection()[0])['values'][0]); refresh_p()
            ctk.CTkButton(tab_produtos, text="Remover Selecionado", height=25, fg_color=self.colors["perigo"], command=del_p).pack(pady=5, anchor="e", padx=10)

        # --- ABA 4: AUDITORIA ---
        if self.current_user['is_admin']:
            tv_log = ttk.Treeview(tab_auditoria, columns=("DH", "U", "A", "D", "M"), show='headings')
            tv_log.heading("DH", text="Data/Hora"); tv_log.column("DH", width=140)
            tv_log.heading("U", text="Usuário"); tv_log.column("U", width=100)
            tv_log.heading("A", text="Ação"); tv_log.column("A", width=150)
            tv_log.heading("D", text="Detalhes"); tv_log.column("D", width=350)
            tv_log.heading("M", text="Máquina"); tv_log.column("M", width=100)
            tv_log.pack(fill="both", expand=True, padx=10, pady=10)
            self.configurar_tags_tabela(tv_log)

            for i, log in enumerate(self.core.get_logs()):
                tag = 'odd' if i % 2 != 0 else 'even'
                tv_log.insert("", "end", values=(log['data_hora'], log['usuario'], log['acao'], log['detalhes'], log['maquina']), tags=(tag,))

    def config_user_view(self) -> None:
        f = ctk.CTkFrame(self.main_frame, width=400); f.pack(pady=50, ipady=20)
        ctk.CTkLabel(f, text="Alterar Minha Senha", font=("Arial", 16, "bold")).pack(pady=15)
        
        ep = ctk.CTkEntry(f, placeholder_text="Nova Senha", show="*", width=250); ep.pack(pady=10)
        epc = ctk.CTkEntry(f, placeholder_text="Confirmar Nova Senha", show="*", width=250); epc.pack(pady=10)
        
        def save_pass(event: object | None = None) -> None:
            p1 = ep.get()
            p2 = epc.get()
            if not p1: return
            if p1 != p2:
                messagebox.showerror("Erro", "As senhas não coincidem.")
                return
            
            u = self.current_user
            self.core.salvar_usuario(u['username'], p1, u['is_admin'], u['can_change_dates'], u.get('can_manage_products', 0), u['username'])
            messagebox.showinfo("Sucesso", "Senha alterada com sucesso!")
            ep.delete(0, 'end'); epc.delete(0, 'end')
            
        epc.bind("<Return>", save_pass)
        ctk.CTkButton(f, text="Atualizar Senha", command=save_pass, fg_color=self.colors["ajustes"]).pack(pady=20)

    # =========================================================================
    # 9. JANELAS DE DIÁLOGO (POPUPS & TOPLEVELS)
    # =========================================================================
    def janela_novo_lancamento_central(self) -> None:
        jan = ctk.CTkToplevel(self); jan.title("Novo Lançamento"); jan.geometry("500x650")
        jan.transient(self); jan.lift(); jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        
        ctk.CTkLabel(jan, text="1. Selecione o Cliente", font=("Arial", 14, "bold")).pack(pady=5)
        
        f_busca = ctk.CTkFrame(jan, fg_color="transparent"); f_busca.pack(fill="x", padx=10)
        e_busca = ctk.CTkEntry(f_busca, placeholder_text="Nome ou CPF/CNPJ"); e_busca.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f_busca, text="+ Novo Hóspede", width=100, command=self.janela_cadastro_hospede).pack(side="right", padx=5)
        
        # Treeview pequena para resultados
        tv_res = ttk.Treeview(jan, columns=("N", "D"), show="headings", height=5)
        tv_res.heading("N", text="Nome"); tv_res.column("N", width=250)
        tv_res.heading("D", text="Documento"); tv_res.column("D", width=150)
        tv_res.pack(fill="x", padx=10, pady=5)
        
        def buscar(e: object | None = None) -> None:
            tv_res.delete(*tv_res.get_children())
            for h in self.core.buscar_filtrado(e_busca.get()):
                tv_res.insert("", "end", values=(h[0], h[1]))
        
        ctk.CTkButton(f_busca, text="🔍", width=40, command=buscar).pack(side="left") # type: ignore
        e_busca.bind("<Return>", buscar)
        
        # Frame de Detalhes
        f_detalhes = ctk.CTkFrame(jan); f_detalhes.pack(fill="both", expand=True, padx=10, pady=10)
        
        lbl_cliente = ctk.CTkLabel(f_detalhes, text="Nenhum cliente selecionado", font=("Arial", 12))
        lbl_cliente.pack(pady=5)
        
        selected_doc = ctk.StringVar(value="")
        
        def selecionar_cliente(e: object) -> None:
            sel = tv_res.selection()
            if not sel: return
            vals = tv_res.item(sel[0])['values']
            selected_doc.set(str(vals[1]))
            s, v, b = self.core.get_saldo_info(selected_doc.get())
            div = self.core.get_divida_multas(selected_doc.get())
            lbl_cliente.configure(text=f"Cliente: {vals[0]}\nSaldo: R$ {s:.2f} | Dívida: R$ {div:.2f}")
            
        tv_res.bind("<ButtonRelease-1>", selecionar_cliente)
        
        ctk.CTkLabel(f_detalhes, text="2. Dados do Lançamento", font=("Arial", 14, "bold")).pack(pady=5)
        
        # Refatoração: Atualização dinâmica dos campos baseada no tipo
        def atualizar_opcoes_categoria() -> None:
            tipo = tipo_var.get()
            if tipo == "ENTRADA":
                e_cat.configure(values=self.core.get_categorias())
                e_cat.set("Selecione a Categoria")
            elif tipo == "SAIDA":
                e_cat.configure(values=["Uso", "Consumo", "Serviço"])
                e_cat.set("Uso")
            elif tipo == "MULTA":
                e_cat.configure(values=["Danos", "Atraso", "Fumar no Quarto", "Outros"])
                e_cat.set("Motivo da Multa")
            elif tipo == "PAGAMENTO_MULTA":
                e_cat.configure(values=["Dinheiro", "PIX", "Cartão"])
                e_cat.set("Forma de Pagamento")

        tipo_var = ctk.StringVar(value="ENTRADA")
        f_tipo = ctk.CTkFrame(f_detalhes, fg_color="transparent"); f_tipo.pack(pady=5)
        
        opcoes_radio = [("Crédito", "ENTRADA", self.colors["sucesso"], 0, 0), ("Uso (Baixa)", "SAIDA", self.colors["perigo"], 0, 1),
                        ("Multa", "MULTA", self.colors["aviso"], 1, 0), ("Pgto Multa", "PAGAMENTO_MULTA", self.colors["sucesso_hover"], 1, 1)]
        
        for txt, val, col, r, c in opcoes_radio:
            ctk.CTkRadioButton(f_tipo, text=txt, variable=tipo_var, value=val, fg_color=col, command=atualizar_opcoes_categoria).grid(row=r, column=c, padx=5, pady=5)
        
        e_valor = ctk.CTkEntry(f_detalhes, placeholder_text="Valor (R$)"); e_valor.pack(pady=5)
        e_cat = ctk.CTkComboBox(f_detalhes, values=self.core.get_categorias()); e_cat.pack(pady=5)
        e_obs = ctk.CTkTextbox(f_detalhes, height=60); e_obs.pack(pady=5, fill="x", padx=20); e_obs.insert("1.0", "Observação...")
        
        def confirmar(event: object | None = None) -> None:
            if not self.current_user: return
            if not selected_doc.get(): messagebox.showwarning("Atenção", "Selecione um cliente primeiro."); return
            t, v, c, o, u = tipo_var.get(), e_valor.get(), e_cat.get(), e_obs.get("1.0", "end-1c"), self.current_user['username']
            try:
                if t == "ENTRADA": self.core.adicionar_movimentacao(selected_doc.get(), v, c, "ENTRADA", o, u)
                elif t == "SAIDA": self.core.adicionar_movimentacao(selected_doc.get(), v, "Uso", "SAIDA", o, u)
                elif t == "MULTA": self.core.adicionar_multa(selected_doc.get(), v, c, o, u)
                elif t == "PAGAMENTO_MULTA": self.core.pagar_multa(selected_doc.get(), v, c, o, u)
                messagebox.showinfo("Sucesso", "Lançamento realizado!"); jan.destroy(); self.tela_financeiro()
            except Exception as e: messagebox.showerror("Erro", str(e))
        
        e_valor.bind("<Return>", confirmar)
        ctk.CTkButton(f_detalhes, text="CONFIRMAR LANÇAMENTO", fg_color=self.colors["financeiro"], height=40, command=confirmar).pack(pady=10, fill="x", padx=20)

    def janela_calendario_vencimento(self, event: object, doc: str, nome: str) -> None:
        # Verificação de permissão melhorada: permite se for admin ou tiver a permissão específica
        if not self.current_user or \
           (not self.current_user.get('is_admin') and not self.current_user.get('can_change_dates')):
            messagebox.showerror("Acesso Negado", "Você não tem permissão para alterar datas.")
            return

        try:
            from tkcalendar import DateEntry
        except ImportError:
            messagebox.showerror("Erro", "Biblioteca 'tkcalendar' não instalada.\nImpossível abrir calendário.")
            return

        item = self.tree_z.identify_row(event.y)
        if not item: return
        self.tree_z.selection_set(item)
        id_mov, tp, val, dt_mov, *_ = self.tree_z.item(item)['values']
        if tp != "ENTRADA": return
        jan = ctk.CTkToplevel(self); jan.title("Ajustar Data"); jan.geometry("300x320")
        jan.transient(self); jan.lift(); jan.focus_force()
        # Garante foco e modalidade após renderização completa
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        
        cal = DateEntry(jan, width=12, background='darkblue', date_pattern='dd/mm/yyyy'); cal.pack(pady=20)
        def ok() -> None:
            self.core.atualizar_data_vencimento_manual(id_mov, cal.get(), self.current_user['username'])
            jan.destroy(); self.tela_historico(nome, doc)
        ctk.CTkButton(jan, text="Atualizar Vencimento", command=ok).pack(pady=10)

    def janela_logs(self) -> None:
        jan = ctk.CTkToplevel(self); jan.title("Logs de Auditoria"); jan.geometry("900x500")
        jan.transient(self); jan.lift(); jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        tv = ttk.Treeview(jan, columns=("DH", "U", "A", "D", "M"), show='headings')
        tv.heading("DH", text="Data/Hora"); tv.column("DH", width=140)
        tv.heading("U", text="Usuário"); tv.column("U", width=100)
        tv.heading("A", text="Ação"); tv.column("A", width=150)
        tv.heading("D", text="Detalhes"); tv.column("D", width=350)
        tv.heading("M", text="Máquina"); tv.column("M", width=100)
        tv.pack(fill="both", expand=True)
        
        for log in self.core.get_logs():
            tv.insert("", "end", values=(log['data_hora'], log['usuario'], log['acao'], log['detalhes'], log['maquina']))

    def janela_cadastro_hospede(self, doc_to_edit: str | None = None) -> None:
        jan = ctk.CTkToplevel(self); jan.geometry("400x400")
        jan.transient(self); jan.lift(); jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])

        title = "Editar Hóspede" if doc_to_edit else "Novo Hóspede"
        jan.title(title)
        ctk.CTkLabel(jan, text=title, font=("Arial", 16, "bold")).pack(pady=15)

        en = ctk.CTkEntry(jan, placeholder_text="Nome Completo", width=350); en.pack(pady=10)
        ed = ctk.CTkEntry(jan, placeholder_text="CPF ou CNPJ", width=300); ed.pack(pady=10)
        etel = ctk.CTkEntry(jan, placeholder_text="Telefone (WhatsApp)", width=300); etel.pack(pady=10)
        eemail = ctk.CTkEntry(jan, placeholder_text="E-mail", width=300); eemail.pack(pady=10)

        if doc_to_edit:
            hospede = self.core.get_hospede(doc_to_edit)
            if hospede:
                en.insert(0, hospede['nome'])
                ed.insert(0, hospede['documento'])
                ed.configure(state="disabled") # Não permite editar o documento
                etel.insert(0, hospede['telefone'] or "")
                eemail.insert(0, hospede['email'] or "")

        def salvar(event: object | None = None) -> None:
            user = self.current_user['username'] if self.current_user else "Sistema"
            try:
                self.core.cadastrar_hospede(en.get(), ed.get(), etel.get(), eemail.get(), usuario_acao=user)
                jan.destroy()
                # Atualiza a tela atual para refletir a mudança (seja a lista de hóspedes ou o histórico)
                if self.current_screen_function:
                    self.current_screen_function(*self.current_screen_args, **self.current_screen_kwargs)
            except Exception as e: messagebox.showerror("Erro", str(e))
        
        en.bind("<Return>", salvar)
        ed.bind("<Return>", salvar)
        etel.bind("<Return>", salvar)
        eemail.bind("<Return>", salvar)
        ctk.CTkButton(jan, text="Salvar", fg_color=self.colors["hospedes"], width=300, command=salvar).pack(pady=20)

    def _janela_movimentacao(self, title: str, doc: str, nome: str, tipo_mov: str, callback: callable) -> None:
        jan = ctk.CTkToplevel(self); jan.title(title); jan.geometry("350x350")
        jan.transient(self); jan.lift(); jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        ctk.CTkLabel(jan, text=title, font=("Arial", 16, "bold")).pack(pady=15)
        
        ev = ctk.CTkEntry(jan, placeholder_text="Valor (R$)", width=250); ev.pack(pady=10)
        
        label_cat = "Categoria"
        if tipo_mov == "MULTA": label_cat = "Motivo"
        elif tipo_mov == "PAGAMENTO_MULTA": label_cat = "Forma de Pagamento"
        
        ec = ctk.CTkComboBox(jan, values=self.core.get_categorias(), width=250) if tipo_mov == "ENTRADA" else ctk.CTkEntry(jan, placeholder_text=label_cat, width=250)
        ec.pack(pady=10)
        
        eo = ctk.CTkTextbox(jan, width=250, height=60); eo.pack(pady=10)
        
        def salvar(event: object | None = None) -> None:
            if not self.current_user: return
            user = self.current_user['username']
            try:
                callback(doc, ev.get(), ec.get(), eo.get("1.0", "end-1c"), user)
                jan.destroy()
                self.tela_historico(nome, doc)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=jan)

        ev.bind("<Return>", salvar)
        ctk.CTkButton(jan, text="Confirmar", command=salvar, fg_color=self.colors["sucesso"]).pack(pady=10)

    def janela_add_credito(self, doc: str, nome: str) -> None:
        def cb(d, v, c, o, u): self.core.adicionar_movimentacao(d, v, c, "ENTRADA", o, u)
        self._janela_movimentacao("Adicionar Crédito", doc, nome, "ENTRADA", cb)

    def janela_usar_credito(self, doc: str, nome: str) -> None:
        def cb(d, v, c, o, u): self.core.adicionar_movimentacao(d, v, "Uso", "SAIDA", o, u)
        self._janela_movimentacao("Utilizar Crédito", doc, nome, "SAIDA", cb)

    def janela_add_multa(self, doc: str, nome: str) -> None:
        def cb(d, v, m, o, u): self.core.adicionar_multa(d, v, m, o, u)
        self._janela_movimentacao("Adicionar Multa", doc, nome, "MULTA", cb)

    def janela_pagar_multa(self, doc: str, nome: str) -> None:
        def cb(d, v, m, o, u): self.core.pagar_multa(d, v, m, o, u)
        self._janela_movimentacao("Pagar Multa", doc, nome, "PAGAMENTO_MULTA", cb)

if __name__ == "__main__":
    try:
        app = AppHotelLTS()
        app.mainloop()
    except Exception as e:
        # --- TRATAMENTO GLOBAL DE ERROS (CRASH LOGGER) ---
        # Se o app falhar ao iniciar, grava o erro em um arquivo para debug
        app_data = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser('~')
        log_dir = os.path.join(app_data, "SistemaHotelSantos", "logs")
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"crash_log_{timestamp}.txt")
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"ERRO CRÍTICO NA INICIALIZAÇÃO - {datetime.now()}\n")
            f.write("-" * 50 + "\n")
            f.write(traceback.format_exc())
        
        # Tenta mostrar um alerta visual (se o Tkinter ainda estiver vivo/acessível)
        try: messagebox.showerror("Erro Fatal", f"O sistema encontrou um erro e precisou ser fechado.\n\nLog salvo em:\n{log_file}")
        except: pass