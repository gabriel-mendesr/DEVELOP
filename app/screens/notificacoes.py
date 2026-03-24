"""
Tela de Notificações — Sistema Hotel Santos

Exibe dois painéis:
  - Logs de auditoria do banco (tabela, últimos 100 registros)
  - Arquivos de log do LoggerSystem (.log files no diretório de logs)

Ações disponíveis:
  - Atualizar (recarrega os dados)
  - Exportar Diagnóstico (gera JSON com info do sistema)
  - Limpar Logs (admin) — remove todos os registros de auditoria
"""

from pathlib import Path

import customtkinter as ctk

from .base import TelaBase


class TelaNotificacoes(TelaBase):
    """Tela de logs e notificações do sistema."""

    def __init__(self, master, core, usuario, colors, logger=None):
        super().__init__(master, core, usuario, colors)
        self._logger = logger

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()
        self.criar_titulo("🔔 Notificações", "Logs de auditoria e arquivos de diagnóstico")

        scroll = ctk.CTkScrollableFrame(self.master, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        self._criar_toolbar(scroll)
        self._criar_secao_auditoria(scroll)
        self._criar_secao_arquivos(scroll)

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _criar_toolbar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=self.colors.get("bg_secondary", "#1f2937"), corner_radius=8)
        bar.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            bar,
            text="🔄 Atualizar",
            width=120,
            fg_color="#1f6aa5",
            hover_color="#144870",
            command=self._atualizar,
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkButton(
            bar,
            text="📋 Exportar Diagnóstico",
            width=180,
            fg_color="#0d9488",
            hover_color="#0f766e",
            command=self._exportar_diagnostico,
        ).pack(side="left", padx=(0, 10), pady=8)

        if self.is_admin:
            ctk.CTkButton(
                bar,
                text="🗑️ Limpar Logs",
                width=130,
                fg_color="#c62828",
                hover_color="#8e0000",
                command=self._limpar_logs,
            ).pack(side="left", padx=(0, 10), pady=8)

        self._lbl_status = ctk.CTkLabel(
            bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        )
        self._lbl_status.pack(side="right", padx=12)

    # =========================================================================
    # SEÇÃO 1 — LOGS DE AUDITORIA (BANCO)
    # =========================================================================

    def _criar_secao_auditoria(self, parent):
        cabecalho = ctk.CTkFrame(parent, fg_color="transparent")
        cabecalho.pack(fill="x", pady=(5, 3))

        ctk.CTkLabel(
            cabecalho,
            text="📝 Logs de Auditoria (últimos 100)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors.get("accent", "#1f6aa5"),
        ).pack(side="left")

        self._tree_logs, _ = self.criar_tabela(
            parent,
            colunas=[
                ("id", 40),
                ("data_hora", 155),
                ("usuario", 90),
                ("acao", 170),
                ("detalhes", 290),
                ("maquina", 110),
            ],
            altura=250,
        )
        self._popular_logs()

    def _popular_logs(self):
        for row in self._tree_logs.get_children():
            self._tree_logs.delete(row)
        logs = self.core.get_logs()
        for log in logs:
            self._tree_logs.insert(
                "",
                "end",
                values=(
                    log.get("id", ""),
                    log.get("data_hora", ""),
                    log.get("usuario", ""),
                    log.get("acao", ""),
                    log.get("detalhes", ""),
                    log.get("maquina", ""),
                ),
            )
        self._lbl_status.configure(text=f"{len(logs)} registro(s) de auditoria")

    # =========================================================================
    # SEÇÃO 2 — ARQUIVOS DE LOG (.log)
    # =========================================================================

    def _criar_secao_arquivos(self, parent):
        cabecalho = ctk.CTkFrame(parent, fg_color="transparent")
        cabecalho.pack(fill="x", pady=(15, 3))

        ctk.CTkLabel(
            cabecalho,
            text="📁 Arquivos de Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors.get("accent", "#1f6aa5"),
        ).pack(side="left")

        log_dir = self._log_dir()
        if not log_dir or not log_dir.exists():
            ctk.CTkLabel(
                parent,
                text="Nenhum arquivo de log encontrado.",
                font=ctk.CTkFont(size=12),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
            ).pack(anchor="w", pady=5)
            return

        log_files = sorted(log_dir.glob("*.log"), reverse=True)
        if not log_files:
            ctk.CTkLabel(
                parent,
                text="Nenhum arquivo .log no diretório.",
                font=ctk.CTkFont(size=12),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
            ).pack(anchor="w", pady=5)
            return

        # Tabela de arquivos
        frame_arqs = ctk.CTkFrame(parent, fg_color=self.colors.get("bg_secondary", "#1f2937"), corner_radius=8)
        frame_arqs.pack(fill="x", pady=5)

        for f in log_files[:10]:  # Mostra os 10 mais recentes
            tamanho_kb = f.stat().st_size / 1024
            linha = ctk.CTkFrame(frame_arqs, fg_color="transparent")
            linha.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(
                linha,
                text=f.name,
                font=ctk.CTkFont(size=12),
                width=250,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                linha,
                text=f"{tamanho_kb:.1f} KB",
                font=ctk.CTkFont(size=11),
                text_color=self.colors.get("text_secondary", "#aaaaaa"),
                width=80,
            ).pack(side="left", padx=10)
            ctk.CTkButton(
                linha,
                text="👁 Ver",
                width=70,
                height=26,
                fg_color="#334155",
                hover_color="#475569",
                command=lambda p=f: self._visualizar_log(p),
            ).pack(side="left")

        ctk.CTkLabel(
            frame_arqs,
            text=f"Diretório: {log_dir}",
            font=ctk.CTkFont(size=10),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).pack(padx=10, pady=(2, 8), anchor="w")

    def _visualizar_log(self, path: Path):
        """Abre uma janela com as últimas 200 linhas do arquivo de log."""
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                linhas = f.readlines()
        except OSError as e:
            self.mostrar_erro(f"Não foi possível abrir o arquivo:\n{e}")
            return

        jan = ctk.CTkToplevel(self.master)
        jan.title(f"Log: {path.name}")
        jan.geometry("900x500")
        jan.transient(self.master)
        jan.after(100, lambda: [jan.grab_set(), jan.focus_force()])

        txt = ctk.CTkTextbox(jan, font=ctk.CTkFont(family="Courier New", size=11), wrap="none")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("end", "".join(linhas[-200:]))
        txt.configure(state="disabled")

    # =========================================================================
    # AÇÕES DOS BOTÕES
    # =========================================================================

    def _atualizar(self):
        self._popular_logs()

    def _exportar_diagnostico(self):
        if not self._logger:
            self.mostrar_erro("Logger não disponível.")
            return
        try:
            caminho = self._logger.exportar_diagnostico()
            self.mostrar_sucesso(f"Diagnóstico exportado:\n{caminho}")
        except Exception as e:
            self.mostrar_erro(f"Erro ao exportar diagnóstico:\n{e}")

    def _limpar_logs(self):
        if not self.confirmar("Apagar TODOS os registros de auditoria?\nEssa ação não pode ser desfeita."):
            return
        self.core.limpar_logs_auditoria(self.username)
        self._popular_logs()
        self.mostrar_sucesso("Logs de auditoria apagados.")

    def _log_dir(self) -> Path | None:
        if self._logger and hasattr(self._logger, "log_dir"):
            return self._logger.log_dir
        fallback = Path.home() / ".hotel_santos_logs"
        return fallback if fallback.exists() else None
