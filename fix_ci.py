"""
fix_ci.py — Corrige os 3 problemas que quebram o CI
═════════════════════════════════════════════════════

PROBLEMA 1 — models.py: __version__ não existe no CI
  O arquivo app/__version__.py é gerado pelo setuptools-scm e está
  no .gitignore. O CI clona o repo sem ele, então o import falha.
  CORREÇÃO: adiciona terceiro fallback com VERSION = "0.0.0"

PROBLEMA 2 — verificar_sistema.py: sys.exit() no nível do módulo
  O pytest importa o arquivo para coletar testes. O sys.exit()
  no final do arquivo roda na importação e trava o pytest com
  INTERNALERROR: SystemExit.
  CORREÇÃO: envolve o sys.exit() em `if __name__ == "__main__":`

PROBLEMA 3 — verificar_sistema.py: SCRIPT_DIR aponta para tests/
  O script foi escrito para rodar de dentro de app/, mas o CI
  o executa de tests/. Todos os caminhos de arquivo ficam errados.
  CORREÇÃO: detecta o diretório correto do app/ dinamicamente

COMO RODAR:
  cd /home/gabrielmendes/develop
  python fix_ci.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(BASE, "app", "core")
TESTS = os.path.join(BASE, "tests")
CI = os.path.join(BASE, ".github", "workflows", "ci.yml")


def ler(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def gravar(caminho: str, texto: str) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def patch_linha(caminho: str, velho: str, novo: str, descricao: str) -> bool:
    texto = ler(caminho)
    if velho not in texto:
        print(f"  ✅ Já correto: {descricao}")
        return False
    gravar(caminho, texto.replace(velho, novo, 1))
    print(f"  ✅ {descricao}")
    return True


print()
print("═" * 56)
print("  fix_ci.py — Corrige 3 problemas do CI")
print("═" * 56)


# ─────────────────────────────────────────────────────────────────────────────
# 1. models.py — triplo fallback para VERSION
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  [1] models.py — fallback VERSION = '0.0.0'")

models = os.path.join(CORE, "models.py")

# Cobre tanto "VERSION" quanto "__version__ as VERSION" (após corrigir_version.py)
for velho in [
    "        try:\n            from __version__ import VERSION\n        except ImportError:\n            from app.__version__ import VERSION\n        self.versao_atual = VERSION",
    "        try:\n            from __version__ import __version__ as VERSION\n        except ImportError:\n            from app.__version__ import __version__ as VERSION\n        self.versao_atual = VERSION",
]:
    novo = (
        "        try:\n"
        "            from __version__ import __version__ as VERSION\n"
        "        except ImportError:\n"
        "            try:\n"
        "                from app.__version__ import __version__ as VERSION\n"
        "            except ImportError:\n"
        '                VERSION = "0.0.0"  # fallback para CI sem setuptools-scm\n'
        "        self.versao_atual = VERSION"
    )
    if patch_linha(models, velho, novo, "models.py — triplo fallback VERSION"):
        break


# ─────────────────────────────────────────────────────────────────────────────
# 2. verificar_sistema.py — sys.exit() e SCRIPT_DIR
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  [2] verificar_sistema.py — sys.exit() e SCRIPT_DIR")

vs = os.path.join(TESTS, "verificar_sistema.py")
texto = ler(vs)

# 2a. Protege sys.exit() com __main__ guard
for velho_exit in [
    "\nsys.exit(0 if _falhou == 0 else 1)\n",
    "\nsys.exit(0 if _falhou == 0 else 1)",
]:
    if velho_exit in texto:
        texto = texto.replace(
            velho_exit,
            '\nif __name__ == "__main__":\n    sys.exit(0 if _falhou == 0 else 1)\n',
            1,
        )
        print("  ✅ verificar_sistema.py — sys.exit() protegido")
        break
else:
    if '__name__ == "__main__"' in texto:
        print("  ✅ Já correto: sys.exit() já protegido")
    else:
        print("  ⚠️  sys.exit() não encontrado — verifique manualmente")

# 2b. Corrige SCRIPT_DIR para encontrar app/ de qualquer diretório
velho_dir = "SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))"
novo_dir = (
    "SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))\n"
    "# Funciona tanto rodando de app/ quanto de tests/ (CI)\n"
    '_app_candidato = os.path.join(SCRIPT_DIR, "..", "app")\n'
    'if os.path.isdir(_app_candidato) and os.path.isdir(os.path.join(_app_candidato, "core")):\n'
    "    SCRIPT_DIR = os.path.normpath(_app_candidato)\n"
    'elif not os.path.isdir(os.path.join(SCRIPT_DIR, "core")):\n'
    "    # Tenta subir mais um nível\n"
    '    _app_candidato2 = os.path.join(SCRIPT_DIR, "..", "..", "app")\n'
    '    if os.path.isdir(os.path.join(_app_candidato2, "core")):\n'
    "        SCRIPT_DIR = os.path.normpath(_app_candidato2)"
)

if velho_dir in texto and "_app_candidato" not in texto:
    texto = texto.replace(velho_dir, novo_dir, 1)
    print("  ✅ verificar_sistema.py — SCRIPT_DIR corrigido")
else:
    print("  ✅ Já correto: SCRIPT_DIR")

gravar(vs, texto)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ci.yml — gerar __version__.py antes dos testes
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  [3] ci.yml — gerar __version__.py antes dos testes")

if not os.path.isfile(CI):
    print(f"  ⚠️  ci.yml não encontrado em: {CI}")
else:
    ci_texto = ler(CI)

    velho_install = (
        "      - name: Instalar dependências\n"
        "        run: |\n"
        "          pip install --upgrade pip\n"
        "          # Instala as dependências do projeto sem as de GUI (não disponíveis no CI)\n"
        "          pip install pytest pytest-cov"
    )
    novo_install = (
        "      - name: Instalar dependências\n"
        "        run: |\n"
        "          pip install --upgrade pip\n"
        "          # Instala as dependências do projeto sem as de GUI (não disponíveis no CI)\n"
        "          pip install pytest pytest-cov setuptools-scm\n"
        "          # Gera app/__version__.py que está no .gitignore mas é necessário\n"
        "          # para os imports em models.py funcionarem\n"
        '          python -c "\n'
        "          import subprocess, pathlib\n"
        "          try:\n"
        "              v = subprocess.check_output(['python', '-m', 'setuptools_scm'], text=True).strip()\n"
        "          except Exception:\n"
        "              v = '0.0.0'\n"
        "          pathlib.Path('app/__version__.py').write_text(f'__version__ = \\\"{v}\\\"\\n')\n"
        "          print(f'Gerado app/__version__.py com versão {v}')\n"
        '          "'
    )

    if velho_install in ci_texto:
        gravar(CI, ci_texto.replace(velho_install, novo_install, 1))
        print("  ✅ ci.yml — geração de __version__.py adicionada")
    elif "setuptools-scm" in ci_texto:
        print("  ✅ Já correto: ci.yml já tem setuptools-scm")
    else:
        # Abordagem alternativa: adiciona antes do step de rodar testes
        velho_run = "      - name: Rodar testes com cobertura"
        novo_gerar = (
            "      - name: Gerar app/__version__.py\n"
            "        run: |\n"
            "          pip install setuptools-scm\n"
            '          python -c "\n'
            "import subprocess, pathlib\n"
            "try:\n"
            "    v = subprocess.check_output(['python', '-m', 'setuptools_scm'], text=True).strip()\n"
            "except Exception:\n"
            "    v = '0.0.0'\n"
            "pathlib.Path('app/__version__.py').write_text(f'__version__ = \\\"{v}\\\"\\n')\n"
            "print(f'Versão: {v}')\n"
            '          "\n\n'
            "      - name: Rodar testes com cobertura"
        )
        if velho_run in ci_texto:
            gravar(CI, ci_texto.replace(velho_run, novo_gerar, 1))
            print("  ✅ ci.yml — step de geração adicionado antes dos testes")
        else:
            print("  ⚠️  ci.yml: não encontrou ponto de inserção — edite manualmente")
            print("      Adicione antes do step de testes:")
            print("        pip install setuptools-scm")
            print("        python -m setuptools_scm  # gera app/__version__.py")


# ─────────────────────────────────────────────────────────────────────────────
print()
print("─" * 56)
print("  git add -A")
print("  git commit -m 'fix: corrige CI - __version__, sys.exit e SCRIPT_DIR'")
print("  git push origin main")
print("─" * 56)
print()
