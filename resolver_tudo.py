#!/usr/bin/env python3
"""
resolver_tudo.py — Resolve todos os erros pendentes antes do commit
════════════════════════════════════════════════════════════════════

O QUE ESTE SCRIPT FAZ (em ordem):
  1. Corrige permissão do setup.iss (bloqueava o pre-commit)
  2. Corrige o erro mypy em database.py (os.getenv → str garantido)
  3. Remove imports não usados e deprecated em core/, screens/, update_manager.py
  4. Corrige variáveis ambíguas e f-strings no tests/verificar_sistema.py
  5. Adiciona # noqa nos erros do app_gui.py (arquivo legado — não refatorar)
  6. Imprime os comandos git para finalizar

COMO RODAR:
  cd /home/gabrielmendes/develop
  python resolver_tudo.py
"""

import os
import stat
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(BASE, "app")
TESTS = os.path.join(BASE, "tests")

erros = []


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────


def ler(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def gravar(caminho: str, conteudo: str) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def corrigir_arquivo(caminho: str, substituicoes: list[tuple[str, str]], titulo: str) -> None:
    """Aplica substituições exatas num arquivo e reporta."""
    if not os.path.isfile(caminho):
        print(f"  ⏭️  Não encontrado: {os.path.relpath(caminho)}")
        return

    original = ler(caminho)
    atual = original

    aplicadas = []
    for velho, novo in substituicoes:
        if velho in atual:
            atual = atual.replace(velho, novo, 1)
            aplicadas.append(velho.strip().split("\n")[0][:80])

    if atual == original:
        print(f"  ✅ Já correto: {titulo}")
        return

    gravar(caminho, atual)
    print(f"  ✅ {titulo} ({len(aplicadas)} correção/ões)")
    for linha in aplicadas:
        print(f"       · {linha}")


def secao(titulo: str) -> None:
    print(f"\n{'─' * 56}")
    print(f"  {titulo}")
    print(f"{'─' * 56}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. PERMISSÃO — setup.iss
# ─────────────────────────────────────────────────────────────────────────────

secao("1. Permissão — setup.iss")

iss = os.path.join(APP, "setup.iss")
if os.path.isfile(iss):
    try:
        os.chmod(iss, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        print(f"  ✅ Permissão corrigida: app/setup.iss")
    except OSError as exc:
        print(f"  ⚠️  Não foi possível corrigir permissão: {exc}")
        print(f"     Tente: sudo chmod 644 app/setup.iss")
else:
    print(f"  ⏭️  setup.iss não encontrado")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MYPY — database.py (os.getenv → str garantido)
# ─────────────────────────────────────────────────────────────────────────────

secao("2. Mypy — database.py")

db = os.path.join(APP, "core", "database.py")

# Lê o arquivo linha a linha para encontrar e corrigir com precisão
if os.path.isfile(db):
    linhas = ler(db).splitlines(keepends=True)
    novo = []
    corrigiu = False
    for linha in linhas:
        # Linha problemática: app_data = os.getenv('APPDATA') ...
        # Mypy reclama porque os.getenv retorna str | None
        # Solução: usar os.environ.get com fallback garantido
        if "app_data" in linha and "os.getenv('APPDATA')" in linha and "or" not in linha:
            indentacao = len(linha) - len(linha.lstrip())
            nova_linha = (
                " " * indentacao
                + "app_data: str = (os.environ.get('APPDATA') or os.path.expanduser('~')) "
                + "if os.name == 'nt' else os.path.expanduser('~')\n"
            )
            novo.append(nova_linha)
            corrigiu = True
        else:
            novo.append(linha)

    if corrigiu:
        gravar(db, "".join(novo))
        print("  ✅ database.py — app_data: str garantida")
    else:
        print("  ✅ Já correto: database.py")
else:
    print("  ⏭️  database.py não encontrado")


# ─────────────────────────────────────────────────────────────────────────────
# 3. RUFF — core/database.py (imports não usados)
# ─────────────────────────────────────────────────────────────────────────────

secao("3. Ruff — core/database.py")

corrigir_arquivo(
    db,
    [
        # F401: pathlib.Path importado mas não usado
        ("from pathlib import Path\n", ""),
        # F401: typing.Optional importado mas não usado
        (", Optional", ""),
        ("from typing import Optional\n", ""),
    ],
    "database.py — imports não usados",
)


# ─────────────────────────────────────────────────────────────────────────────
# 4. RUFF — core/models.py
# ─────────────────────────────────────────────────────────────────────────────

secao("4. Ruff — core/models.py")

models = os.path.join(APP, "core", "models.py")

corrigir_arquivo(
    models,
    [
        # UP035: Dict, List, Tuple deprecados — usa built-ins
        # A linha de import é algo como:
        # from typing import Any, Dict, List, Optional, Tuple
        # Precisamos remover Dict, List, Tuple e manter Any e Optional
        ("from typing import Any, Dict, List, Optional, Tuple\n", "from typing import Any, Optional\n"),
        ("from typing import Any, Dict, List, Optional, Tuple, Union\n", "from typing import Any, Optional, Union\n"),
        # Caso o ruff já tenha removido alguns:
        ("from typing import Dict, List, Tuple\n", ""),
        (", Dict, List, Tuple", ""),
        (", Dict", ""),
        (", List", ""),
        (", Tuple", ""),
        # UP038: isinstance com tupla → usa X | Y
        ("isinstance(valor, (int, float))", "isinstance(valor, int | float)"),
    ],
    "models.py — typing deprecated e isinstance",
)


# ─────────────────────────────────────────────────────────────────────────────
# 5. RUFF — update_manager.py
# ─────────────────────────────────────────────────────────────────────────────

secao("5. Ruff — update_manager.py")

upd = os.path.join(APP, "update_manager.py")

corrigir_arquivo(
    upd,
    [
        # F401: imports não usados
        ("import json\n", ""),
        ("from datetime import datetime\n", ""),
        ("from pathlib import Path\n", ""),
        # UP035: Tuple deprecado
        ("from typing import Optional, Tuple, Callable\n", "from typing import Optional, Callable\n"),
        ("from typing import Tuple, Optional, Callable\n", "from typing import Optional, Callable\n"),
        (", Tuple", ""),
        # Tuple nos type hints → tuple
        (") -> Tuple[bool, Optional[str], Optional[str]]:", ") -> tuple[bool, Optional[str], Optional[str]]:"),
    ],
    "update_manager.py — imports não usados e Tuple deprecado",
)


# ─────────────────────────────────────────────────────────────────────────────
# 6. RUFF — screens/
# ─────────────────────────────────────────────────────────────────────────────

secao("6. Ruff — screens/")

# base.py
corrigir_arquivo(
    os.path.join(APP, "screens", "base.py"),
    [
        ("import tkinter as tk\n", ""),
        ("from typing import Optional, Callable\n", "from typing import Callable\n"),
        ("from typing import Optional\n", ""),
        (", Optional", ""),
    ],
    "screens/base.py",
)

# compras.py
corrigir_arquivo(
    os.path.join(APP, "screens", "compras.py"),
    [
        ("from tkinter import ttk, messagebox\n", "from tkinter import messagebox\n"),
        ("from tkinter import ttk\n", ""),
        (", ttk", ""),
    ],
    "screens/compras.py",
)

# config.py
corrigir_arquivo(
    os.path.join(APP, "screens", "config.py"),
    [
        ("from datetime import datetime\n", ""),
        ("from tkinter import ttk, messagebox, filedialog\n", "from tkinter import messagebox, filedialog\n"),
        (", ttk", ""),
    ],
    "screens/config.py",
)

# financeiro.py
corrigir_arquivo(
    os.path.join(APP, "screens", "financeiro.py"),
    [
        ("import tkinter as tk\n", ""),
        ("from tkinter import ttk\n", ""),
        ("from tkinter import ttk, messagebox\n", "from tkinter import messagebox\n"),
        (", ttk", ""),
    ],
    "screens/financeiro.py",
)

# hospedes.py — F401 ttk e F841 status_txt
corrigir_arquivo(
    os.path.join(APP, "screens", "hospedes.py"),
    [
        ("from tkinter import ttk\n", ""),
        ("from tkinter import ttk, messagebox\n", "from tkinter import messagebox\n"),
        (", ttk", ""),
    ],
    "screens/hospedes.py — import ttk",
)

# hospedes.py — F841: status_txt atribuído mas nunca lido
hsp = os.path.join(APP, "screens", "hospedes.py")
if os.path.isfile(hsp):
    linhas = ler(hsp).splitlines(keepends=True)
    novo = []
    corrigiu = False
    for linha in linhas:
        # Remove a linha de atribuição da variável não usada
        if (
            "status_txt" in linha
            and "=" in linha
            and "status_txt" not in "".join([l for l in linhas if "status_txt" in l and "=" not in l])
        ):
            novo.append("        # " + linha.lstrip())  # comenta a linha
            corrigiu = True
        else:
            novo.append(linha)
    if corrigiu:
        gravar(hsp, "".join(novo))
        print("  ✅ screens/hospedes.py — status_txt (F841)")


# ─────────────────────────────────────────────────────────────────────────────
# 7. RUFF — tests/verificar_sistema.py
# ─────────────────────────────────────────────────────────────────────────────

secao("7. Ruff — tests/verificar_sistema.py")

vs = os.path.join(TESTS, "verificar_sistema.py")
if os.path.isfile(vs):
    linhas = ler(vs).splitlines(keepends=True)
    novo = []
    corrigiu = False

    for i, linha in enumerate(linhas):
        nova = linha

        # E741: variável ambígua `l` → renomeia para `lista`
        # Ocorre em: for l in ...: e  assert ... l ...
        if " l " in nova and ("for l " in nova or "in l " in nova or "len(l)" in nova):
            nova = nova.replace(" l ", " lista ").replace("(l)", "(lista)")
            corrigiu = True

        # E741: for l in listas → for lista in listas
        if "for l in" in nova:
            nova = nova.replace("for l in", "for lista in")
            corrigiu = True

        # UP038: isinstance com tupla
        if "isinstance(" in nova and "(int, float)" in nova:
            nova = nova.replace("isinstance(v, (int, float))", "isinstance(v, int | float)")
            nova = nova.replace("isinstance(valor, (int, float))", "isinstance(valor, int | float)")
            corrigiu = True

        # F541: f-string sem placeholder
        # Substitui f"texto" por "texto"
        if 'f"' in nova and "{" not in nova:
            nova = nova.replace('f"', '"')
            corrigiu = True
        if "f'" in nova and "{" not in nova:
            nova = nova.replace("f'", "'")
            corrigiu = True

        novo.append(nova)

    # E402: imports fora do topo — o from core.database import está no meio
    # Adiciona # noqa: E402 nas linhas afetadas
    resultado = []
    passou_imports_core = False
    for linha in novo:
        if ("from core." in linha or "from __version__" in linha) and "import" in linha:
            if "# noqa" not in linha:
                linha = linha.rstrip("\n") + "  # noqa: E402\n"
            passou_imports_core = True
        resultado.append(linha)

    if corrigiu or resultado != novo:
        gravar(vs, "".join(resultado))
        print("  ✅ verificar_sistema.py — E741, UP038, F541, E402")
    else:
        print("  ✅ Já correto: verificar_sistema.py")


# ─────────────────────────────────────────────────────────────────────────────
# 8. RUFF — app_gui.py (arquivo legado — adiciona # noqa cirúrgico)
# ─────────────────────────────────────────────────────────────────────────────

secao("8. Ruff — app_gui.py (noqa cirúrgico)")

gui = os.path.join(APP, "app_gui.py")
if os.path.isfile(gui):
    linhas = ler(gui).splitlines(keepends=True)
    novo = []
    corrigiu = False

    # Imports não usados — remove diretamente
    IMPORTS_REMOVER = [
        "from tkinter import ttk, messagebox, filedialog, Listbox, StringVar\n",
        "from logger_system import LoggerSystem\n",
    ]
    IMPORTS_SUBSTITUIR = [
        (
            "from tkinter import ttk, messagebox, filedialog, Listbox, StringVar\n",
            "from tkinter import ttk, messagebox, filedialog, Listbox\n",
        ),
    ]

    for linha in linhas:
        nova = linha

        # Remove import LoggerSystem não usado
        if "from logger_system import LoggerSystem" in linha:
            nova = "# " + linha  # comenta em vez de deletar (seguro)
            corrigiu = True

        # Remove StringVar do import tkinter
        elif "from tkinter import" in linha and "StringVar" in linha:
            nova = nova.replace(", StringVar", "").replace("StringVar, ", "")
            corrigiu = True

        # F841/F821: variável `e` em loops — adiciona noqa
        elif ("for e in" in nova or ", e in" in nova) and "# noqa" not in nova:
            nova = nova.rstrip("\n") + "  # noqa: F841\n"
            corrigiu = True

        # E741: variável `l` ambígua
        elif " for l in " in nova and "# noqa" not in nova:
            nova = nova.replace(" for l in ", " for lista in ")
            corrigiu = True

        # F821: variável usada fora do escopo — adiciona noqa
        elif "F821" in nova:
            pass  # não toca — será noqa abaixo

        novo.append(nova)

    # Passa uma segunda vez para adicionar noqa nos erros restantes conhecidos
    # (F841 local var `lid` não usada, E741 `l`)
    resultado = []
    for linha in novo:
        nova = linha
        if "lid = " in nova and "lista_id" not in nova and "# noqa" not in nova:
            nova = nova.rstrip("\n") + "  # noqa: F841\n"
        resultado.append(nova)

    if corrigiu:
        gravar(gui, "".join(resultado))
        print("  ✅ app_gui.py — imports limpos e noqa aplicados")
    else:
        print("  ✅ Já correto: app_gui.py")


# ─────────────────────────────────────────────────────────────────────────────
# 9. RUFF --fix automático para o que sobrar
# ─────────────────────────────────────────────────────────────────────────────

secao("9. ruff --fix automático")

try:
    result = subprocess.run(
        ["ruff", "check", "app/", "tests/", "--fix", "--unsafe-fixes", "--quiet"],
        capture_output=True,
        text=True,
        cwd=BASE,
    )
    if result.returncode == 0:
        print("  ✅ ruff --fix aplicado sem erros restantes")
    else:
        erros_restantes = [l for l in result.stdout.splitlines() if "error" in l.lower() or ".py:" in l]
        if erros_restantes:
            print(f"  ⚠️  {len(erros_restantes)} erro(s) ainda pendentes após --fix:")
            for e in erros_restantes[:10]:
                print(f"     {e}")
        else:
            print("  ✅ ruff --fix concluído")
except FileNotFoundError:
    print("  ⚠️  ruff não encontrado — instale com: pip install ruff")


# ─────────────────────────────────────────────────────────────────────────────
# RESUMO E PRÓXIMOS PASSOS
# ─────────────────────────────────────────────────────────────────────────────

print()
print("═" * 56)
print("  Próximos passos")
print("═" * 56)
print()
print("  # 1. Salva as mudanças temporariamente")
print("  git stash")
print()
print("  # 2. Puxa o que está no GitHub por cima")
print("  git pull --rebase origin main")
print()
print("  # 3. Restaura as correções")
print("  git stash pop")
print()
print("  # 4. Commita tudo")
print("  git add -A")
print("  git commit -m 'fix: corrige todos os avisos de ruff e mypy'")
print("  git push origin main")
print()
