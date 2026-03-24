"""
Tela de Relatórios — Sistema Hotel Santos

Gera e exporta relatórios em PDF:
  - Extrato individual por hóspede
  - Resumo financeiro mensal
  - Lista de inadimplentes (com multa)

DEPENDÊNCIA: fpdf2 (instalado via pyproject.toml como 'fpdf2').
O import é feito como `from fpdf import FPDF` — nome correto do módulo.
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime

import customtkinter as ctk

from .base import TelaBase


class TelaRelatorios(TelaBase):
    """Tela de geração de relatórios em PDF."""

    def renderizar(self):
        """Ponto de entrada — chamado pelo app_gui.py."""
        self.limpar_master()
        self.criar_titulo("📄 Relatórios", "Gerar e exportar relatórios em PDF")

        tabs = ctk.CTkTabview(self.master, fg_color=self.colors.get("bg_secondary", "#1f2937"))
        tabs.pack(fill="both", expand=True, padx=15, pady=10)

        tabs.add("👤 Extrato Hóspede")
        tabs.add("📅 Resumo Mensal")
        tabs.add("⚠️ Inadimplentes")

        self._tab_extrato(tabs.tab("👤 Extrato Hóspede"))
        self._tab_mensal(tabs.tab("📅 Resumo Mensal"))
        self._tab_inadimplentes(tabs.tab("⚠️ Inadimplentes"))

    # =========================================================================
    # TAB 1 — EXTRATO POR HÓSPEDE
    # =========================================================================

    def _tab_extrato(self, tab: ctk.CTkFrame):
        frame_busca = ctk.CTkFrame(tab, fg_color="transparent")
        frame_busca.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_busca, text="Documento ou nome:").pack(side="left", padx=(0, 8))
        self._ent_extrato = ctk.CTkEntry(frame_busca, placeholder_text="CPF, CNPJ ou nome...", width=260)
        self._ent_extrato.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame_busca,
            text="🔍 Buscar",
            width=100,
            fg_color="#1f6aa5",
            hover_color="#144870",
            command=self._buscar_extrato,
        ).pack(side="left")

        self._tree_extrato, _ = self.criar_tabela(
            tab,
            colunas=[
                ("data", 110),
                ("tipo", 90),
                ("valor", 100),
                ("categoria", 140),
                ("vencimento", 110),
                ("obs", 220),
                ("usuario", 100),
            ],
            altura=320,
        )

        frame_btn = ctk.CTkFrame(tab, fg_color="transparent")
        frame_btn.pack(pady=8)
        ctk.CTkButton(
            frame_btn,
            text="📥 Gerar PDF",
            width=160,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._gerar_extrato_pdf,
        ).pack()

        self._hospede_extrato: dict | None = None

    def _buscar_extrato(self):
        termo = self._ent_extrato.get().strip()
        if not termo:
            return
        resultados = self.core.buscar_filtrado(termo)
        if not resultados:
            self.mostrar_erro("Nenhum hóspede encontrado.")
            return

        self._hospede_extrato = self.core.get_hospede(resultados[0][1])
        movimentos = self.core.get_historico_detalhado(resultados[0][1])

        for row in self._tree_extrato.get_children():
            self._tree_extrato.delete(row)
        for m in movimentos:
            self._tree_extrato.insert(
                "",
                "end",
                values=(
                    m.get("data_acao", ""),
                    m.get("tipo", ""),
                    self.formatar_moeda(float(m.get("valor", 0))),
                    m.get("categoria", ""),
                    m.get("data_vencimento", "") or "",
                    m.get("obs", "") or "",
                    m.get("usuario", ""),
                ),
            )

    def _gerar_extrato_pdf(self):
        if not self._hospede_extrato:
            self.mostrar_erro("Busque um hóspede antes de gerar o PDF.")
            return
        doc = self._hospede_extrato.get("documento", "")
        movimentos = self.core.get_historico_detalhado(doc)
        saldo, venc, bloqueado = self.core.get_saldo_info(doc)

        try:
            from fpdf import FPDF  # noqa: PLC0415
        except ImportError:
            self.mostrar_erro("fpdf2 não está instalado.\nExecute: pip install fpdf2")
            return

        pdf = FPDF()
        pdf.add_page()
        self._cabecalho(pdf)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, f"EXTRATO DO HÓSPEDE: {self._hospede_extrato.get('nome', '')}", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 6, f"Documento: {doc}   Telefone: {self._hospede_extrato.get('telefone') or 'N/I'}", ln=True)
        pdf.cell(
            0,
            6,
            f"Saldo atual: {self.formatar_moeda(saldo)}   Vencimento: {venc}   Status: {'VENCIDO' if bloqueado else 'OK'}",
            ln=True,
        )
        pdf.ln(4)

        # Cabeçalho da tabela
        pdf.set_fill_color(31, 106, 165)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        for col, w in [("Data", 28), ("Tipo", 22), ("Valor", 28), ("Categoria", 38), ("Obs", 50), ("Usuário", 26)]:
            pdf.cell(w, 7, col, border=1, fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=9)
        fill = False
        for m in movimentos:
            pdf.set_fill_color(240, 248, 255) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(28, 6, str(m.get("data_acao", ""))[:10], border=1, fill=True)
            pdf.cell(22, 6, str(m.get("tipo", ""))[:8], border=1, fill=True)
            pdf.cell(28, 6, self.formatar_moeda(float(m.get("valor", 0))), border=1, fill=True)
            pdf.cell(38, 6, str(m.get("categoria", ""))[:18], border=1, fill=True)
            pdf.cell(50, 6, str(m.get("obs") or "")[:24], border=1, fill=True)
            pdf.cell(26, 6, str(m.get("usuario", ""))[:12], border=1, fill=True, ln=True)
            fill = not fill

        self._abrir_pdf(pdf, f"extrato_{doc}")

    # =========================================================================
    # TAB 2 — RESUMO MENSAL
    # =========================================================================

    def _tab_mensal(self, tab: ctk.CTkFrame):
        frame_filtro = ctk.CTkFrame(tab, fg_color="transparent")
        frame_filtro.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_filtro, text="Mês (MM/AAAA):").pack(side="left", padx=(0, 8))
        self._ent_mes = ctk.CTkEntry(frame_filtro, placeholder_text=datetime.now().strftime("%m/%Y"), width=120)
        self._ent_mes.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame_filtro,
            text="🔍 Carregar",
            width=100,
            fg_color="#1f6aa5",
            hover_color="#144870",
            command=self._carregar_mensal,
        ).pack(side="left")

        self._tree_mensal, _ = self.criar_tabela(
            tab,
            colunas=[
                ("data", 100),
                ("hospede", 200),
                ("tipo", 90),
                ("valor", 100),
                ("categoria", 140),
                ("usuario", 100),
            ],
            altura=320,
        )

        frame_btn = ctk.CTkFrame(tab, fg_color="transparent")
        frame_btn.pack(pady=8)
        ctk.CTkButton(
            frame_btn,
            text="📥 Gerar PDF",
            width=160,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._gerar_mensal_pdf,
        ).pack()

        self._historico_mensal: list[dict] = []

    def _carregar_mensal(self):
        mes = self._ent_mes.get().strip() or datetime.now().strftime("%m/%Y")
        try:
            dt = datetime.strptime(mes, "%m/%Y")
            inicio = dt.strftime("%Y-%m-01")
            # Último dia do mês
            if dt.month == 12:
                fim = f"{dt.year + 1}-01-01"
            else:
                fim = f"{dt.year}-{dt.month + 1:02d}-01"
        except ValueError:
            self.mostrar_erro("Formato inválido. Use MM/AAAA.")
            return

        self._historico_mensal = self.core.get_historico_global(data_inicio=inicio, data_fim=fim, limite=500)

        for row in self._tree_mensal.get_children():
            self._tree_mensal.delete(row)
        for m in self._historico_mensal:
            self._tree_mensal.insert(
                "",
                "end",
                values=(
                    m.get("data_acao", "")[:10],
                    m.get("nome", ""),
                    m.get("tipo", ""),
                    self.formatar_moeda(float(m.get("valor", 0))),
                    m.get("categoria", ""),
                    m.get("usuario", ""),
                ),
            )

    def _gerar_mensal_pdf(self):
        if not self._historico_mensal:
            self.mostrar_erro("Carregue os dados antes de gerar o PDF.")
            return

        try:
            from fpdf import FPDF  # noqa: PLC0415
        except ImportError:
            self.mostrar_erro("fpdf2 não está instalado.\nExecute: pip install fpdf2")
            return

        mes = self._ent_mes.get().strip() or datetime.now().strftime("%m/%Y")
        total_e = sum(float(m["valor"]) for m in self._historico_mensal if m.get("tipo") == "ENTRADA")
        total_s = sum(float(m["valor"]) for m in self._historico_mensal if m.get("tipo") == "SAIDA")

        pdf = FPDF()
        pdf.add_page()
        self._cabecalho(pdf)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, f"RESUMO FINANCEIRO — {mes}", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(
            0,
            6,
            f"Total entradas: {self.formatar_moeda(total_e)}   Total saídas: {self.formatar_moeda(total_s)}",
            ln=True,
        )
        pdf.cell(
            0,
            6,
            f"Saldo do período: {self.formatar_moeda(total_e - total_s)}   Registros: {len(self._historico_mensal)}",
            ln=True,
        )
        pdf.ln(4)

        pdf.set_fill_color(31, 106, 165)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        for col, w in [("Data", 26), ("Hóspede", 60), ("Tipo", 22), ("Valor", 30), ("Categoria", 40), ("Usuário", 20)]:
            pdf.cell(w, 7, col, border=1, fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=9)
        fill = False
        for m in self._historico_mensal:
            pdf.set_fill_color(240, 248, 255) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(26, 6, str(m.get("data_acao", ""))[:10], border=1, fill=True)
            pdf.cell(60, 6, str(m.get("nome", ""))[:28], border=1, fill=True)
            pdf.cell(22, 6, str(m.get("tipo", ""))[:8], border=1, fill=True)
            pdf.cell(30, 6, self.formatar_moeda(float(m.get("valor", 0))), border=1, fill=True)
            pdf.cell(40, 6, str(m.get("categoria", ""))[:18], border=1, fill=True)
            pdf.cell(20, 6, str(m.get("usuario", ""))[:10], border=1, fill=True, ln=True)
            fill = not fill

        self._abrir_pdf(pdf, f"mensal_{mes.replace('/', '-')}")

    # =========================================================================
    # TAB 3 — INADIMPLENTES
    # =========================================================================

    def _tab_inadimplentes(self, tab: ctk.CTkFrame):
        frame_topo = ctk.CTkFrame(tab, fg_color="transparent")
        frame_topo.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            frame_topo,
            text="Hóspedes com dívida de multas em aberto",
            font=ctk.CTkFont(size=13),
            text_color=self.colors.get("text_secondary", "#aaaaaa"),
        ).pack(side="left")
        ctk.CTkButton(
            frame_topo,
            text="🔄 Atualizar",
            width=100,
            fg_color="#1f6aa5",
            hover_color="#144870",
            command=self._carregar_inadimplentes,
        ).pack(side="right")

        self._tree_inad, _ = self.criar_tabela(
            tab,
            colunas=[("nome", 240), ("documento", 160), ("telefone", 140), ("divida", 120)],
            altura=320,
        )

        frame_btn = ctk.CTkFrame(tab, fg_color="transparent")
        frame_btn.pack(pady=8)
        ctk.CTkButton(
            frame_btn,
            text="📥 Gerar PDF",
            width=160,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._gerar_inadimplentes_pdf,
        ).pack()

        self._devedores: list[tuple] = []
        self._carregar_inadimplentes()

    def _carregar_inadimplentes(self):
        self._devedores = self.core.get_devedores_multas()
        for row in self._tree_inad.get_children():
            self._tree_inad.delete(row)
        for nome, doc, tel, divida in self._devedores:
            self._tree_inad.insert(
                "",
                "end",
                values=(nome, doc, tel or "N/I", self.formatar_moeda(divida)),
            )

    def _gerar_inadimplentes_pdf(self):
        if not self._devedores:
            self.mostrar_erro("Nenhum inadimplente encontrado.")
            return

        try:
            from fpdf import FPDF  # noqa: PLC0415
        except ImportError:
            self.mostrar_erro("fpdf2 não está instalado.\nExecute: pip install fpdf2")
            return

        total = sum(d[3] for d in self._devedores)
        pdf = FPDF()
        pdf.add_page()
        self._cabecalho(pdf)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "LISTA DE INADIMPLENTES", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(
            0, 6, f"Total de devedores: {len(self._devedores)}   Dívida total: {self.formatar_moeda(total)}", ln=True
        )
        pdf.cell(0, 6, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(4)

        pdf.set_fill_color(198, 40, 40)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        for col, w in [("Nome", 70), ("Documento", 44), ("Telefone", 40), ("Dívida", 36)]:
            pdf.cell(w, 7, col, border=1, fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=9)
        fill = False
        for nome, doc, tel, divida in self._devedores:
            pdf.set_fill_color(255, 235, 235) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(70, 6, str(nome)[:33], border=1, fill=True)
            pdf.cell(44, 6, str(doc), border=1, fill=True)
            pdf.cell(40, 6, str(tel or "N/I")[:18], border=1, fill=True)
            pdf.cell(36, 6, self.formatar_moeda(divida), border=1, fill=True, ln=True)
            fill = not fill

        self._abrir_pdf(pdf, "inadimplentes")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _cabecalho(self, pdf) -> None:
        """Cabeçalho padrão da empresa no topo de cada PDF."""
        emp = self.core.empresa
        pdf.set_fill_color(31, 106, 165)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, emp.get("nome", "HOTEL"), ln=True, fill=True, align="C")
        pdf.set_font("Helvetica", size=8)
        pdf.cell(0, 5, emp.get("razao", ""), ln=True, fill=True, align="C")
        pdf.cell(0, 5, f"CNPJ: {emp.get('cnpj', '')}   {emp.get('endereco', '')}", ln=True, fill=True, align="C")
        pdf.cell(0, 5, f"{emp.get('contato', '')}   {emp.get('email', '')}", ln=True, fill=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    def _abrir_pdf(self, pdf, prefixo: str) -> None:
        """Salva o PDF em temp e abre com o visualizador padrão do sistema."""
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", prefix=f"hotel_{prefixo}_", delete=False)
            tmp.close()
            pdf.output(tmp.name)
            if sys.platform == "win32":
                os.startfile(tmp.name)
            else:
                subprocess.Popen(["xdg-open", tmp.name])
            self.mostrar_sucesso(f"PDF gerado:\n{tmp.name}")
        except Exception as e:
            self.mostrar_erro(f"Erro ao gerar PDF:\n{e}")
