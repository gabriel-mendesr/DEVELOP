"""
fix_por_linha.py — Corrige erros por número de linha (imune a reformatação)
═══════════════════════════════════════════════════════════════════════════════

Ao invés de procurar texto exato (que falha quando ruff-format muda
espaçamento/aspas), este script mostra o conteúdo atual de cada linha
problemática e aplica a correção cirúrgica.

COMO RODAR:
  cd /home/gabrielmendes/develop
  python fix_por_linha.py
"""

import os
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────


def ler_linhas(caminho: str) -> list[str]:
    with open(caminho, encoding="utf-8") as f:
        return f.readlines()


def gravar_linhas(caminho: str, linhas: list[str]) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        f.writelines(linhas)


def mostrar_linha(caminho: str, numero: int, contexto: int = 1) -> None:
    """Mostra uma linha e seu contexto (para diagnóstico)."""
    linhas = ler_linhas(caminho)
    inicio = max(0, numero - contexto - 1)
    fim = min(len(linhas), numero + contexto)
    for i, linha in enumerate(linhas[inicio:fim], inicio + 1):
        marcador = ">>>" if i == numero else "   "
        print(f"       {marcador} {i:4d}: {linha}", end="")


def substituir_linha(caminho: str, numero: int, nova_linha: str, descricao: str) -> bool:
    """
    Substitui a linha `numero` (1-based) por `nova_linha`.
    Preserva a indentação original se nova_linha não tiver '\n' no fim.
    """
    linhas = ler_linhas(caminho)
    idx = numero - 1

    if idx >= len(linhas):
        print(f"  ❌ Linha {numero} não existe em {os.path.relpath(caminho)}")
        return False

    original = linhas[idx]

    # Preserva newline do arquivo original
    if not nova_linha.endswith("\n"):
        nova_linha += "\n"

    if original == nova_linha:
        print(f"  ✅ Já correto ({descricao})")
        return False

    print(f"  ✅ {descricao}")
    print(f"       - {original.rstrip()}")
    print(f"       + {nova_linha.rstrip()}")

    linhas[idx] = nova_linha
    gravar_linhas(caminho, linhas)
    return True


def encontrar_linha_com(caminho: str, texto: str, a_partir: int = 1) -> int:
    """
    Encontra o número da primeira linha que contém `texto`,
    começando de `a_partir`. Retorna -1 se não encontrar.
    """
    linhas = ler_linhas(caminho)
    for i, linha in enumerate(linhas[a_partir - 1 :], a_partir):
        if texto in linha:
            return i
    return -1


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNÓSTICO: mostra as linhas problemáticas antes de corrigir
# ─────────────────────────────────────────────────────────────────────────────

print()
print("═" * 60)
print("  fix_por_linha.py — diagnóstico e correção")
print("═" * 60)

erros = {
    os.path.join(BASE, "app", "core", "database.py"): [199],
    os.path.join(BASE, "app", "app_gui.py"): [1048, 1049, 1050, 2205],
    os.path.join(BASE, "app", "update_manager.py"): [25],
    os.path.join(BASE, "tests", "verificar_sistema.py"): [839, 850, 991, 1004],
}

print("\n  Linhas problemáticas atuais:")
for caminho, numeros in erros.items():
    rel = os.path.relpath(caminho, BASE)
    print(f"\n  📄 {rel}")
    if os.path.isfile(caminho):
        for n in numeros:
            mostrar_linha(caminho, n, contexto=0)
    else:
        print(f"     (não encontrado)")


# ─────────────────────────────────────────────────────────────────────────────
# CORREÇÕES
# ─────────────────────────────────────────────────────────────────────────────

print()
print("─" * 60)
print("  Aplicando correções...")
print("─" * 60)


# ── 1. database.py — mypy: os.getenv retorna str|None ────────────────────────
#
# Não sabemos o número exato depois das reformatações, então buscamos o texto.
db = os.path.join(BASE, "app", "core", "database.py")
n = encontrar_linha_com(db, "os.getenv('APPDATA')")
if n > 0:
    linhas = ler_linhas(db)
    linha_atual = linhas[n - 1]
    indent = len(linha_atual) - len(linha_atual.lstrip())
    nova = (
        " " * indent
        + "app_data: str = (os.environ.get('APPDATA') or os.path.expanduser('~')) "
        + "if os.name == 'nt' else os.path.expanduser('~')\n"
    )
    substituir_linha(db, n, nova, f"database.py:{n} — app_data: str garantida")
else:
    print(f"  ✅ database.py — os.getenv já foi corrigido anteriormente")


