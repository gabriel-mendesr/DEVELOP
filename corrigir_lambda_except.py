"""
corrigir_lambda_except.py — Corrige captura de variável de exceção em lambdas
══════════════════════════════════════════════════════════════════════════════

PROBLEMA (bug real, não só estilo):
  Em Python 3, a variável do except (e) é APAGADA quando o bloco termina.
  Um lambda que referencia `e` vai encontrar NameError quando executar.

  except Exception as e:
      self.after(0, lambda: messagebox.showerror("Erro", str(e)))
                                                              ^ e não existe mais aqui!

CORREÇÃO:
  Capturar `e` no parâmetro default do lambda — o valor é copiado na hora:

  except Exception as e:
      self.after(0, lambda err=e: messagebox.showerror("Erro", str(err)))
                         ^^^^^ copia o valor agora        ^^^ usa a cópia

COMO RODAR:
  cd /home/gabrielmendes/develop
  python corrigir_lambda_except.py
"""

import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
GUI = os.path.join(BASE, "app", "app_gui.py")


def corrigir_lambda_except(caminho: str) -> int:
    """
    Encontra todos os lambdas que capturam `e` de um except e corrige.
    Retorna o número de correções feitas.
    """
    with open(caminho, encoding="utf-8") as f:
        conteudo = f.read()

    # Estratégia: procura lambdas que usam `e` (de um except) sem parâmetros
    # e os reescreve para capturar `e` via parâmetro default.
    #
    # Padrões encontrados no arquivo:
    #   lambda: messagebox.showerror("Erro", str(e))
    #   lambda: messagebox.showerror("Erro", f"...\n{e}")
    #   lambda: self.configure(cursor="arrow")  ← este NÃO tem `e`, ignorar
    #
    # Regex:
    #   lambda\s*:          → lambda sem parâmetros
    #   ([^)]*)\be\b         → corpo que contém `e` como palavra
    #   (?=\))              → seguido de fechamento de parêntese

    # Passo 1: troca `lambda: ...str(e)...` por `lambda err=e: ...str(err)...`
    substituicoes = [
        # str(e) — o mais comum
        (
            r"lambda\s*:\s*(.*?str\()e\)",
            r"lambda err=e: \1err)",
        ),
        # f"...\n{e}" ou f"...{e}..."
        (
            r"lambda\s*:\s*(.*?\{)e(\})",
            r"lambda err=e: \1err\2",
        ),
        # Caso genérico: lambda: ... e ... onde e aparece sozinho no final
        # (cobertura extra para variantes não capturadas acima)
        (
            r"lambda\s*:\s*(.*[^a-zA-Z_])e([^a-zA-Z_0-9])",
            r"lambda err=e: \1err\2",
        ),
    ]

    atual = conteudo
    total = 0

    for padrao, substituicao in substituicoes:
        novo, n = re.subn(padrao, substituicao, atual)
        if n > 0:
            atual = novo
            total += n

    if total == 0:
        print(f"  ✅ Já correto: {os.path.relpath(caminho)}")
        return 0

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(atual)

    print(f"  ✅ {os.path.relpath(caminho)} — {total} lambda(s) corrigido(s)")
    return total


def verificar_com_ruff(caminho: str) -> list[str]:
    """Roda ruff no arquivo e retorna os erros F821/F841 restantes."""
    import subprocess

    result = subprocess.run(
        ["ruff", "check", caminho, "--select", "F821,F841", "--quiet"], capture_output=True, text=True, cwd=BASE
    )
    return [l for l in result.stdout.splitlines() if ".py:" in l]


def main():
    print()
    print("═" * 58)
    print("  Corrige lambdas que capturam variável de except")
    print("═" * 58)
    print()

    if not os.path.isfile(GUI):
        print(f"  ❌ Não encontrado: {GUI}")
        return

    n = corrigir_lambda_except(GUI)
    print()

    if n > 0:
        # Verifica se ainda há erros F821/F841 relacionados
        pendentes = verificar_com_ruff(GUI)
        if pendentes:
            print(f"  ⚠️  {len(pendentes)} erro(s) F821/F841 ainda pendentes:")
            for linha in pendentes[:8]:
                print(f"     {linha}")
            print()
            print("  Esses podem ser outros padrões não cobertos.")
            print("  Adicione  # noqa: F821,F841  no fim das linhas acima")
            print("  se forem falsos positivos.")
        else:
            print("  ✅ Nenhum erro F821/F841 restante em app_gui.py")

    print()
    print("─" * 58)
    print("  Próximos passos:")
    print()
    print("  git stash")
    print("  git pull --rebase origin main")
    print("  git stash pop")
    print("  git add -A")
    print("  git commit -m 'fix: corrige lambdas com variável de except'")
    print("  git push origin main")
    print("─" * 58)
    print()


if __name__ == "__main__":
    main()
