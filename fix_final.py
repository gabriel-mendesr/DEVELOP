"""
fix_final.py — Corrige os erros restantes de ruff e mypy
══════════════════════════════════════════════════════════

ERROS RESTANTES:
  database.py:199   mypy — os.getenv str|None
  models.py:36      ruff — Optional não usado
  update_manager.py ruff — json, Path, datetime, Optional, Tuple não usados
  app_gui.py:1047   ruff — variável `l` ambígua/undefined
  app_gui.py:2204   ruff — variável `e` não usada
  verificar_sistema.py — `l` undefined em vários pontos

COMO RODAR:
  cd /home/gabrielmendes/develop
  python fix_final.py
"""

import os

BASE   = os.path.dirname(os.path.abspath(__file__))
CORE   = os.path.join(BASE, "app", "core")
APP    = os.path.join(BASE, "app")
TESTS  = os.path.join(BASE, "tests")


def patch(caminho: str, correcoes: list[tuple[str, str]]) -> None:
    rel = os.path.relpath(caminho, BASE)
    if not os.path.isfile(caminho):
        print(f"  ⏭️  não encontrado: {rel}")
        return

    with open(caminho, encoding="utf-8") as f:
        texto = f.read()

    original = texto
    for velho, novo in correcoes:
        if velho in texto:
            texto = texto.replace(velho, novo, 1)

    if texto == original:
        print(f"  ✅ já correto: {rel}")
    else:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"  ✅ corrigido:  {rel}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════════")
print("  fix_final.py")
print("══════════════════════════════════════════════════════\n")

# 1. database.py — mypy: os.getenv retorna str|None, os.path.join exige str
#    Adiciona anotação de tipo explícita: app_data: str = ...
patch(os.path.join(CORE, "database.py"), [
    (
        "            app_data = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser('~')\n",
        "            app_data: str = (os.environ.get('APPDATA') or os.path.expanduser('~')) if os.name == 'nt' else os.path.expanduser('~')\n",
    ),
])

# 2. models.py — remove Optional não usado, moderniza Dict/List/Tuple
patch(os.path.join(CORE, "models.py"), [
    (
        "from typing import Any, Dict, List, Optional, Tuple\n",
        "from typing import Any\n",
    ),
    # Caso o ruff já tenha parcialmente corrigido:
    (
        "from typing import Any, Optional\n",
        "from typing import Any\n",
    ),
    # Substitui usos remanescentes de Optional nos type hints
    ("Optional[Dict]",  "dict | None"),
    ("Optional[str]",   "str | None"),
    ("Optional[int]",   "int | None"),
    ("Optional[float]", "float | None"),
    # Substitui Dict, List, Tuple nos type hints pelo built-in moderno
    ("Dict[",  "dict["),
    ("List[",  "list["),
    ("Tuple[", "tuple["),
    # isinstance com tupla de tipos → X | Y
    ("isinstance(valor, (int, float))", "isinstance(valor, int | float)"),
])

# 3. update_manager.py — remove imports não usados
patch(os.path.join(APP, "update_manager.py"), [
    ("import json\n",                               ""),
    ("from pathlib import Path\n",                  ""),
    ("from datetime import datetime\n",             ""),
    (
        "from typing import Optional, Tuple, Callable\n",
        "from typing import Callable\n",
    ),
    (
        "from typing import Tuple, Optional, Callable\n",
        "from typing import Callable\n",
    ),
    # Atualiza as assinaturas de tipo que usavam Optional e Tuple
    (
        ") -> Tuple[bool, Optional[str], Optional[str]]:",
        ") -> tuple[bool, str | None, str | None]:",
    ),
    (
        "Optional[Callable]",
        "Callable | None",
    ),
])