# ── 2. update_manager.py — Optional não usado ────────────────────────────────
upd = os.path.join(BASE, "app", "update_manager.py")
n = encontrar_linha_com(upd, "Optional")
if n > 0:
    linhas = ler_linhas(upd)
    linha_atual = linhas[n - 1]
    # Remove apenas ", Optional" ou "Optional, " da linha de import
    nova = linha_atual.replace(", Optional", "").replace("Optional, ", "").replace("from typing import Optional\n", "")
    if nova != linha_atual:
        substituir_linha(upd, n, nova, f"update_manager.py:{n} — Optional removido")
    else:
        print(f"  ✅ update_manager.py — Optional já removido")


# ── 3. app_gui.py — `l` no loop (F821) e `e` não usada (F841) ───────────────
gui = os.path.join(BASE, "app", "app_gui.py")

# Busca o for loop com `l` (que não foi renomeado pelos scripts anteriores)
# Procura a linha que tem "for l in" OU variável `l[` usada
n_for = encontrar_linha_com(gui, "for l in listas")
if n_for > 0:
    linhas = ler_linhas(gui)
    indent = len(linhas[n_for - 1]) - len(linhas[n_for - 1].lstrip())
    substituir_linha(gui, n_for, " " * indent + "for lista in listas:\n", f"app_gui.py:{n_for} — for l → for lista")
    # Corrige as linhas seguintes que usam `l[` dentro do loop
    for offset in range(1, 6):
        idx = n_for + offset
        if idx <= len(linhas):
            linha = linhas[idx - 1]  # re-lê (arquivo pode ter mudado)
        else:
            break
        # Re-lê após possível modificação anterior
        linhas_atuais = ler_linhas(gui)
        linha = linhas_atuais[idx - 1]

        if "l[" in linha or "l['" in linha or 'l["' in linha:
            nova = linha.replace("l[", "lista[")
            substituir_linha(gui, idx, nova, f"app_gui.py:{idx} — l[ → lista[")
        elif "l[" not in linha and "for" not in linha and linha.strip() and "lista" not in linha:
            break
else:
    print(f"  ✅ app_gui.py — for loop já corrigido")

# F841: `except Exception as e` onde `e` não é usado
# Busca a partir da linha 2200 para não pegar outros excepts
n_e = encontrar_linha_com(gui, "except Exception as e:", a_partir=2195)
if n_e > 0:
    linhas = ler_linhas(gui)
    linha_atual = linhas[n_e - 1]
    indent = len(linha_atual) - len(linha_atual.lstrip())
    nova = " " * indent + "except Exception:\n"
    substituir_linha(gui, n_e, nova, f"app_gui.py:{n_e} — except e não usado → except")
else:
    print(f"  ✅ app_gui.py:{2205} — except já corrigido")


# ── 4. verificar_sistema.py — `l` undefined ──────────────────────────────────
vs = os.path.join(BASE, "tests", "verificar_sistema.py")

# Encontra e corrige todos os `for l in` e usos de `l[` no arquivo
linhas = ler_linhas(vs)
nova_linhas = []
corrigiu = False
for i, linha in enumerate(linhas, 1):
    nova = linha
    # for l in ... → for lista in ...
    if "for l in " in nova:
        nova = nova.replace("for l in ", "for lista in ")
        corrigiu = True
    # usos de l[ fora de for (dentro de loops renomeados)
    if " l[" in nova and "for " not in nova:
        nova = nova.replace(" l[", " lista[")
        corrigiu = True
    if "\tl[" in nova:
        nova = nova.replace("\tl[", "\tlista[")
        corrigiu = True
    nova_linhas.append(nova)

if corrigiu:
    gravar_linhas(vs, nova_linhas)
    print(f"  ✅ verificar_sistema.py — todas as ocorrências de `l` → `lista`")
else:
    print(f"  ✅ verificar_sistema.py — `l` já corrigido")


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICAÇÃO FINAL com ruff
# ─────────────────────────────────────────────────────────────────────────────

print()
print("─" * 60)
print("  Verificando com ruff...")

result = subprocess.run(["ruff", "check", "app/", "tests/", "--quiet"], capture_output=True, text=True, cwd=BASE)

if result.returncode == 0:
    print("  ✅ Nenhum erro ruff restante!")
else:
    linhas_erro = [l for l in result.stdout.splitlines() if ".py:" in l]
    print(f"  ⚠️  {len(linhas_erro)} erro(s) ainda pendentes:")
    for linha in linhas_erro:
        print(f"     {linha}")

print()
print("─" * 60)
print("  git add -A")
print("  git commit -m 'fix: corrige todos os erros ruff e mypy'")
print("  git push origin main")
print("─" * 60)
print()
