"""Hotel Santos — Portal Web (FastAPI + Jinja2)

Como rodar localmente:
    cd web
    pip install -r requirements.txt
    uvicorn main:app --reload

Variáveis de ambiente:
    DATABASE_URL - connection string PostgreSQL (ex: postgresql://user:pass@host/db)
                   Se ausente, usa SQLite local (desenvolvimento)
    DB_PATH      - caminho do SQLite (padrão: ../app/hotel.db)
    SECRET_KEY   - chave para sessões (alterar em produção!)
"""

import csv as _csv
import io
import os
import sys
from pathlib import Path

from exporters import pdf_extrato, pdf_inadimplentes, pdf_mensal
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# =============================================================================
# Inicialização — PostgreSQL (produção) ou SQLite (local)
# =============================================================================
BASE_DIR = Path(__file__).parent
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    # Produção: Neon.tech / PostgreSQL
    from db_pg import SistemaCreditos as _SC

    sistema = _SC(DATABASE_URL)
else:
    # Desenvolvimento: SQLite local (mesmo banco do app desktop)
    sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
    from core.database import Database
    from core.models import SistemaCreditos as _SC  # type: ignore[no-redef]

    _db = Database(os.getenv("DB_PATH", str(Path(__file__).parent.parent / "app" / "hotel.db")))
    sistema = _SC(_db)

app = FastAPI(title="Hotel Santos")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "hotel-santos-dev-mude-em-producao"),
    max_age=86400,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# =============================================================================
# Helpers
# =============================================================================
def _flash(request: Request, msg: str, cat: str = "info") -> None:
    request.session.setdefault("_flashes", []).append({"msg": msg, "cat": cat})


def _pop_flashes(request: Request) -> list:
    return request.session.pop("_flashes", [])


def _user(request: Request) -> dict | None:
    return request.session.get("user")


def _ctx(request: Request, **kwargs) -> dict:
    """Contexto base injetado em todos os templates (sem 'request' — Starlette injeta automaticamente)."""
    return {"user": _user(request), "flashes": _pop_flashes(request), **kwargs}


def _redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)


