"""
Módulo de Auto-Atualização — Sistema Hotel Santos

MUDANÇAS EM RELAÇÃO À VERSÃO ANTERIOR:
---------------------------------------
ANTES: A versão era buscada na API do GitHub no __init__().
       Se a internet estivesse lenta, o app demorava pra abrir.

AGORA: A versão vem do arquivo __version__.py (local, instantâneo).
       A verificação de updates roda em BACKGROUND, sem travar.

FLUXO:
  1. App abre → lê versão de __version__.py (instantâneo)
  2. App mostra a interface (já funcional!)
  3. Em background, verifica se há versão nova no GitHub
  4. Se houver, mostra botão "Atualizar" na sidebar
"""

import os  # noqa: I001
import platform
import subprocess
import sys
import threading
from collections.abc import Callable


class UpdateManager:
    """Gerencia verificação e aplicação de atualizações."""

    # CONFIGURAÇÃO — Repositório do GitHub
    # Altere aqui se mudar o repositório
    GITHUB_REPO = "gabriel-mendesr/DEVELOP"
    GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    def __init__(self):
        """
        Inicializa o gerenciador de updates.

        NOTA: NÃO faz requisição HTTP aqui! A versão vem do arquivo local.
        A verificação de updates é feita depois, em background.
        """
        # Versão LOCAL (sem internet — instantânea!)
        try:
            from __version__ import __version__ as VERSION
        except ImportError:
            from app.__version__ import __version__ as VERSION
        self.versao_atual = VERSION

    def comparar_versoes(self, v1: str, v2: str) -> int:
        """
        Compara duas versões no formato "X.Y.Z".

        Retorna:
          -1 se v1 < v2  (v1 é mais antiga)
           0 se v1 == v2  (mesma versão)
           1 se v1 > v2  (v1 é mais nova)

        Exemplos:
          comparar_versoes("1.0.0", "1.1.0") → -1
          comparar_versoes("2.0.0", "1.9.9") → 1
          comparar_versoes("1.0.0", "1.0.0") → 0
        """
        try:
            v1_parts = [int(x) for x in v1.split(".")]
            v2_parts = [int(x) for x in v2.split(".")]

            # Padroniza tamanho (ex: "1.0" → "1.0.0")
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)

            if v1_parts < v2_parts:
                return -1
            elif v1_parts > v2_parts:
                return 1
            return 0
        except (ValueError, AttributeError):
            return 0

    def verificar_atualizacao(self) -> tuple[bool, str | None, str | None]:
        """
        Verifica se há nova versão disponível no GitHub.

        ESTA FUNÇÃO FAZ REQUISIÇÃO HTTP — deve ser chamada em background!

        Retorna:
            (tem_atualizacao, versao_nova, url_download)
            Ex: (True, "1.2.0", "https://github.com/.../SistemaHotelSantos-Setup-Windows.exe")
            Ou: (False, None, None)
        """
        try:
            import requests  # noqa: PLC0415

            print(f"🔍 Verificando atualizações... (versão atual: {self.versao_atual})")
            response = requests.get(self.GITHUB_API, timeout=10)
            response.raise_for_status()

            data = response.json()
            versao_nova = data["tag_name"].lstrip("v")

            print(f"   Versão remota: {versao_nova}")

            if self.comparar_versoes(self.versao_atual, versao_nova) < 0:
                # Há versão mais nova!
                print(f"✅ Nova versão disponível: {versao_nova}")

                # Procura o arquivo de download correto para o OS
                assets = data.get("assets", [])
                os_identifier = "Windows" if platform.system() == "Windows" else "Ubuntu"

                for asset in assets:
                    if os_identifier in asset["name"]:
                        url = asset["browser_download_url"]
                        print(f"📥 Download: {url}")
                        return True, versao_nova, url

                print(f"⚠️ Nova versão sem build para {os_identifier}")
                return False, None, None
            else:
                print("✅ Você está na versão mais recente.")
                return False, None, None

        except requests.exceptions.Timeout:
            raise ConnectionError("Tempo esgotado ao verificar atualizações.")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Erro de rede: {e}")
        except Exception as e:
            raise RuntimeError(f"Não foi possível verificar atualizações: {e}")

    def verificar_em_background(self, callback: Callable) -> None:
        """
        Verifica atualizações em background (sem travar a interface).

        Args:
            callback: Função chamada com o resultado.
                      Recebe: (tem_update, versao_nova, url_download)

        Uso no app_gui.py:
            def quando_verificar(tem_update, versao, url):
                if tem_update:
                    self.btn_update.configure(text=f"⬇️ v{versao}")
                    self.btn_update.pack(...)

            self.update_manager.verificar_em_background(quando_verificar)
        """

        def _tarefa():
            try:
                resultado = self.verificar_atualizacao()
                callback(*resultado)
            except Exception as e:
                print(f"⚠️ Verificação de update falhou: {e}")
                callback(False, None, None)

        thread = threading.Thread(target=_tarefa, daemon=True)
        thread.start()

    def aplicar_atualizacao(
        self, url_download: str, versao_nova: str, progress_callback: Callable | None = None
    ) -> None:
        """
        Baixa e aplica a atualização.

        O processo:
        1. Baixa o novo executável para um arquivo temporário
        2. Cria um script (bat/sh) que:
           a. Espera o app atual fechar
           b. Substitui o executável antigo pelo novo
           c. Reabre o app
        3. Fecha o app atual

        Args:
            url_download: URL do novo executável
            versao_nova: String da versão nova (ex: "1.2.0")
            progress_callback: Função(progresso, status) chamada durante download
        """

        def _task():
            try:
                import requests  # noqa: PLC0415

                is_windows = platform.system() == "Windows"
                exec_path = os.path.abspath(sys.executable)
                exec_dir = os.path.dirname(exec_path)
                exec_name = os.path.basename(exec_path)

                temp_suffix = ".exe" if is_windows else ""
                temp_path = os.path.join(exec_dir, f"update_temp{temp_suffix}")

                # 1. Baixar
                r = requests.get(url_download, stream=True, timeout=30)
                r.raise_for_status()

                total_size = int(r.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded / total_size, None)

                # 2. Criar script de atualização
                if is_windows:
                    updater_path = os.path.join(exec_dir, "updater.bat")
                    script = f"""@echo off
echo Atualizando o sistema... Por favor, aguarde.
timeout /t 3 /nobreak > NUL
:retry
del "{exec_path}"
if exist "{exec_path}" (
    echo Arquivo ainda em uso, tentando novamente...
    timeout /t 2 /nobreak > NUL
    goto retry
)
ren "{temp_path}" "{exec_name}"
start "" "{exec_path}"
del "{updater_path}"
"""
                    with open(updater_path, "w", encoding="utf-8") as f:
                        f.write(script)

                    if progress_callback:
                        progress_callback(1.0, "finalizando")

                    subprocess.Popen(updater_path, shell=True, cwd=exec_dir, creationflags=subprocess.DETACHED_PROCESS)
                else:
                    updater_path = os.path.join(exec_dir, "updater.sh")
                    os.chmod(temp_path, 0o755)
                    script = f"""#!/bin/bash
echo "Atualizando..."
sleep 3
rm -f "{exec_path}"
mv "{temp_path}" "{exec_path}"
nohup "{exec_path}" >/dev/null 2>&1 &
rm -- "$0"
"""
                    with open(updater_path, "w") as f:
                        f.write(script)
                    os.chmod(updater_path, 0o755)

                    if progress_callback:
                        progress_callback(1.0, "finalizando")

                    subprocess.Popen(["/bin/bash", updater_path], cwd=exec_dir, start_new_session=True)

                # 3. Fechar o app
                os._exit(0)

            except Exception as e:
                if "temp_path" in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
                raise RuntimeError(f"Falha ao atualizar: {e}")

        threading.Thread(target=_task, daemon=True).start()
