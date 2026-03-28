"""Geração de PDFs para o portal web — Hotel Santos.

Porta fiel das funções de relatorios.py do app desktop,
usando fpdf2 (mesma biblioteca) e os mesmos estilos/cabeçalhos.
"""

from datetime import datetime

from fpdf import FPDF

# Cores padrão (mesmo do app)
AZUL = (31, 106, 165)
VERMELHO = (198, 40, 40)
AZUL_CLARO = (240, 248, 255)
ROSA_CLARO = (255, 235, 235)
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cabecalho(pdf: FPDF, empresa: dict) -> None:
    """Cabeçalho azul com dados da empresa — igual ao app desktop."""
    pdf.set_fill_color(*AZUL)
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, empresa.get("nome", "HOTEL"), ln=True, fill=True, align="C")
    pdf.set_font("Helvetica", size=8)
    pdf.cell(0, 5, empresa.get("razao", ""), ln=True, fill=True, align="C")
    pdf.cell(
        0,
        5,
        f"CNPJ: {empresa.get('cnpj', '')}   {empresa.get('endereco', '')}",
        ln=True,
        fill=True,
        align="C",
    )
    pdf.cell(
        0,
        5,
        f"{empresa.get('contato', '')}   {empresa.get('email', '')}",
        ln=True,
        fill=True,
        align="C",
    )
    pdf.set_text_color(*PRETO)
    pdf.ln(4)


# =============================================================================
# PDF 1 — Extrato do Hóspede
# =============================================================================


def pdf_extrato(
    hospede: dict,
    movimentos: list[dict],
    saldo: float,
    venc: str,
    bloqueado: bool,
    empresa: dict,
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    _cabecalho(pdf, empresa)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"EXTRATO DO HOSPEDE: {hospede.get('nome', '')}", ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Documento: {hospede.get('documento', '')}   Telefone: {hospede.get('telefone') or 'N/I'}", ln=True)
    pdf.cell(
        0,
        6,
        f"Saldo atual: {_moeda(saldo)}   Vencimento: {venc}   Status: {'VENCIDO' if bloqueado else 'OK'}",
        ln=True,
    )
    pdf.ln(4)

    # Cabeçalho da tabela
    pdf.set_fill_color(*AZUL)
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 9)
    for col, w in [("Data", 28), ("Tipo", 22), ("Valor", 28), ("Categoria", 38), ("Obs", 50), ("Usuario", 26)]:
        pdf.cell(w, 7, col, border=1, fill=True)
    pdf.ln()

    pdf.set_text_color(*PRETO)
    pdf.set_font("Helvetica", size=9)
    fill = False
    for m in movimentos:
        pdf.set_fill_color(*AZUL_CLARO) if fill else pdf.set_fill_color(*BRANCO)
        pdf.cell(28, 6, str(m.get("data_acao", ""))[:10], border=1, fill=True)
        pdf.cell(22, 6, str(m.get("tipo", ""))[:8], border=1, fill=True)
        pdf.cell(28, 6, _moeda(float(m.get("valor", 0))), border=1, fill=True)
        pdf.cell(38, 6, str(m.get("categoria") or "")[:18], border=1, fill=True)
        pdf.cell(50, 6, str(m.get("obs") or "")[:24], border=1, fill=True)
        pdf.cell(26, 6, str(m.get("usuario") or "")[:12], border=1, fill=True, ln=True)
        fill = not fill

    pdf.ln(4)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)

    return bytes(pdf.output())


# =============================================================================
# PDF 2 — Resumo Mensal
# =============================================================================


def pdf_mensal(mes: str, movimentos: list[dict], empresa: dict) -> bytes:
    total_e = sum(float(m["valor"]) for m in movimentos if m.get("tipo") == "ENTRADA")
    total_s = sum(float(m["valor"]) for m in movimentos if m.get("tipo") == "SAIDA")

    pdf = FPDF()
    pdf.add_page()
    _cabecalho(pdf, empresa)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"RESUMO FINANCEIRO - {mes}", ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Total entradas: {_moeda(total_e)}   Total saidas: {_moeda(total_s)}", ln=True)
    pdf.cell(
        0,
        6,
        f"Saldo do periodo: {_moeda(total_e - total_s)}   Registros: {len(movimentos)}",
        ln=True,
    )
    pdf.ln(4)

    pdf.set_fill_color(*AZUL)
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 9)
    for col, w in [("Data", 26), ("Hospede", 60), ("Tipo", 22), ("Valor", 30), ("Categoria", 40), ("Usuario", 20)]:
        pdf.cell(w, 7, col, border=1, fill=True)
    pdf.ln()

    pdf.set_text_color(*PRETO)
    pdf.set_font("Helvetica", size=9)
    fill = False
    for m in movimentos:
        pdf.set_fill_color(*AZUL_CLARO) if fill else pdf.set_fill_color(*BRANCO)
        pdf.cell(26, 6, str(m.get("data_acao", ""))[:10], border=1, fill=True)
        pdf.cell(60, 6, str(m.get("nome", ""))[:28], border=1, fill=True)
        pdf.cell(22, 6, str(m.get("tipo", ""))[:8], border=1, fill=True)
        pdf.cell(30, 6, _moeda(float(m.get("valor", 0))), border=1, fill=True)
        pdf.cell(40, 6, str(m.get("categoria") or "")[:18], border=1, fill=True)
        pdf.cell(20, 6, str(m.get("usuario") or "")[:10], border=1, fill=True, ln=True)
        fill = not fill

    pdf.ln(4)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)

    return bytes(pdf.output())


# =============================================================================
# PDF 3 — Inadimplentes
# =============================================================================


def pdf_inadimplentes(devedores: list, empresa: dict) -> bytes:
    total = sum(float(d[3]) for d in devedores)

    pdf = FPDF()
    pdf.add_page()
    _cabecalho(pdf, empresa)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "LISTA DE INADIMPLENTES", ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Total de devedores: {len(devedores)}   Divida total: {_moeda(total)}", ln=True)
    pdf.cell(0, 6, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(4)

    pdf.set_fill_color(*VERMELHO)
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 9)
    for col, w in [("Nome", 80), ("Documento", 50), ("Telefone", 45), ("Divida", 35)]:
        pdf.cell(w, 7, col, border=1, fill=True)
    pdf.ln()

    pdf.set_text_color(*PRETO)
    pdf.set_font("Helvetica", size=9)
    fill = False
    for nome, doc, tel, divida in devedores:
        pdf.set_fill_color(*ROSA_CLARO) if fill else pdf.set_fill_color(*BRANCO)
        pdf.cell(80, 6, str(nome)[:38], border=1, fill=True)
        pdf.cell(50, 6, str(doc), border=1, fill=True)
        pdf.cell(45, 6, str(tel or "N/I")[:20], border=1, fill=True)
        pdf.cell(35, 6, _moeda(float(divida)), border=1, fill=True, ln=True)
        fill = not fill

    return bytes(pdf.output())