# =============================================================================
# Autenticação
# =============================================================================
@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    return FileResponse(BASE_DIR / "static" / "manifest.json", media_type="application/json")


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if _user(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", _ctx(request))


@app.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = sistema.verificar_login(username, password)
    if user:
        request.session["user"] = dict(user)
        sistema.registrar_log(username, "LOGIN_WEB", "Acesso via portal web")
        return RedirectResponse("/", status_code=302)
    _flash(request, "Usuário ou senha incorretos.", "danger")
    return RedirectResponse("/login", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    u = _user(request)
    if u:
        sistema.registrar_log(u["username"], "LOGOUT_WEB", "")
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# =============================================================================
# Home
# =============================================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not _user(request):
        return _redirect_login()
    return templates.TemplateResponse(
        request,
        "home.html",
        _ctx(request, active="home"),
    )


# =============================================================================
# Dashboard
# =============================================================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _user(request):
        return _redirect_login()
    total_saldo, total_vencido, total_a_vencer, total_hospedes, total_multas = sistema.get_dados_dash()
    vencendo = sistema.get_hospedes_vencendo_em_breve()
    movimentos = sistema.get_historico_global(limite=10)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(
            request,
            total_saldo=total_saldo,
            total_vencido=total_vencido,
            total_a_vencer=total_a_vencer,
            total_hospedes=total_hospedes,
            total_multas=total_multas,
            vencendo=vencendo,
            movimentos=movimentos,
            active="dashboard",
        ),
    )


# =============================================================================
# Hóspedes
# =============================================================================
@app.get("/hospedes", response_class=HTMLResponse)
async def hospedes_list(request: Request, q: str = "", filtro: str = "todos"):
    if not _user(request):
        return _redirect_login()
    raw = sistema.buscar_filtrado(q, filtro)
    hospedes = [{"nome": h[0], "documento": h[1], "saldo": h[2]} for h in raw]
    return templates.TemplateResponse(
        request,
        "hospedes.html",
        _ctx(
            request,
            hospedes=hospedes,
            q=q,
            filtro=filtro,
            active="hospedes",
        ),
    )


@app.post("/hospedes")
async def hospedes_create(
    request: Request,
    nome: str = Form(...),
    documento: str = Form(...),
    telefone: str = Form(""),
    email: str = Form(""),
):
    u = _user(request)
    if not u:
        return _redirect_login()
    try:
        sistema.cadastrar_hospede(nome, documento, telefone=telefone, email=email, usuario_acao=u["username"])
        _flash(request, f"Hóspede '{nome}' cadastrado com sucesso.", "success")
    except ValueError as e:
        _flash(request, str(e), "danger")
    return RedirectResponse("/hospedes", status_code=302)


@app.post("/hospedes/{doc:path}/movimentacao")
async def hospede_mov(
    request: Request,
    doc: str,
    tipo: str = Form(...),
    valor: str = Form(...),
    categoria: str = Form(""),
    obs: str = Form(""),
):
    u = _user(request)
    if not u:
        return _redirect_login()
    try:
        if tipo == "MULTA":
            sistema.adicionar_multa(doc, valor, categoria, obs=obs, usuario=u["username"])
        elif tipo == "PAGAMENTO_MULTA":
            sistema.pagar_multa(doc, valor, categoria, obs=obs, usuario=u["username"])
        else:
            sistema.adicionar_movimentacao(doc, valor, categoria, tipo, obs=obs, usuario=u["username"])
        _flash(request, "Movimentação registrada com sucesso.", "success")
    except ValueError as e:
        _flash(request, str(e), "danger")
    return RedirectResponse(f"/hospedes/{doc}", status_code=302)


@app.post("/hospedes/{doc:path}/movimentacao/{id_mov}/vencimento")
async def hospede_alterar_vencimento(
    request: Request,
    doc: str,
    id_mov: int,
    nova_data: str = Form(...),
):
    u = _user(request)
    if not u:
        return _redirect_login()
    if not u.get("can_change_dates"):
        _flash(request, "Sem permissão para alterar datas de vencimento.", "danger")
        return RedirectResponse(f"/hospedes/{doc}", status_code=302)
    try:
        sistema.atualizar_data_vencimento_manual(id_mov, nova_data, usuario_acao=u["username"])
        _flash(request, "Data de vencimento atualizada.", "success")
    except ValueError as e:
        _flash(request, str(e), "danger")
    return RedirectResponse(f"/hospedes/{doc}", status_code=302)


@app.post("/hospedes/{doc:path}/anotacao")
async def hospede_anotacao(request: Request, doc: str, texto: str = Form("")):
    if not _user(request):
        return _redirect_login()
    sistema.salvar_anotacao(doc, texto)
    _flash(request, "Anotação salva.", "success")
    return RedirectResponse(f"/hospedes/{doc}", status_code=302)


@app.post("/hospedes/{doc:path}/inativar")
async def hospede_inativar(request: Request, doc: str):
    u = _user(request)
    if not u or not u.get("is_admin"):
        _flash(request, "Apenas administradores podem inativar hóspedes.", "warning")
        return RedirectResponse(f"/hospedes/{doc}", status_code=302)
    sistema.inativar_hospede(doc, usuario_acao=u["username"])
    _flash(request, "Hóspede inativado.", "success")
    return RedirectResponse("/hospedes", status_code=302)


@app.post("/hospedes/{doc:path}/reativar")
async def hospede_reativar(request: Request, doc: str):
    u = _user(request)
    if not u or not u.get("is_admin"):
        _flash(request, "Apenas administradores podem reativar hóspedes.", "warning")
        return RedirectResponse(f"/hospedes/{doc}", status_code=302)
    sistema.reativar_hospede(doc, usuario_acao=u["username"])
    _flash(request, "Hóspede reativado.", "success")
    return RedirectResponse(f"/hospedes/{doc}", status_code=302)


@app.post("/hospedes/{doc:path}/excluir")
async def hospede_excluir(request: Request, doc: str):
    u = _user(request)
    if not u or not u.get("is_admin"):
        _flash(request, "Apenas administradores podem excluir hóspedes.", "warning")
        return RedirectResponse(f"/hospedes/{doc}", status_code=302)
    sistema.excluir_hospede(doc, usuario_acao=u["username"])
    _flash(request, "Hóspede e todo o histórico excluídos.", "success")
    return RedirectResponse("/hospedes", status_code=302)


# =============================================================================
# Financeiro
# =============================================================================
@app.get("/financeiro", response_class=HTMLResponse)
async def financeiro(
    request: Request,
    filtro: str = "",
    tipo: str = "",
    data_inicio: str = "",
    data_fim: str = "",
):
    if not _user(request):
        return _redirect_login()
    tipos_filter = (tipo,) if tipo else None
    movimentos = sistema.get_historico_global(
        filtro=filtro,
        tipos=tipos_filter,
        data_inicio=data_inicio or None,
        data_fim=data_fim or None,
        limite=500,
    )
    return templates.TemplateResponse(
        request,
        "financeiro.html",
        _ctx(
            request,
            movimentos=movimentos,
            filtro=filtro,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            active="financeiro",
        ),
    )


# =============================================================================
# Compras
# =============================================================================
@app.get("/compras", response_class=HTMLResponse)
async def compras_list(request: Request):
    if not _user(request):
        return _redirect_login()
    listas = sistema.get_listas_resumo()
    return templates.TemplateResponse(
        request,
        "compras.html",
        _ctx(
            request,
            listas=listas,
            active="compras",
        ),
    )


@app.post("/compras")
async def compras_create(request: Request):
    u = _user(request)
    if not u:
        return _redirect_login()
    lista_id = sistema.criar_lista_compras(u["username"])
    return RedirectResponse(f"/compras/{lista_id}", status_code=302)


@app.get("/compras/{lista_id}", response_class=HTMLResponse)
async def compras_detalhe(request: Request, lista_id: int):
    if not _user(request):
        return _redirect_login()
    listas = sistema.get_listas_resumo()
    lista = next((item for item in listas if item["id"] == lista_id), None)
    if not lista:
        _flash(request, "Lista não encontrada.", "warning")
        return RedirectResponse("/compras", status_code=302)
    itens = sistema.get_itens_lista(lista_id)
    produtos = sistema.get_produtos_predefinidos()
    nomes_itens = list({item["produto"] for item in itens})
    historico_precos = sistema.get_historico_precos(nomes_itens)
    return templates.TemplateResponse(
        request,
        "compras_detalhe.html",
        _ctx(
            request,
            lista=lista,
            itens=itens,
            produtos=produtos,
            historico_precos=historico_precos,
            active="compras",
        ),
    )


@app.post("/compras/{lista_id}/item")
async def compras_add_item(
    request: Request,
    lista_id: int,
    data: str = Form(...),
    produto: str = Form(...),
    quantidade: str = Form(...),
    valor: str = Form(...),
):
    if not _user(request):
        return _redirect_login()
    try:
        sistema.adicionar_compra(data, produto, quantidade, valor, lista_id=lista_id)
        _flash(request, "Item adicionado.", "success")
    except Exception as e:
        _flash(request, str(e), "danger")
    return RedirectResponse(f"/compras/{lista_id}", status_code=302)


@app.post("/compras/{lista_id}/fechar")
async def compras_fechar(request: Request, lista_id: int):
    if not _user(request):
        return _redirect_login()
    sistema.fechar_lista_compras(lista_id)
    _flash(request, "Lista fechada com sucesso.", "success")
    return RedirectResponse("/compras", status_code=302)


# =============================================================================
# Relatórios
# =============================================================================
@app.get("/relatorios", response_class=HTMLResponse)
async def relatorios(request: Request, doc: str = "", mes: str = ""):
    if not _user(request):
        return _redirect_login()
    inadimplentes_raw = sistema.buscar_filtrado("", "vencidos")
    inadimplentes = [{"nome": h[0], "documento": h[1], "saldo": h[2]} for h in inadimplentes_raw]
    extrato: list = []
    hospede_extrato = None
    if doc:
        hospede_extrato = sistema.get_hospede(doc)
        extrato = sistema.get_historico_detalhado(doc)
    mensal: list = []
    if mes:
        mensal = sistema.get_historico_global(data_inicio=f"{mes}-01", data_fim=f"{mes}-31", limite=500)
    return templates.TemplateResponse(
        request,
        "relatorios.html",
        _ctx(
            request,
            inadimplentes=inadimplentes,
            extrato=extrato,
            hospede_extrato=hospede_extrato,
            doc=doc,
            mes=mes,
            mensal=mensal,
            active="relatorios",
        ),
    )


# =============================================================================
# Ajustes
# =============================================================================
@app.get("/ajustes", response_class=HTMLResponse)
async def ajustes(request: Request, tab: str = ""):
    u = _user(request)
    if not u:
        return _redirect_login()
    is_admin = u.get("is_admin")
    default_tab = "geral" if is_admin else "senha"
    can_manage = is_admin or u.get("can_manage_products")
    ctx: dict = dict(
        tab=tab or default_tab,
        active="ajustes",
        can_manage=can_manage,
        empresa=sistema.empresa,
        versao=sistema.versao_atual,
    )
    if is_admin:
        ctx.update(
            usuarios=sistema.get_usuarios(),
            logs=sistema.get_logs(),
            categorias=sistema.get_categorias(),
            produtos=sistema.get_produtos_predefinidos(),
            config_validade=sistema.get_config("validade_meses"),
            config_alerta=sistema.get_config("alerta_dias"),
        )
    return templates.TemplateResponse(request, "ajustes.html", _ctx(request, **ctx))


@app.post("/ajustes/usuario")
async def ajustes_usuario_salvar(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form("0"),
    can_change_dates: str = Form("0"),
    can_manage_products: str = Form("0"),
    can_access_hospedes: str = Form("1"),
    can_access_financeiro: str = Form("1"),
    can_access_compras: str = Form("1"),
    can_access_dash: str = Form("1"),
    can_access_relatorios: str = Form("1"),
):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    try:
        sistema.salvar_usuario(
            username=username,
            password=password,
            is_admin=bool(int(is_admin)),
            can_change_dates=bool(int(can_change_dates)),
            can_manage_products=bool(int(can_manage_products)),
            can_access_hospedes=bool(int(can_access_hospedes)),
            can_access_financeiro=bool(int(can_access_financeiro)),
            can_access_compras=bool(int(can_access_compras)),
            can_access_dash=bool(int(can_access_dash)),
            can_access_relatorios=bool(int(can_access_relatorios)),
            usuario_acao=u["username"],
        )
        _flash(request, f"Usuário '{username}' salvo com sucesso.", "success")
    except Exception as e:
        _flash(request, str(e), "danger")
    return RedirectResponse("/ajustes", status_code=302)


@app.post("/ajustes/usuario/{username}/editar")
async def ajustes_usuario_editar(
    request: Request,
    username: str,
    password: str = Form(""),
    is_admin: str = Form("0"),
    can_change_dates: str = Form("0"),
    can_manage_products: str = Form("0"),
    can_access_hospedes: str = Form("1"),
    can_access_financeiro: str = Form("1"),
    can_access_compras: str = Form("1"),
    can_access_dash: str = Form("1"),
    can_access_relatorios: str = Form("1"),
):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    try:
        if password:
            # Atualiza tudo incluindo senha
            sistema.salvar_usuario(
                username=username,
                password=password,
                is_admin=bool(int(is_admin)),
                can_change_dates=bool(int(can_change_dates)),
                can_manage_products=bool(int(can_manage_products)),
                can_access_hospedes=bool(int(can_access_hospedes)),
                can_access_financeiro=bool(int(can_access_financeiro)),
                can_access_compras=bool(int(can_access_compras)),
                can_access_dash=bool(int(can_access_dash)),
                can_access_relatorios=bool(int(can_access_relatorios)),
                usuario_acao=u["username"],
            )
        else:
            # Atualiza só permissões, mantém senha atual
            sistema.atualizar_permissoes_usuario(
                username=username,
                is_admin=int(is_admin),
                can_change_dates=int(can_change_dates),
                can_manage_products=int(can_manage_products),
                can_access_hospedes=int(can_access_hospedes),
                can_access_financeiro=int(can_access_financeiro),
                can_access_compras=int(can_access_compras),
                can_access_dash=int(can_access_dash),
                can_access_relatorios=int(can_access_relatorios),
                usuario_acao=u["username"],
            )
        _flash(request, f"Usuário '{username}' atualizado.", "success")
        # Se editou a si mesmo, atualiza a sessão
        if username == u["username"]:
            updated = sistema.get_usuarios()
            for usr in updated:
                if usr["username"] == username:
                    request.session["user"] = usr
                    break
    except Exception as e:
        _flash(request, str(e), "danger")
    return RedirectResponse("/ajustes", status_code=302)


# ── Config geral ─────────────────────────────────────────────────────────────
@app.post("/ajustes/config")
async def ajustes_config(
    request: Request,
    validade_meses: int = Form(...),
    alerta_dias: int = Form(...),
):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    try:
        if not (1 <= validade_meses <= 120):
            raise ValueError("Validade deve ser entre 1 e 120 meses.")
        if not (1 <= alerta_dias <= 365):
            raise ValueError("Alerta deve ser entre 1 e 365 dias.")
        sistema.set_config("validade_meses", validade_meses, u["username"])
        sistema.set_config("alerta_dias", alerta_dias, u["username"])
        _flash(request, "Configurações salvas.", "success")
    except (ValueError, Exception) as e:
        _flash(request, str(e), "danger")
    return RedirectResponse("/ajustes?tab=geral", status_code=302)


# ── Categorias ────────────────────────────────────────────────────────────────
@app.post("/ajustes/categoria")
async def categoria_add(request: Request, nome: str = Form(...)):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    sistema.adicionar_categoria(nome.strip())
    _flash(request, f"Categoria '{nome}' adicionada.", "success")
    return RedirectResponse("/ajustes?tab=categorias", status_code=302)


@app.post("/ajustes/categoria/{nome}/excluir")
async def categoria_del(request: Request, nome: str):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    sistema.remover_categoria(nome)
    _flash(request, f"Categoria '{nome}' removida.", "success")
    return RedirectResponse("/ajustes?tab=categorias", status_code=302)


# ── Produtos ──────────────────────────────────────────────────────────────────
@app.post("/ajustes/produto")
async def produto_add(request: Request, nome: str = Form(...)):
    u = _user(request)
    if not u or not (u.get("is_admin") or u.get("can_manage_products")):
        _flash(request, "Sem permissão para gerenciar produtos.", "danger")
        return RedirectResponse("/ajustes?tab=produtos", status_code=302)
    sistema.adicionar_produto_predefinido(nome.strip())
    _flash(request, f"Produto '{nome}' adicionado.", "success")
    return RedirectResponse("/ajustes?tab=produtos", status_code=302)


@app.post("/ajustes/produto/{nome}/excluir")
async def produto_del(request: Request, nome: str):
    u = _user(request)
    if not u or not (u.get("is_admin") or u.get("can_manage_products")):
        _flash(request, "Sem permissão para gerenciar produtos.", "danger")
        return RedirectResponse("/ajustes?tab=produtos", status_code=302)
    sistema.remover_produto_predefinido(nome)
    _flash(request, f"Produto '{nome}' removido.", "success")
    return RedirectResponse("/ajustes?tab=produtos", status_code=302)


# ── Banco de dados ────────────────────────────────────────────────────────────
@app.post("/ajustes/banco/backup")
async def banco_backup(request: Request):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    try:
        caminho = sistema.db.fazer_backup()
        _flash(request, f"Backup salvo em: {caminho}", "success")
    except Exception as e:
        _flash(request, f"Erro ao fazer backup: {e}", "danger")
    return RedirectResponse("/ajustes?tab=banco", status_code=302)


@app.post("/ajustes/banco/otimizar")
async def banco_otimizar(request: Request):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    try:
        sistema.db.otimizar()
        _flash(request, "Banco otimizado com sucesso.", "success")
    except Exception as e:
        _flash(request, f"Erro ao otimizar: {e}", "danger")
    return RedirectResponse("/ajustes?tab=banco", status_code=302)


# ── Limpeza de hóspede por documento (bypassa problemas de URL) ───────────────
@app.post("/ajustes/hospede-excluir")
async def ajustes_hospede_excluir(request: Request, documento: str = Form(...)):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    doc = documento.strip()
    hospede = sistema.get_hospede(doc)
    if not hospede:
        _flash(request, f"Hóspede com documento '{doc}' não encontrado.", "warning")
        return RedirectResponse("/ajustes?tab=banco", status_code=302)
    nome = hospede.get("nome", doc)
    sistema.excluir_hospede(doc, usuario_acao=u["username"])
    _flash(request, f"Hóspede '{nome}' excluído com sucesso.", "success")
    return RedirectResponse("/ajustes?tab=banco", status_code=302)


# ── Logs ──────────────────────────────────────────────────────────────────────
@app.post("/ajustes/logs/limpar")
async def logs_limpar(request: Request):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    sistema.limpar_logs_auditoria(u["username"])
    _flash(request, "Logs de auditoria limpos.", "success")
    return RedirectResponse("/ajustes?tab=logs", status_code=302)


@app.post("/ajustes/usuario/{username}/excluir")
async def ajustes_usuario_excluir(request: Request, username: str):
    u = _user(request)
    if not u or not u.get("is_admin"):
        return _redirect_login()
    if username == u["username"]:
        _flash(request, "Não é possível excluir o próprio usuário.", "danger")
        return RedirectResponse("/ajustes", status_code=302)
    sistema.excluir_usuario(username, usuario_acao=u["username"])
    _flash(request, f"Usuário '{username}' excluído.", "success")
    return RedirectResponse("/ajustes", status_code=302)


@app.post("/ajustes/minha-senha")
async def ajustes_minha_senha(
    request: Request,
    senha_atual: str = Form(...),
    nova_senha: str = Form(...),
    confirmar_senha: str = Form(...),
):
    u = _user(request)
    if not u:
        return _redirect_login()
    if nova_senha != confirmar_senha:
        _flash(request, "As senhas não coincidem.", "danger")
        return RedirectResponse("/ajustes?tab=senha", status_code=302)
    if len(nova_senha) < 4:
        _flash(request, "A senha deve ter pelo menos 4 caracteres.", "danger")
        return RedirectResponse("/ajustes?tab=senha", status_code=302)
    if not sistema.verificar_login(u["username"], senha_atual):
        _flash(request, "Senha atual incorreta.", "danger")
        return RedirectResponse("/ajustes?tab=senha", status_code=302)
    sistema.alterar_senha(u["username"], nova_senha, usuario_acao=u["username"])
    _flash(request, "Senha alterada com sucesso.", "success")
    return RedirectResponse("/ajustes?tab=senha", status_code=302)


# =============================================================================
# Exportações — PDF e CSV
# =============================================================================


@app.get("/hospedes/{doc:path}/extrato.pdf")
async def hospede_extrato_pdf(request: Request, doc: str):
    if not _user(request):
        return _redirect_login()
    hospede = sistema.get_hospede(doc)
    if not hospede:
        return RedirectResponse("/hospedes", status_code=302)
    movimentos = sistema.get_historico_detalhado(doc)
    saldo, venc, bloqueado = sistema.get_saldo_info(doc)
    data = pdf_extrato(hospede, movimentos, saldo, venc, bloqueado, sistema.empresa)
    nome = hospede.get("nome", doc).replace(" ", "_")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=extrato_{nome}.pdf"},
    )