# 4. app_gui.py — variável `l` ambígua (linha ~1045) e `e` não usada (linha ~2204)
patch(os.path.join(APP, "app_gui.py"), [
    # E741 / F821: loop com variável `l` — renomeia para `lista`
    (
        "        for l in listas:\n",
        "        for lista in listas:\n",
    ),
    (
        "            self.tree_listas.insert(\"\", \"end\", values=(l['id'], data_br, l['status'], f\"R$ {l['total_valor'] if l['total_valor'] else 0.0:.2f}\"))\n",
        "            self.tree_listas.insert(\"\", \"end\", values=(lista['id'], data_br, lista['status'], f\"R$ {lista['total_valor'] if lista['total_valor'] else 0.0:.2f}\"))\n",
    ),
    # Versão alternativa de formatação que o ruff pode ter gerado:
    (
        "            self.tree_listas.insert(\"\", \"end\", values=(l[\"id\"], data_br, l[\"status\"], f\"R$ {l['total_valor'] if l['total_valor'] else 0.0:.2f}\"))\n",
        "            self.tree_listas.insert(\"\", \"end\", values=(lista[\"id\"], data_br, lista[\"status\"], f\"R$ {lista['total_valor'] if lista['total_valor'] else 0.0:.2f}\"))\n",
    ),
    # F841: variável `e` atribuída mas não usada no bloco final do __main__
    (
        "    except Exception as e:\n        # --- TRATAMENTO GLOBAL",
        "    except Exception:\n        # --- TRATAMENTO GLOBAL",
    ),
    # Variante: se o bloco ficou numa linha só
    (
        "    except Exception as e:  # noqa",
        "    except Exception:  # noqa",
    ),
])

# 5. verificar_sistema.py — `l` undefined (o resolver_tudo renomeou o `for`
#    mas não renomeou os usos dentro do loop)
patch(os.path.join(TESTS, "verificar_sistema.py"), [
    # Padrão: for l in listas: → for lista in listas:
    ("for l in listas:\n",          "for lista in listas:\n"),
    ("for l in listas_resumo:\n",   "for lista in listas_resumo:\n"),
    # Usos de l dentro do loop
    ("            lid = l[",        "            lid = lista["),
    ("            lid = l.get(",    "            lid = lista.get("),
    ("        lid = l[",            "        lid = lista["),
    ("        lid = l.get(",        "        lid = lista.get("),
    ("            assert l[",       "            assert lista["),
    ("        assert l[",           "        assert lista["),
    # isinstance com tupla
    ("isinstance(v, (int, float))", "isinstance(v, int | float)"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Exclui os scripts de reparo do ruff (estão na raiz, não são código do projeto)
# ─────────────────────────────────────────────────────────────────────────────

pyproject = os.path.join(BASE, "pyproject.toml")
if os.path.isfile(pyproject):
    with open(pyproject, encoding="utf-8") as f:
        toml = f.read()

    # Adiciona os scripts de reparo ao exclude do ruff
    scripts_excluir = [
        "fix_final.py",
        "corrigir_lambda_except.py",
        "corrigir_tipos2.py",
        "corrigir_version.py",
        "resolver_tudo.py",
        "reparar_banco.py",
    ]

    exclude_linha_atual = 'exclude = [".git", "__pycache__", "dist", "build", "app/__version__.py"]'
    itens = '", "'.join(scripts_excluir)
    exclude_linha_nova = (
        f'exclude = [".git", "__pycache__", "dist", "build", '
        f'"app/__version__.py", "{itens}"]'
    )

    if exclude_linha_atual in toml and exclude_linha_nova not in toml:
        toml = toml.replace(exclude_linha_atual, exclude_linha_nova)
        with open(pyproject, "w", encoding="utf-8") as f:
            f.write(toml)
        print("  ✅ corrigido:  pyproject.toml — scripts de reparo excluídos do ruff")
    else:
        print("  ✅ já correto: pyproject.toml")

# ─────────────────────────────────────────────────────────────────────────────
print()
print("──────────────────────────────────────────────────────")
print("  Próximos passos:")
print()
print("  git add -A")
print("  git commit -m 'fix: corrige todos os erros ruff e mypy'")
print("  git push origin main")
print("──────────────────────────────────────────────────────\n")
