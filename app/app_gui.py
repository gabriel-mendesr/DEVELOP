import os
import sys
import threading
import traceback
import webbrowser
from collections.abc import Callable
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote

import customtkinter as ctk

# =============================================================================
# MUDANÇA 1 DE 3 — IMPORTS ATUALIZADOS
# =============================================================================
# ANTES: from sistema_clientes import SistemaCreditos
#   → sistema_clientes.py era o arquivo monolítico com 1116 linhas.
#
# DEPOIS: A lógica foi dividida em dois arquivos na pasta core/:
#   - core/database.py  → cria e migra o banco SQLite
#   - core/models.py    → todas as regras de negócio
#
# O Database precisa ser criado ANTES do SistemaCreditos (veja __init__).
from core.database import Database
from core.models import SistemaCreditos
from logger_system import LoggerSystem
from screens.compras import TelaCompras
from screens.config import TelaConfig
from screens.dashboard import TelaDashboard
from screens.financeiro import TelaFinanceiro
from screens.hospedes import TelaHospedes
from screens.relatorios import TelaRelatorios
from update_manager import UpdateManager

try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None


def resource_path(relative_path: str) -> str:
    """Obtém o caminho absoluto para recursos, funcionando para dev e PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class AppHotelLTS(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # --- Declaração de Atributos de Instância para Type Hinting ---
        self.core: SistemaCreditos
        self.logger: LoggerSystem
        self.update_manager: UpdateManager
        self.colors: dict[str, str]
        self.current_user: dict | None = None
        self.search_job: str | None = None
        self.current_screen_function: Callable[..., None] | None = None
        self.current_screen_args: tuple = ()
        self.current_screen_kwargs: dict = {}
        # Tela anterior — usada pelo botão "← Voltar"
        self._prev_screen_fn: Callable[..., None] | None = None
        self._prev_screen_args: tuple = ()
        self._prev_screen_kwargs: dict = {}

        # Widgets da UI principal
        self.sidebar: ctk.CTkFrame
        self.main_frame: ctk.CTkFrame
        self.btn_update: ctk.CTkButton
        self.btn_sair: ctk.CTkButton
        self.ent_busca_global: ctk.CTkEntry

        # Widgets da tela de Histórico (não migrada para screens/ ainda)
        self.tree_z: ttk.Treeview

        # Instâncias de telas migradas (screens/)
        self._tela_hospedes: TelaHospedes

        # Widgets da tela de Agenda
        # cal_agenda é o widget de calendário — guardado como atributo para
        # que refresh_lista_funcionarios e agendar_funcionario_selecionado
        # possam ler a data selecionada sem precisar de variáveis globais.
        self.cal_agenda: object | None = None
        self.combo_funcionarios: ctk.CTkComboBox | None = None
        self.e_obs_agenda: ctk.CTkEntry | None = None
        self.tree_tarefas_dia: ttk.Treeview | None = None
        self.lbl_data_selecionada: ctk.CTkLabel | None = None
        self.funcionarios_cache: list[dict] = []
        # --- Fim da Declaração ---

        # =======================================================================
        # MUDANÇA 2 DE 3 — INICIALIZAÇÃO DO CORE
        # =======================================================================
        # ANTES: self.core = SistemaCreditos()
        #   → SistemaCreditos criava a própria conexão internamente.
        #
        # DEPOIS: O banco é criado separadamente e injetado no SistemaCreditos.
        #   Isso é chamado "Injeção de Dependência":
        #   - Facilita testes (podemos injetar um banco na memória)
        #   - Separa responsabilidades: Database cuida do banco, SistemaCreditos cuida da lógica
        db = Database()
        self.core = SistemaCreditos(db)
        self.logger = LoggerSystem()
        # =======================================================================

        self.update_manager = UpdateManager()
        saved_theme = self.core.get_config("tema")

        # Aplicar tema ttk ANTES do ctk para evitar que theme_use("clam") dentro de
        # setup_custom_styles() seja chamado depois de ctk já ter configurado seus estilos,
        # o que resetaria o Treeview para branco ao reiniciar no modo escuro.
        _style = ttk.Style()
        try:
            _style.theme_use("clam")
        except Exception:
            pass

        ctk.set_appearance_mode("Dark" if saved_theme == 1 else "Light")
        ctk.set_default_color_theme("green")

        self.title(f"🏨 Hotel Santos - Gestão de Créditos v{self.core.versao_atual}")
        self.geometry("1200x850")
        self.minsize(1024, 768)

        try:
            import platform

            if platform.system() == "Windows":
                self.state("zoomed")
        except Exception:
            pass

        # --- PALETA DE CORES FOSCAS (MATTE) & SINGULARES ---
        self.colors = {
            "sucesso": "#059669",
            "sucesso_hover": "#047857",
            "perigo": "#dc2626",
            "perigo_hover": "#b91c1c",
            "aviso": "#d97706",
            "hospedes": "#7c3aed",
            "hospedes_hover": "#6d28d9",
            "financeiro": "#16a34a",
            "financeiro_hover": "#15803d",
            "compras": "#ea580c",
            "compras_hover": "#c2410c",
            "dashboard": "#2563eb",
            "dashboard_hover": "#1d4ed8",
            "ajustes": "#0d9488",
            "ajustes_hover": "#0f766e",
            "branco": "#f8fafc",
            "relatorios": "#7b1fa2",
            "relatorios_hover": "#6a1090",
            "notificacoes": "#0369a1",
            "notificacoes_hover": "#075985",
            "sidebar_bg": "#1e293b",
            "sidebar_txt": "#e2e8f0",
        }
        # Adia setup_custom_styles() para depois do mainloop iniciar — garante que
        # o tema ctk já esteja totalmente aplicado antes de configurar os estilos ttk.
        self.after(1, self.setup_custom_styles)
        # Reaplica estilos ttk automaticamente sempre que o tema mudar (Dark ↔ Light)
        ctk.AppearanceModeTracker.add(self.setup_custom_styles)

        try:
            self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=self.colors["sidebar_bg"])
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="H-SANTOS", font=("Arial", 22, "bold"), text_color=self.colors["sucesso"]).pack(
            pady=30
        )

        btn_opts = {"height": 40, "anchor": "w", "fg_color": "transparent", "text_color": self.colors["sidebar_txt"]}

        ctk.CTkButton(
            self.sidebar, text="🏠 Home", command=self.tela_home, hover_color=self.colors["ajustes_hover"], **btn_opts
        ).pack(pady=5, fill="x", padx=10)

        # Frame que conterá os botões de módulo — reconstruído após o login
        # para refletir as permissões do usuário logado.
        self.frame_sidebar_modulos = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_sidebar_modulos.pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#334155").pack(fill="x", padx=10, pady=5)

        self.ent_busca_global = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="🔍 Busca rápida...",
            width=160,
            fg_color="#334155",
            border_color="#475569",
            text_color=self.colors["sidebar_txt"],
            placeholder_text_color="#94a3b8",
        )
        self.ent_busca_global.pack(padx=10, pady=(0, 5))
        self.ent_busca_global.bind("<Return>", self._busca_global_enter)

        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(expand=True, fill="y")

        self.btn_update = ctk.CTkButton(
            self.sidebar,
            text="⬇️ Atualização",
            fg_color=self.colors["aviso"],
            hover_color="#b45309",
            text_color="#ffffff",
            anchor="center",
        )

        self.btn_sair = ctk.CTkButton(
            self.sidebar, text=" 🚪 Sair", command=self.logout, hover_color=self.colors["perigo_hover"], **btn_opts
        )
        self.btn_sair.pack(pady=20, fill="x", padx=10)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        self.tela_login()

    # =========================================================================
    # 1. SETUP & CORE (Estilos, Configurações Globais)
    # =========================================================================
    def setup_custom_styles(self) -> None:
        style = ttk.Style()

        is_dark = ctk.get_appearance_mode() == "Dark"

        # Atualiza as chaves de cor dependentes do tema; usadas por screens/base.py
        self.colors["bg_secondary"] = "#1f2937" if is_dark else "#f1f5f9"
        self.colors["text"] = "#f3f4f6" if is_dark else "#1f2937"
        self.colors["text_secondary"] = "#9ca3af" if is_dark else "#6b7280"
        self.colors["accent"] = "#1f6aa5"

        bg_color = "#1f2937" if is_dark else "#ffffff"
        fg_color = "#f3f4f6" if is_dark else "#1f2937"
        field_bg = "#374151" if is_dark else "#f8fafc"
        header_bg = "#111827" if is_dark else "#e2e8f0"
        selected_fg = "#ffffff"

        for style_name in ("Treeview", "Hotel.Treeview"):
            style.configure(
                style_name,
                background=bg_color,
                fieldbackground=field_bg,
                foreground=fg_color,
                rowheight=35,
                borderwidth=0,
            )
            style.configure(
                f"{style_name}.Heading",
                background=header_bg,
                foreground=fg_color,
                relief="flat",
                font=("Arial", 11, "bold"),
            )
            style.map(
                style_name,
                background=[("selected", self.colors["ajustes"])],
                foreground=[("selected", selected_fg)],
            )

        # Re-renderiza a tela atual para que as tabelas (Treeview) reflitam
        # imediatamente o novo tema — sem isso, os widgets já renderizados
        # não atualizam as cores automaticamente.
        if self.current_user and self.current_screen_function:
            try:
                self.current_screen_function(*self.current_screen_args, **self.current_screen_kwargs)
            except Exception:
                pass

    def configurar_tags_tabela(self, tree: ttk.Treeview) -> None:
        """Aplica configurações de cores para linhas pares, ímpares e saídas, adaptando-se ao tema."""
        is_dark = ctk.get_appearance_mode() == "Dark"

        if is_dark:
            odd_bg = "#1f2937"
            even_bg = "#2d3748"
        else:
            odd_bg = "#f8fafc"
            even_bg = "#ffffff"

        tree.tag_configure("odd", background=odd_bg)
        tree.tag_configure("even", background=even_bg)
        tree.tag_configure("saida", foreground=self.colors["perigo"])
        tree.tag_configure("multa", foreground=self.colors["aviso"])
        tree.tag_configure("pagamento_multa", foreground=self.colors["sucesso"])
        tree.tag_configure("seta_subiu", foreground=self.colors["perigo"])
        tree.tag_configure("seta_desceu", foreground=self.colors["sucesso"])

    def on_closing(self) -> None:
        """Encerra o processo de forma limpa"""
        try:
            ctk.AppearanceModeTracker.remove(self.setup_custom_styles)
        except Exception:
            pass
        try:
            # =======================================================================
            # MUDANÇA 3 DE 3 — BACKUP VIA db (NÃO MAIS VIA core)
            # =======================================================================
            # ANTES: self.core.fazer_backup()
            #   → fazer_backup() era um método do SistemaCreditos (sistema_clientes.py).
            #
            # DEPOIS: fazer_backup() é um método do Database (core/database.py).
            #   O SistemaCreditos expõe o banco como self.core.db, então:
            if hasattr(self, "core") and hasattr(self.core, "db"):
                self.core.db.fazer_backup()
        except Exception:
            pass
        self.quit()
        self.destroy()
        sys.exit()

    def _gerar_cores_funcionarios(self):
        """Gera paleta de cores para funcionários"""
        return [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#FFA07A",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E2",
            "#F8B739",
            "#52C9C0",
        ]

    def _obter_cor_funcionario(self, nome_func: str) -> str:
        """Obtém ou cria cor para um funcionário"""
        if not hasattr(self, "cores_funcionarios"):
            self.cores_funcionarios: dict[str, str] = {}
        if nome_func not in self.cores_funcionarios:
            cores = self._gerar_cores_funcionarios()
            idx = len(self.cores_funcionarios) % len(cores)
            self.cores_funcionarios[nome_func] = cores[idx]
        return self.cores_funcionarios[nome_func]

    def limpar_tela(self) -> None:
        for w in self.main_frame.winfo_children():
            w.destroy()
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)
        self.main_frame.grid_rowconfigure(0, weight=1)

    # =========================================================================
    # 1.5. NOTIFICAÇÕES & BACKUP AUTOMÁTICO
    # =========================================================================

    def notificar_vencimentos(self) -> None:
        """Exibe popup ao entrar com hóspedes vencendo em breve ou já vencidos."""
        vencendo = self.core.get_hospedes_vencendo_em_breve()
        vencidos = self.core.buscar_filtrado("", "vencidos")
        devedores = self.core.get_devedores_multas()

        if not vencendo and not vencidos and not devedores:
            return

        jan = ctk.CTkToplevel(self)
        jan.title("⚠️ Alertas do Sistema")
        jan.geometry("500x420")
        jan.transient(self)
        jan.lift()
        jan.grab_set()

        ctk.CTkLabel(jan, text="Alertas Pendentes", font=("Arial", 16, "bold")).pack(pady=15)

        scroll = ctk.CTkScrollableFrame(jan, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        if vencendo:
            ctk.CTkLabel(
                scroll,
                text=f"⚠️ {len(vencendo)} hóspede(s) com crédito vencendo em breve:",
                text_color=self.colors["aviso"],
                font=("Arial", 12, "bold"),
            ).pack(anchor="w", pady=(5, 2))
            for nome, venc, saldo in vencendo[:5]:
                ctk.CTkLabel(scroll, text=f"  • {nome}  →  {venc}  (R$ {saldo})", font=("Arial", 11)).pack(anchor="w")
            if len(vencendo) > 5:
                ctk.CTkLabel(scroll, text=f"  ... e mais {len(vencendo) - 5}", font=("Arial", 11)).pack(anchor="w")

        if vencidos:
            ctk.CTkLabel(
                scroll,
                text=f"🔴 {len(vencidos)} hóspede(s) com crédito VENCIDO:",
                text_color=self.colors["perigo"],
                font=("Arial", 12, "bold"),
            ).pack(anchor="w", pady=(10, 2))
            for nome, doc, saldo in vencidos[:5]:
                ctk.CTkLabel(scroll, text=f"  • {nome}", font=("Arial", 11)).pack(anchor="w")
            if len(vencidos) > 5:
                ctk.CTkLabel(scroll, text=f"  ... e mais {len(vencidos) - 5}", font=("Arial", 11)).pack(anchor="w")

        if devedores:
            ctk.CTkLabel(
                scroll,
                text=f"💸 {len(devedores)} hóspede(s) com multas em aberto:",
                text_color=self.colors["perigo"],
                font=("Arial", 12, "bold"),
            ).pack(anchor="w", pady=(10, 2))
            for nome, doc, tel, divida in devedores[:5]:
                ctk.CTkLabel(scroll, text=f"  • {nome}  →  R$ {divida:.2f}", font=("Arial", 11)).pack(anchor="w")
            if len(devedores) > 5:
                ctk.CTkLabel(scroll, text=f"  ... e mais {len(devedores) - 5}", font=("Arial", 11)).pack(anchor="w")

        ctk.CTkButton(jan, text="Entendido", width=120, command=jan.destroy).pack(pady=10)

    def fazer_backup_automatico(self) -> None:
        """Realiza backup silencioso ao abrir o sistema."""

        def _task():
            try:
                if hasattr(self, "core") and hasattr(self.core, "db"):
                    self.core.db.fazer_backup()
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()

    def _busca_global_enter(self, event: object | None = None) -> None:
        """Abre tela de hóspedes com busca pré-preenchida a partir da sidebar."""
        termo = self.ent_busca_global.get().strip()
        if not termo:
            return
        self.tela_hospedes()
        self._tela_hospedes.set_busca(termo)

    def _exportar_hospedes_csv(self) -> None:
        """Exporta lista de hóspedes para arquivo CSV escolhido pelo usuário."""
        caminho = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"hospedes_{datetime.now().strftime('%Y%m%d')}.csv",
        )
        if not caminho:
            return
        try:
            self.core.exportar_hospedes_csv(caminho)
            messagebox.showinfo("Exportado", f"Lista de hóspedes salva em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _exportar_relatorio_mensal_csv(self) -> None:
        """Exporta relatório financeiro do mês atual (ou escolhido pelo usuário) para CSV."""
        mes_atual = datetime.now().strftime("%m/%Y")
        dialog = ctk.CTkInputDialog(
            text="Mês/Ano para exportar (MM/AAAA):\nDeixe vazio para exportar TUDO.",
            title="Exportar Relatório Mensal",
        )
        mes = dialog.get_input()
        if mes is None:
            return
        mes_filtro = mes.strip() if mes.strip() else None
        caminho = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"relatorio_{(mes_filtro or mes_atual).replace('/', '-')}.csv",
        )
        if not caminho:
            return
        try:
            import shutil

            tmp = self.core.exportar_historico_financeiro_csv(mes_filtro)
            shutil.copy2(tmp, caminho)
            messagebox.showinfo("Exportado", f"Relatório salvo em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    # =========================================================================
    # 1.6. AUTO-UPDATE
    # =========================================================================
    def verificar_e_notificar_update(self) -> None:
        def _task():
            try:
                if not getattr(sys, "frozen", False):
                    self.logger.log_info("Verificação de update pulada (rodando como script).")
                    return
                tem_update, nova_versao, url = self.update_manager.verificar_atualizacao()
                if tem_update:
                    self.after(0, self.mostrar_botao_update, nova_versao, url)
            except Exception as e:
                self.logger.log_erro(e, "verificar_atualizacao")

        threading.Thread(target=_task, daemon=True).start()

    def mostrar_botao_update(self, nova_versao: str, url: str) -> None:
        self.btn_update.configure(
            text=f"⬇️ Atualizar v{nova_versao}", command=lambda: self.propor_atualizacao(nova_versao, url)
        )
        self.btn_update.pack(before=self.btn_sair, pady=10, fill="x", padx=10)

    def propor_atualizacao(self, nova_versao: str, url: str) -> None:
        if messagebox.askyesno(
            "Atualização Disponível",
            f"Uma nova versão ({nova_versao}) está disponível!\n"
            "Deseja baixar e instalar agora?\n\n"
            "O aplicativo será reiniciado.",
        ):
            self.iniciar_janela_de_progresso(url, nova_versao)

    def iniciar_janela_de_progresso(self, url: str, nova_versao: str) -> None:
        janela_progresso = ctk.CTkToplevel(self)
        janela_progresso.title("Atualizando...")
        janela_progresso.geometry("400x150")
        janela_progresso.transient(self)
        janela_progresso.lift()
        janela_progresso.grab_set()
        janela_progresso.protocol("WM_DELETE_WINDOW", lambda: None)
        ctk.CTkLabel(janela_progresso, text="Baixando nova versão, por favor aguarde...", font=("Arial", 14)).pack(
            pady=20
        )
        progress_bar = ctk.CTkProgressBar(janela_progresso, width=350)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        lbl_status = ctk.CTkLabel(janela_progresso, text="Iniciando download...")
        lbl_status.pack(pady=5)

        def update_callback(progress, status=None):
            progress_bar.set(progress)
            if status == "finalizando":
                lbl_status.configure(text="Atualização baixada! Reiniciando o aplicativo...")
                self.after(1500, lambda: os._exit(0))
            else:
                lbl_status.configure(text=f"{int(progress * 100)}%")

        self.update_manager.aplicar_atualizacao(
            url, nova_versao, progress_callback=lambda p, s=None: self.after(0, update_callback, p, s)
        )

    def verificar_update_manual(self) -> None:
        self.configure(cursor="watch")
        self.update_idletasks()

        def _task():
            try:
                if not getattr(sys, "frozen", False):
                    self.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Aviso", "A verificação de atualização só funciona no aplicativo compilado (instalador)."
                        ),
                    )
                    return
                tem_update, nova_versao, url = self.update_manager.verificar_atualizacao()
                if tem_update:
                    self.after(0, self.propor_atualizacao, nova_versao, url)
                else:
                    self.after(
                        0, lambda: messagebox.showinfo("Atualização", "Você já está usando a versão mais recente.")
                    )
            except Exception as e:
                self.after(
                    0,
                    lambda err=e: messagebox.showerror("Erro", f"Não foi possível verificar por atualizações:\n{err}"),
                )
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))

        threading.Thread(target=_task, daemon=True).start()

    # =========================================================================
    # 2. AUTENTICAÇÃO
    # =========================================================================
    def logout(self) -> None:
        if messagebox.askyesno("Sair", "Tem certeza que deseja sair?"):
            self.current_user = None
            self.tela_login()

    def tela_login(self) -> None:
        self.limpar_tela()
        self.sidebar.pack_forget()

        f = ctk.CTkFrame(self.main_frame, width=300, height=350)
        f.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(f, text="LOGIN", font=("Arial", 20, "bold")).pack(pady=30)

        eu = ctk.CTkEntry(f, placeholder_text="Usuário", width=200)
        eu.pack(pady=10)
        ep = ctk.CTkEntry(f, placeholder_text="Senha", show="*", width=200)
        ep.pack(pady=10)

        def tentar_login(event: object | None = None) -> None:
            u = self.core.verificar_login(eu.get(), ep.get())
            if u:
                self.current_user = u
                self.main_frame.pack_forget()
                self.sidebar.pack(side="left", fill="y")
                self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
                self._construir_botoes_sidebar_modulos()
                self.tela_home()
                self.after(500, self.notificar_vencimentos)
                self.after(1000, self.fazer_backup_automatico)
                self.after(2000, self.verificar_e_notificar_update)
            else:
                messagebox.showerror("Erro", "Credenciais inválidas")

        ep.bind("<Return>", tentar_login)
        ctk.CTkButton(
            f,
            text="Entrar",
            command=tentar_login,
            width=200,
            fg_color=self.colors["sucesso"],
            hover_color=self.colors["sucesso_hover"],
        ).pack(pady=20)

    # =========================================================================
    # 3. NAVEGAÇÃO PRINCIPAL
    # =========================================================================
    def _construir_botoes_sidebar_modulos(self) -> None:
        """Reconstrói os botões de módulo na sidebar conforme as permissões do usuário logado."""
        for w in self.frame_sidebar_modulos.winfo_children():
            w.destroy()

        u = self.current_user or {}
        is_admin = bool(u.get("is_admin", 0))
        btn_opts = {"height": 40, "anchor": "w", "fg_color": "transparent", "text_color": self.colors["sidebar_txt"]}

        # (texto, comando, hover_color, permission_key)
        modulos = [
            ("👥 Hóspedes", self.tela_hospedes, self.colors["hospedes_hover"], "can_access_hospedes"),
            ("💰 Financeiro", self.tela_financeiro, self.colors["financeiro_hover"], "can_access_financeiro"),
            ("🛒 Compras", self.tela_compras, self.colors["compras_hover"], "can_access_compras"),
            ("📊 Dashboard", self.tela_dash, self.colors["dashboard_hover"], "can_access_dash"),
            ("⚙️ Ajustes", self.tela_config, self.colors["ajustes_hover"], None),  # sempre visível
            ("📄 Relatórios", self.tela_relatorios, self.colors["relatorios_hover"], "can_access_relatorios"),
        ]

        for texto, comando, hover, perm_key in modulos:
            # Admin vê tudo; outros só veem se a permissão estiver habilitada (default=1)
            if perm_key and not is_admin and not u.get(perm_key, 1):
                continue
            ctk.CTkButton(
                self.frame_sidebar_modulos,
                text=texto,
                command=comando,
                hover_color=hover,
                **btn_opts,
            ).pack(pady=5, fill="x", padx=10)

    def tela_home(self) -> None:
        self.current_screen_function = self.tela_home
        self.current_screen_args = ()
        self.current_screen_kwargs = {}
        self.limpar_tela()
        ctk.CTkLabel(
            self.main_frame,
            text="Controle de Créditos - Hotel Santos",
            font=("Arial", 28, "bold"),
            text_color=self.colors["sucesso"],
        ).pack(pady=60)
        grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        grid.pack()

        u = self.current_user or {}
        is_admin = bool(u.get("is_admin", 0))

        # (texto, comando, cores, permission_key)
        todos_btns = [
            (
                "👥 HÓSPEDES",
                self.tela_hospedes,
                (self.colors["hospedes"], self.colors["hospedes_hover"]),
                "can_access_hospedes",
            ),
            (
                "💰 FINANCEIRO",
                self.tela_financeiro,
                (self.colors["financeiro"], self.colors["financeiro_hover"]),
                "can_access_financeiro",
            ),
            (
                "🛒 COMPRAS",
                self.tela_compras,
                (self.colors["compras"], self.colors["compras_hover"]),
                "can_access_compras",
            ),
            (
                "📊 DASHBOARD",
                self.tela_dash,
                (self.colors["dashboard"], self.colors["dashboard_hover"]),
                "can_access_dash",
            ),
            ("⚙️ AJUSTES", self.tela_config, (self.colors["ajustes"], self.colors["ajustes_hover"]), None),
            (
                "📄 RELATÓRIOS",
                self.tela_relatorios,
                (self.colors["relatorios"], self.colors["relatorios_hover"]),
                "can_access_relatorios",
            ),
        ]

        btns = [(t, c, col) for t, c, col, perm in todos_btns if perm is None or is_admin or u.get(perm, 1)]

        for i, (t, c, col) in enumerate(btns):
            ctk.CTkButton(grid, text=t, width=250, height=90, command=c, fg_color=col, font=("Arial", 14, "bold")).grid(
                row=i // 2, column=i % 2, padx=20, pady=20
            )

    # =========================================================================
    # 4. MÓDULO HÓSPEDES (Listagem e Busca)
    # =========================================================================
    def tela_hospedes(self, filtro: str = "todos") -> None:
        self._set_tela(self.tela_hospedes, filtro=filtro)
        self.limpar_tela()
        self._tela_hospedes = TelaHospedes(self.main_frame, self.core, self.current_user, self.colors)
        self._tela_hospedes.on_back = self.voltar
        self._tela_hospedes.renderizar()
        if filtro != "todos":
            self._tela_hospedes._set_filtro(filtro)

    # =========================================================================
    # 5. MÓDULO HISTÓRICO & FINANCEIRO (Detalhes do Cliente)
    # =========================================================================
    def tela_historico(self, nome: str, doc: str) -> None:
        self._set_tela(self.tela_historico, nome, doc)
        self.limpar_tela()
        self.main_frame.columnconfigure(0, weight=3)
        self.main_frame.columnconfigure(1, weight=1)
        f_esq = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_esq.grid(row=0, column=0, sticky="nsew", padx=10)
        top = ctk.CTkFrame(f_esq, fg_color="transparent")
        top.pack(fill="x", pady=5)
        ctk.CTkButton(top, text="← Voltar", width=80, command=self.tela_hospedes).pack(side="left")
        ctk.CTkButton(
            top,
            text="💬 WhatsApp",
            fg_color="#25D366",
            hover_color="#128C7E",
            width=100,
            command=lambda: self.enviar_whatsapp(nome, str(doc)),
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top, text=" Extrato", fg_color="#2c3e50", width=80, command=lambda: self.emitir_extrato(nome, doc)
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top,
            text="📄 Ticket Multas",
            fg_color="#c0392b",
            width=80,
            command=lambda: self.emitir_extrato_multas(nome, doc),
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top,
            text="📄 PDF Voucher",
            fg_color=self.colors["sucesso"],
            width=100,
            command=lambda: self.emitir_voucher(nome, doc),
        ).pack(side="right", padx=5)
        ctk.CTkLabel(f_esq, text=f"Histórico Financeiro: {nome}", font=("Arial", 20, "bold")).pack(pady=10)

        form = ctk.CTkFrame(f_esq, fg_color="transparent")
        form.pack(fill="x", pady=5)
        ctk.CTkButton(
            form,
            text="Adicionar Crédito",
            fg_color=self.colors["sucesso"],
            command=lambda: self.janela_add_credito(doc, nome),
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            form,
            text="Utilizar Crédito",
            fg_color=self.colors["perigo"],
            command=lambda: self.janela_usar_credito(doc, nome),
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            form,
            text="Lançar Multa",
            fg_color=self.colors["aviso"],
            text_color="white",
            command=lambda: self.janela_add_multa(doc, nome),
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            form, text="Pagar Multa", fg_color="#27ae60", command=lambda: self.janela_pagar_multa(doc, nome)
        ).pack(side="left", padx=5)

        self.tree_z = ttk.Treeview(f_esq, columns=("ID", "T", "V", "D", "C", "U"), show="headings", height=10)
        self.tree_z.heading("ID", text="#")
        self.tree_z.column("ID", width=40, anchor="center")
        for c, t in [("T", "Tipo"), ("V", "Valor"), ("D", "Data"), ("C", "Categoria"), ("U", "Resp.")]:
            self.tree_z.heading(c, text=t)
            self.tree_z.column(c, anchor="center")
        self.tree_z.pack(expand=True, fill="both")
        self.configurar_tags_tabela(self.tree_z)

        # Clique direito para ajustar data (restaurado)
        self.tree_z.bind("<Button-3>", lambda e: self.janela_ajuste_data(e, nome, doc))

        hist = self.core.get_historico_detalhado(doc)
        for i, m in enumerate(hist):
            data_br = datetime.strptime(m["data_acao"], "%Y-%m-%d").strftime("%d/%m/%Y")
            user_resp = m["usuario"] if m["usuario"] else "Sistema"
            tags = ["odd" if i % 2 != 0 else "even"]
            if m["tipo"] == "SAIDA":
                tags.append("saida")
            if m["tipo"] == "MULTA":
                tags.append("multa")
            if m["tipo"] == "PAGAMENTO_MULTA":
                tags.append("pagamento_multa")
            self.tree_z.insert(
                "",
                "end",
                values=(m["id"], m["tipo"], f"{m['valor']:.2f}", data_br, m["categoria"], user_resp),
                tags=tags,
            )

        f_dir = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_dir.grid(row=0, column=1, sticky="nsew", padx=10)
        s, v, b = self.core.get_saldo_info(doc)
        divida = self.core.get_divida_multas(doc)

        info_cards = [
            ("Saldo de Crédito", f"R$ {s:.2f}", self.colors["sucesso"]),
            ("Vencimento Próximo", v, self.colors["perigo"] if b else self.colors["aviso"]),
            ("Dívida (Multas)", f"R$ {divida:.2f}", self.colors["aviso"] if divida > 0 else "gray"),
        ]

        for t, val, col in info_cards:
            c = ctk.CTkFrame(f_dir, border_width=1)
            c.pack(fill="x", pady=5, ipady=10)
            ctk.CTkLabel(c, text=t, font=("Arial", 11)).pack()
            ctk.CTkLabel(c, text=val, font=("Arial", 16, "bold"), text_color=col).pack()

        p = ctk.CTkFrame(f_dir, fg_color="#fef9c3", border_width=1, border_color="#facc15")
        p.pack(fill="both", expand=True, pady=10)
        ctk.CTkLabel(p, text="📌 NOTAS GERAIS", text_color="#854d0e", font=("Arial", 12, "bold")).pack(pady=5)
        txt = ctk.CTkTextbox(p, fg_color="transparent", text_color="black")
        txt.pack(fill="both", expand=True, padx=5)
        txt.insert("1.0", self.core.get_anotacao(doc))
        ctk.CTkButton(
            p,
            text="Salvar Notas",
            width=100,
            fg_color=self.colors["aviso"],
            text_color="white",
            command=lambda: self.core.salvar_anotacao(doc, txt.get("1.0", "end-1c")),
        ).pack(pady=5)

    def enviar_whatsapp(self, nome: str, doc: str) -> None:
        s, v, b = self.core.get_saldo_info(doc)
        if s <= 0:
            messagebox.showwarning("Aviso", "Cliente sem saldo para enviar.")
            return
        hospede = self.core.get_hospede(doc)
        fone = hospede["telefone"] if hospede and hospede["telefone"] else None
        if not fone:
            if messagebox.askyesno(
                "Telefone não encontrado",
                "Este cliente não possui um telefone cadastrado. Deseja cadastrar/editar agora?",
            ):
                self.janela_cadastro_hospede(doc_to_edit=doc)
            return
        fone_limpo = "".join(filter(str.isdigit, fone))
        if not fone_limpo:
            messagebox.showerror("Erro", f"O número de telefone cadastrado ('{fone}') é inválido.")
            return
        msg = f"*HOTEL SANTOS - VOUCHER DE CRÉDITO*\n\nOlá {nome},\nSegue seu saldo atualizado:\n\n💰 *Valor:* R$ {s:.2f}\n📅 *Validade:* {v}\n\nUtilize este crédito em sua próxima hospedagem!"
        link = f"https://web.whatsapp.com/send?phone=55{fone_limpo}&text={quote(msg)}"
        webbrowser.open(link)

    def emitir_voucher(self, nome: str, doc: str) -> None:
        self.configure(cursor="watch")

        def _task():
            try:
                f = self.core.gerar_pdf_voucher(nome, doc)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Voucher gerado: {f}"))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Erro", str(err)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))

        threading.Thread(target=_task, daemon=True).start()

    def emitir_extrato(self, nome: str, doc: str) -> None:
        self.configure(cursor="watch")

        def _task():
            try:
                f = self.core.gerar_pdf_extrato(nome, doc)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f"Extrato gerado: {f}"))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Erro", str(err)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))

        threading.Thread(target=_task, daemon=True).start()

    def emitir_extrato_multas(self, nome: str, doc: str) -> None:
        self.configure(cursor="watch")

        def _task():
            try:
                f = self.core.gerar_pdf_multas(nome, doc)
                self.after(0, lambda: messagebox.showinfo("Sucesso", f" Ticket de Multas gerado: {f}"))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Erro", str(err)))
            finally:
                self.after(0, lambda: self.configure(cursor="arrow"))

        threading.Thread(target=_task, daemon=True).start()

    def voltar(self) -> None:
        """Navega para a tela anterior, ou para home se não houver anterior."""
        if self._prev_screen_fn is not None:
            fn, args, kwargs = self._prev_screen_fn, self._prev_screen_args, self._prev_screen_kwargs
            self._prev_screen_fn = None
            fn(*args, **kwargs)
        else:
            self.tela_home()

    def _set_tela(self, fn: Callable[..., None], *args, **kwargs) -> None:
        """Registra a tela atual como 'anterior' antes de trocar."""
        if self.current_screen_function is not None:
            self._prev_screen_fn = self.current_screen_function
            self._prev_screen_args = self.current_screen_args
            self._prev_screen_kwargs = self.current_screen_kwargs
        self.current_screen_function = fn
        self.current_screen_args = args
        self.current_screen_kwargs = kwargs

    # =========================================================================
    # 6. MÓDULO DASHBOARD & RELATÓRIOS
    # =========================================================================
    def tela_dash(self) -> None:
        self._set_tela(self.tela_dash)
        self.limpar_tela()
        tela = TelaDashboard(self.main_frame, self.core, self.current_user, self.colors)
        tela.on_back = self.voltar
        tela.renderizar()

    # =========================================================================
    # MÓDULO COMPRAS
    # =========================================================================
    def tela_compras(self) -> None:
        self._set_tela(self.tela_compras)
        self.limpar_tela()
        tela = TelaCompras(self.main_frame, self.core, self.current_user, self.colors)
        tela.on_back = self.voltar
        tela.renderizar()

    # =========================================================================
    # MÓDULO AGENDA
    # =========================================================================
    def tela_agenda(self) -> None:
        # ===========================================================================
        # CORREÇÃO — DEF HEADER RESTAURADO
        # ===========================================================================
        # No arquivo original, o início desta função estava FALTANDO — o código
        # começava direto no `if not Calendar:` sem o `def tela_agenda(self):`.
        # Isso causava SyntaxError ao carregar o módulo.
        # ===========================================================================
        if not Calendar:
            messagebox.showerror(
                "Erro de Dependência",
                "A biblioteca 'tkcalendar' é necessária para este módulo.\n\nInstale com: pip install tkcalendar",
            )
            return

        self.current_screen_function = self.tela_agenda
        self.current_screen_args = ()
        self.current_screen_kwargs = {}
        self.limpar_tela()

        nav = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(nav, text="← Início", width=80, command=self.tela_home).pack(side="left")
        ctk.CTkLabel(
            nav, text="AGENDA DE FUNCIONÁRIOS", font=("Arial", 18, "bold"), text_color=self.colors["ajustes"]
        ).pack(side="left", padx=20)

        main_paned = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        main_paned.pack(fill="both", expand=True, padx=10, pady=5)

        # --- PAINEL ESQUERDO (Gerenciamento) ---
        left_frame = ctk.CTkFrame(main_paned, width=350)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)

        # --- PAINEL DIREITO (Calendário) ---
        right_frame = ctk.CTkFrame(main_paned)
        right_frame.pack(side="right", fill="both", expand=True)

        # ===========================================================================
        # CORREÇÃO — CALENDÁRIO ADICIONADO NO PAINEL DIREITO
        # ===========================================================================
        # O original tinha right_frame criado mas vazio. O calendário nunca foi
        # colocado nele. Sem o calendário, cal_date e data_selecionada ficavam
        # indefinidos e causavam NameError em refresh_lista_funcionarios.
        # ===========================================================================
        ctk.CTkLabel(right_frame, text="Calendário", font=("Arial", 14, "bold")).pack(pady=10)

        # Cria o calendário e guarda como self.cal_agenda para acesso pelos métodos
        self.cal_agenda = Calendar(right_frame, selectmode="day", date_pattern="dd/mm/yyyy", locale="pt_BR")
        self.cal_agenda.pack(fill="both", expand=True, padx=10, pady=10)  # type: ignore[union-attr]

        # Quando o usuário clica numa data, atualiza a lista de tarefas do dia
        self.cal_agenda.bind("<<CalendarSelected>>", lambda e: self.refresh_lista_funcionarios())  # type: ignore[union-attr]

        # --- Conteúdo do Painel Esquerdo ---
        add_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=5)

        # ===========================================================================
        # CORREÇÃO — BOTÃO "ADICIONAR FUNCIONÁRIO" ESTAVA DEFINIDO MAS NÃO CRIADO
        # ===========================================================================
        def adicionar_func_action():
            dialog = ctk.CTkInputDialog(text="Nome do Funcionário:", title="Novo Funcionário")
            nome = dialog.get_input()
            if nome and self.current_user:
                try:
                    self.core.adicionar_funcionario(nome, self.current_user["username"])
                    self.refresh_lista_funcionarios()
                except Exception as e:
                    messagebox.showerror("Erro", str(e))

        ctk.CTkButton(
            add_frame, text="+ Novo Funcionário", fg_color=self.colors["sucesso"], command=adicionar_func_action
        ).pack(fill="x")

        ctk.CTkLabel(left_frame, text="Tarefas do Dia", font=("Arial", 14, "bold")).pack(pady=(15, 5))
        self.lbl_data_selecionada = ctk.CTkLabel(left_frame, text="Selecione uma data", text_color="gray")
        self.lbl_data_selecionada.pack(pady=5)

        self.combo_funcionarios = ctk.CTkComboBox(left_frame, width=250, values=["Nenhum"])
        self.combo_funcionarios.pack(pady=5)
        self.e_obs_agenda = ctk.CTkEntry(left_frame, width=250, placeholder_text="Tarefa / Turno")
        self.e_obs_agenda.pack(pady=5)
        ctk.CTkButton(
            left_frame,
            text="Adicionar Tarefa",
            fg_color=self.colors["sucesso"],
            command=self.agendar_funcionario_selecionado,
        ).pack(pady=5)

        self.tree_tarefas_dia = ttk.Treeview(left_frame, columns=("ID", "Func", "Obs"), show="headings", height=15)
        self.tree_tarefas_dia.heading("ID", text="#")
        self.tree_tarefas_dia.column("ID", width=0, stretch=False)
        self.tree_tarefas_dia.heading("Func", text="Funcionário")
        self.tree_tarefas_dia.column("Func", width=120)
        self.tree_tarefas_dia.heading("Obs", text="Tarefa")
        self.tree_tarefas_dia.column("Obs", width=150)
        self.tree_tarefas_dia.pack(fill="both", expand=True, padx=5, pady=10)
        ctk.CTkButton(
            left_frame,
            text="Remover Tarefa Selecionada",
            fg_color=self.colors["perigo"],
            command=self.remover_agendamento_selecionado,
        ).pack(pady=10)

        self.refresh_lista_funcionarios()

    def refresh_lista_funcionarios(self):
        """
        Atualiza o combo de funcionários e a lista de tarefas do dia selecionado.

        CORREÇÃO: No original, este método usava as variáveis 'cal_date' e
        'data_selecionada' sem elas estarem definidas no escopo, causando NameError.
        Agora lemos a data diretamente de self.cal_agenda (o widget de calendário).
        """
        if not self.combo_funcionarios:
            return

        # Lê a data selecionada no calendário (agora é um atributo, não variável local)
        if self.cal_agenda is None:
            return
        data_selecionada = self.cal_agenda.get_date()  # formato dd/mm/yyyy

        self.funcionarios_cache = [dict(f) for f in self.core.get_funcionarios()]
        nomes_funcionarios = [f["nome"] for f in self.funcionarios_cache]
        self.combo_funcionarios.configure(values=["Nenhum"] + nomes_funcionarios)
        self.combo_funcionarios.set("Nenhum")

        # Atualiza o label da data
        if self.lbl_data_selecionada:
            self.lbl_data_selecionada.configure(text=f"Data: {data_selecionada}")

        # Limpa e recarrega a lista de tarefas do dia
        if self.tree_tarefas_dia:
            self.tree_tarefas_dia.delete(*self.tree_tarefas_dia.get_children())
            try:
                data_iso = datetime.strptime(data_selecionada, "%d/%m/%Y").strftime("%Y-%m-%d")
                tarefas = self.core.get_tarefas_dia(data_iso)
                for t in tarefas:
                    self.tree_tarefas_dia.insert("", "end", values=(t["id"], t["nome"], t["obs"]))
            except Exception as e:
                self.logger.log_erro(e, "buscar_agendamentos")

    def agendar_funcionario_selecionado(self):
        """
        CORREÇÃO: No original, 'data_str' era usada sem estar definida no escopo.
        Agora lemos diretamente de self.cal_agenda.
        """
        if not self.current_user or self.cal_agenda is None:
            return

        nome_func = self.combo_funcionarios.get()
        if nome_func == "Nenhum":
            messagebox.showwarning("Aviso", "Selecione um funcionário para agendar.")
            return

        func_id = None
        for f in self.funcionarios_cache:
            if f["nome"] == nome_func:
                func_id = f["id"]
                break

        if func_id is None:
            messagebox.showerror("Erro", "Funcionário não encontrado no cache.")
            return

        # Lê a data do calendário (antes era 'data_str' sem definição)
        data_str = self.cal_agenda.get_date()
        data_iso = datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        obs = self.e_obs_agenda.get()

        try:
            self.core.salvar_agendamento(data_iso, func_id, obs, self.current_user["username"])
            self.e_obs_agenda.delete(0, "end")
            self.refresh_lista_funcionarios()
        except Exception as e:
            messagebox.showerror("Erro ao Agendar", str(e))

    def remover_agendamento_selecionado(self):
        if not self.tree_tarefas_dia or not self.current_user:
            return
        sel = self.tree_tarefas_dia.selection()
        if not sel:
            return
        item = self.tree_tarefas_dia.item(sel[0])
        agenda_id = item["values"][0]
        if messagebox.askyesno("Confirmar", "Deseja remover esta tarefa?"):
            try:
                self.core.remover_agendamento_id(agenda_id, self.current_user["username"])
                self.refresh_lista_funcionarios()
            except Exception as e:
                messagebox.showerror("Erro ao Remover", str(e))

    # =========================================================================
    # 7. MÓDULO LANÇAMENTOS (Central)
    # =========================================================================
    def tela_financeiro(self) -> None:
        self._set_tela(self.tela_financeiro)
        self.limpar_tela()
        tela = TelaFinanceiro(self.main_frame, self.core, self.current_user, self.colors)
        tela.on_back = self.voltar
        tela.renderizar()

    # =========================================================================
    # 8. MÓDULO CONFIGURAÇÕES & ADMIN
    # =========================================================================
    def tela_config(self) -> None:
        self._set_tela(self.tela_config)
        self.limpar_tela()
        tela = TelaConfig(self.main_frame, self.core, self.current_user, self.colors, logger=self.logger)
        tela.on_back = self.voltar
        tela.renderizar()

    def tela_relatorios(self) -> None:
        self._set_tela(self.tela_relatorios)
        self.limpar_tela()
        tela = TelaRelatorios(self.main_frame, self.core, self.current_user, self.colors)
        tela.on_back = self.voltar
        tela.renderizar()

    # =========================================================================
    # 9. JANELAS DE DIÁLOGO (POPUPS & TOPLEVELS)
    # =========================================================================
    def janela_novo_lancamento_central(self) -> None:
        jan = ctk.CTkToplevel(self)
        jan.title("Novo Lançamento")
        jan.geometry("500x650")
        jan.transient(self)
        jan.lift()
        jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        ctk.CTkLabel(jan, text="1. Selecione o Cliente", font=("Arial", 14, "bold")).pack(pady=5)
        f_busca = ctk.CTkFrame(jan, fg_color="transparent")
        f_busca.pack(fill="x", padx=10)
        e_busca = ctk.CTkEntry(f_busca, placeholder_text="Nome ou CPF/CNPJ")
        e_busca.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f_busca, text="+ Novo Hóspede", width=100, command=self.janela_cadastro_hospede).pack(
            side="right", padx=5
        )
        tv_res = ttk.Treeview(jan, columns=("N", "D"), show="headings", height=5)
        tv_res.heading("N", text="Nome")
        tv_res.column("N", width=250)
        tv_res.heading("D", text="Documento")
        tv_res.column("D", width=150)
        tv_res.pack(fill="x", padx=10, pady=5)

        def buscar(e: object | None = None) -> None:
            tv_res.delete(*tv_res.get_children())
            for h in self.core.buscar_filtrado(e_busca.get()):
                tv_res.insert("", "end", values=(h[0], h[1]))

        ctk.CTkButton(f_busca, text="🔍", width=40, command=buscar).pack(side="left")
        e_busca.bind("<Return>", buscar)
        f_detalhes = ctk.CTkFrame(jan)
        f_detalhes.pack(fill="both", expand=True, padx=10, pady=10)
        lbl_cliente = ctk.CTkLabel(f_detalhes, text="Nenhum cliente selecionado", font=("Arial", 12))
        lbl_cliente.pack(pady=5)
        selected_doc = ctk.StringVar(value="")

        def selecionar_cliente(e: object) -> None:
            sel = tv_res.selection()
            if not sel:
                return
            vals = tv_res.item(sel[0])["values"]
            selected_doc.set(str(vals[1]))
            s, v, b = self.core.get_saldo_info(selected_doc.get())
            div = self.core.get_divida_multas(selected_doc.get())
            lbl_cliente.configure(text=f"Cliente: {vals[0]}\nSaldo: R$ {s:.2f} | Dívida: R$ {div:.2f}")

        tv_res.bind("<ButtonRelease-1>", selecionar_cliente)
        ctk.CTkLabel(f_detalhes, text="2. Dados do Lançamento", font=("Arial", 14, "bold")).pack(pady=5)

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
        f_tipo = ctk.CTkFrame(f_detalhes, fg_color="transparent")
        f_tipo.pack(pady=5)
        opcoes_radio = [
            ("Crédito", "ENTRADA", self.colors["sucesso"], 0, 0),
            ("Uso (Baixa)", "SAIDA", self.colors["perigo"], 0, 1),
            ("Multa", "MULTA", self.colors["aviso"], 1, 0),
            ("Pgto Multa", "PAGAMENTO_MULTA", self.colors["sucesso_hover"], 1, 1),
        ]
        for txt, val, col, r, c in opcoes_radio:
            ctk.CTkRadioButton(
                f_tipo, text=txt, variable=tipo_var, value=val, fg_color=col, command=atualizar_opcoes_categoria
            ).grid(row=r, column=c, padx=5, pady=5)
        e_valor = ctk.CTkEntry(f_detalhes, placeholder_text="Valor (R$)")
        e_valor.pack(pady=5)
        e_cat = ctk.CTkComboBox(f_detalhes, values=self.core.get_categorias())
        e_cat.pack(pady=5)
        e_obs = ctk.CTkTextbox(f_detalhes, height=60)
        e_obs.pack(pady=5, fill="x", padx=20)
        e_obs.insert("1.0", "Observação...")

        def confirmar(event: object | None = None) -> None:
            if not self.current_user:
                return
            if not selected_doc.get():
                messagebox.showwarning("Atenção", "Selecione um cliente primeiro.")
                return
            t, v, c, o, u = (
                tipo_var.get(),
                e_valor.get(),
                e_cat.get(),
                e_obs.get("1.0", "end-1c"),
                self.current_user["username"],
            )
            try:
                if t == "ENTRADA":
                    self.core.adicionar_movimentacao(selected_doc.get(), v, c, "ENTRADA", o, u)
                elif t == "SAIDA":
                    self.core.adicionar_movimentacao(selected_doc.get(), v, "Uso", "SAIDA", o, u)
                elif t == "MULTA":
                    self.core.adicionar_multa(selected_doc.get(), v, c, o, u)
                elif t == "PAGAMENTO_MULTA":
                    self.core.pagar_multa(selected_doc.get(), v, c, o, u)
                messagebox.showinfo("Sucesso", "Lançamento realizado!")
                jan.destroy()
                self.tela_financeiro()
            except Exception as e:
                messagebox.showerror("Erro", str(e))

        e_valor.bind("<Return>", confirmar)
        ctk.CTkButton(
            f_detalhes, text="CONFIRMAR LANÇAMENTO", fg_color=self.colors["financeiro"], height=40, command=confirmar
        ).pack(pady=10, fill="x", padx=20)

    def janela_ajuste_data(self, event: object, nome: str, doc: str) -> None:
        """Ajusta data de vencimento de uma ENTRADA (clique direito na tela de histórico)."""
        if not self.current_user or (
            not self.current_user.get("is_admin") and not self.current_user.get("can_change_dates")
        ):
            messagebox.showerror("Acesso Negado", "Você não tem permissão para alterar datas.")
            return
        try:
            from tkcalendar import DateEntry
        except ImportError:
            return
        item = self.tree_z.identify_row(event.y)  # type: ignore[attr-defined]
        if not item:
            return
        self.tree_z.selection_set(item)
        id_mov, tp, val, dt_mov, *_ = self.tree_z.item(item)["values"]  # type: ignore[str-unpack]
        if tp != "ENTRADA":
            return
        jan = ctk.CTkToplevel(self)
        jan.title("Ajustar Data")
        jan.geometry("300x320")
        jan.transient(self)
        jan.lift()
        jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        cal = DateEntry(jan, width=12, background="darkblue", date_pattern="dd/mm/yyyy")
        cal.pack(pady=20)

        def ok() -> None:
            self.core.atualizar_data_vencimento_manual(id_mov, cal.get(), self.current_user["username"])  # type: ignore[index]
            jan.destroy()
            self.tela_historico(nome, doc)

        ctk.CTkButton(jan, text="Atualizar Vencimento", command=ok).pack(pady=10)

    def janela_logs(self) -> None:
        jan = ctk.CTkToplevel(self)
        jan.title("Logs de Auditoria")
        jan.geometry("900x500")
        jan.transient(self)
        jan.lift()
        jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        tv = ttk.Treeview(jan, columns=("DH", "U", "A", "D", "M"), show="headings")
        tv.heading("DH", text="Data/Hora")
        tv.column("DH", width=140)
        tv.heading("U", text="Usuário")
        tv.column("U", width=100)
        tv.heading("A", text="Ação")
        tv.column("A", width=150)
        tv.heading("D", text="Detalhes")
        tv.column("D", width=350)
        tv.heading("M", text="Máquina")
        tv.column("M", width=100)
        tv.pack(fill="both", expand=True)
        for log in self.core.get_logs():
            tv.insert(
                "", "end", values=(log["data_hora"], log["usuario"], log["acao"], log["detalhes"], log["maquina"])
            )

    def janela_cadastro_hospede(self, doc_to_edit: str | None = None) -> None:
        jan = ctk.CTkToplevel(self)
        jan.geometry("450x350")
        jan.transient(self)
        jan.lift()
        jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        title = "Editar Hóspede" if doc_to_edit else "Novo Hóspede"
        jan.title(title)
        ctk.CTkLabel(jan, text=title, font=("Arial", 16, "bold")).pack(pady=15)
        campo_width = 380
        en = ctk.CTkEntry(jan, placeholder_text="Nome Completo", width=campo_width)
        en.pack(pady=8)
        ed = ctk.CTkEntry(jan, placeholder_text="CPF ou CNPJ", width=campo_width)
        ed.pack(pady=8)
        etel = ctk.CTkEntry(jan, placeholder_text="Telefone (WhatsApp)", width=campo_width)
        etel.pack(pady=8)
        eemail = ctk.CTkEntry(jan, placeholder_text="E-mail", width=campo_width)
        eemail.pack(pady=8)
        if doc_to_edit:
            hospede = self.core.get_hospede(doc_to_edit)
            if hospede:
                en.insert(0, hospede["nome"])
                ed.insert(0, hospede["documento"])
                ed.configure(state="disabled")
                etel.insert(0, hospede["telefone"] or "")
                eemail.insert(0, hospede["email"] or "")

        def salvar(event: object | None = None) -> None:
            user = self.current_user["username"] if self.current_user else "Sistema"
            try:
                self.core.cadastrar_hospede(en.get(), ed.get(), etel.get(), eemail.get(), usuario_acao=user)
                jan.destroy()
                if self.current_screen_function:
                    self.current_screen_function(*self.current_screen_args, **self.current_screen_kwargs)
            except Exception as e:
                messagebox.showerror("Erro", str(e))

        en.bind("<Return>", salvar)
        ed.bind("<Return>", salvar)
        etel.bind("<Return>", salvar)
        eemail.bind("<Return>", salvar)
        ctk.CTkButton(jan, text="Salvar", fg_color=self.colors["hospedes"], width=300, command=salvar).pack(pady=20)

    def _janela_movimentacao(
        self, title: str, doc: str, nome: str, tipo_mov: str, callback: Callable[..., None]
    ) -> None:
        jan = ctk.CTkToplevel(self)
        jan.title(title)
        jan.geometry("350x350")
        jan.transient(self)
        jan.lift()
        jan.focus_force()
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])
        ctk.CTkLabel(jan, text=title, font=("Arial", 16, "bold")).pack(pady=15)
        ev = ctk.CTkEntry(jan, placeholder_text="Valor (R$)", width=250)
        ev.pack(pady=10)
        label_cat = "Categoria"
        if tipo_mov == "MULTA":
            label_cat = "Motivo"
        elif tipo_mov == "PAGAMENTO_MULTA":
            label_cat = "Forma de Pagamento"
        ec = (
            ctk.CTkComboBox(jan, values=self.core.get_categorias(), width=250)
            if tipo_mov == "ENTRADA"
            else ctk.CTkEntry(jan, placeholder_text=label_cat, width=250)
        )
        ec.pack(pady=10)
        eo = ctk.CTkTextbox(jan, width=250, height=60)
        eo.pack(pady=10)

        def salvar(event: object | None = None) -> None:
            if not self.current_user:
                return
            user = self.current_user["username"]
            try:
                callback(doc, ev.get(), ec.get(), eo.get("1.0", "end-1c"), user)
                jan.destroy()
                self.tela_historico(nome, doc)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=jan)

        ev.bind("<Return>", salvar)
        ctk.CTkButton(jan, text="Confirmar", command=salvar, fg_color=self.colors["sucesso"]).pack(pady=10)

    def janela_add_credito(self, doc: str, nome: str) -> None:
        def cb(d, v, c, o, u):
            self.core.adicionar_movimentacao(d, v, c, "ENTRADA", o, u)

        self._janela_movimentacao("Adicionar Crédito", doc, nome, "ENTRADA", cb)

    def janela_usar_credito(self, doc: str, nome: str) -> None:
        def cb(d, v, c, o, u):
            self.core.adicionar_movimentacao(d, v, "Uso", "SAIDA", o, u)

        self._janela_movimentacao("Utilizar Crédito", doc, nome, "SAIDA", cb)

    def janela_add_multa(self, doc: str, nome: str) -> None:
        def cb(d, v, m, o, u):
            self.core.adicionar_multa(d, v, m, o, u)

        self._janela_movimentacao("Adicionar Multa", doc, nome, "MULTA", cb)

    def janela_pagar_multa(self, doc: str, nome: str) -> None:
        def cb(d, v, m, o, u):
            self.core.pagar_multa(d, v, m, o, u)

        self._janela_movimentacao("Pagar Multa", doc, nome, "PAGAMENTO_MULTA", cb)


if __name__ == "__main__":
    try:
        app = AppHotelLTS()
        app.mainloop()
    except Exception:
        app_data = os.getenv("APPDATA") or os.path.expanduser("~")
        log_dir = os.path.join(app_data, "SistemaHotelSantos", "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"crash_log_{timestamp}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"ERRO CRÍTICO NA INICIALIZAÇÃO - {datetime.now()}\n")
            f.write("-" * 50 + "\n")
            f.write(traceback.format_exc())
        try:
            messagebox.showerror(
                "Erro Fatal", f"O sistema encontrou um erro e precisou ser fechado.\n\nLog salvo em:\n{log_file}"
            )
        except Exception:
            pass