# Rota de detalhe APÓS extrato.pdf para que {doc:path} não engula o sufixo /extrato.pdf
@app.get("/hospedes/{doc:path}", response_class=HTMLResponse)
async def hospede_detalhe(request: Request, doc: str):
    if not _user(request):
        return _redirect_login()
    hospede = sistema.get_hospede(doc)
    if not hospede:
        _flash(request, "Hóspede não encontrado.", "warning")
        return RedirectResponse("/hospedes", status_code=302)
    saldo, vencimento, bloqueado = sistema.get_saldo_info(doc)
    historico = sistema.get_historico_detalhado(doc)
    multa = sistema.get_divida_multas(doc)
    anotacao = sistema.get_anotacao(doc)
    categorias = sistema.get_categorias()
    return templates.TemplateResponse(
        request,
        "hospede_detalhe.html",
        _ctx(
            request,
            hospede=dict(hospede),
            saldo=saldo,
            vencimento=vencimento,
            bloqueado=bloqueado,
            historico=historico,
            multa=multa,
            anotacao=anotacao,
            categorias=categorias,
            active="hospedes",
        ),
    )


@app.get("/relatorios/mensal.pdf")
async def relatorio_mensal_pdf(request: Request, mes: str = ""):
    if not _user(request):
        return _redirect_login()
    if not mes:
        mes = __import__("datetime").datetime.now().strftime("%m/%Y")
    try:
        from datetime import datetime as _dt

        dt = _dt.strptime(mes, "%m/%Y")
        inicio = dt.strftime("%Y-%m-01")
        fim = f"{dt.year}-{dt.month + 1:02d}-01" if dt.month < 12 else f"{dt.year + 1}-01-01"
    except ValueError:
        return RedirectResponse("/relatorios", status_code=302)
    movimentos = sistema.get_historico_global(data_inicio=inicio, data_fim=fim, limite=1000)
    data = pdf_mensal(mes, movimentos, sistema.empresa)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=mensal_{mes.replace('/', '-')}.pdf"},
    )


@app.get("/relatorios/inadimplentes.pdf")
async def relatorio_inadimplentes_pdf(request: Request):
    if not _user(request):
        return _redirect_login()
    devedores = sistema.get_devedores_multas()
    if not devedores:
        _flash(request, "Nenhum inadimplente encontrado.", "info")
        return RedirectResponse("/relatorios", status_code=302)
    data = pdf_inadimplentes(devedores, sistema.empresa)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=inadimplentes.pdf"},
    )


@app.get("/hospedes/exportar.csv")
async def hospedes_csv(request: Request):
    if not _user(request):
        return _redirect_login()
    hospedes_raw = sistema.buscar_filtrado("", "todos")
    output = io.StringIO()
    w = _csv.writer(output)
    w.writerow(["Nome", "Documento", "Saldo", "Vencimento", "Status"])
    for nome, doc, saldo in hospedes_raw:
        _, venc, bloqueado = sistema.get_saldo_info(doc)
        status = "VENCIDO" if bloqueado else ("ATIVO" if saldo > 0 else "SEM SALDO")
        w.writerow([nome, doc, f"{saldo:.2f}", venc, status])
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hospedes.csv"},
    )


@app.get("/relatorios/exportar.csv")
async def relatorio_csv(request: Request, mes: str = ""):
    if not _user(request):
        return _redirect_login()
    kwargs: dict = {"limite": 5000}
    if mes:
        try:
            from datetime import datetime as _dt

            dt = _dt.strptime(mes, "%m/%Y")
            kwargs["data_inicio"] = dt.strftime("%Y-%m-01")
            kwargs["data_fim"] = f"{dt.year}-{dt.month + 1:02d}-01" if dt.month < 12 else f"{dt.year + 1}-01-01"
        except ValueError:
            pass
    movimentos = sistema.get_historico_global(**kwargs)
    output = io.StringIO()
    w = _csv.writer(output)
    w.writerow(["Data", "Hospede", "Documento", "Tipo", "Valor", "Categoria", "Obs", "Usuario"])
    for m in movimentos:
        w.writerow(
            [
                m.get("data_acao", ""),
                m.get("nome", ""),
                m.get("documento", ""),
                m.get("tipo", ""),
                m.get("valor", ""),
                m.get("categoria", "") or "",
                m.get("obs", "") or "",
                m.get("usuario", "") or "",
            ]
        )
    fname = f"financeiro_{mes.replace('/', '-')}.csv" if mes else "financeiro.csv"
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
