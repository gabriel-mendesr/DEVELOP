#!/usr/bin/env python3
"""
Gerenciador de Releases - Sistema Hotel Santos
Cria tags e dispara builds automaticamente no GitHub
"""

import subprocess
import sys
import re
from pathlib import Path
from typing import Tuple, Optional

class ReleaseManager:
    """Gerencia criação de releases no GitHub"""
    
    REPO = "gabriel-mendesr/develop"
    APP_DIR = Path("/home/gabrielmendes/develop/HotelSantos")
    
    def __init__(self):
        self.versao_atual = self._obter_versao_atual()
    
    @staticmethod
    def validar_versao(versao: str) -> Tuple[bool, str]:
        """Valida formato semver (X.Y.Z)"""
        padrao = r'^(\d+)\.(\d+)\.(\d+)$'
        if re.match(padrao, versao):
            return True, versao
        return False, f"Versão inválida: {versao}. Use formato X.Y.Z (ex: 1.0.0)"
    
    def _obter_versao_atual(self) -> Optional[str]:
        """Obtém última versão do Git"""
        try:
            resultado = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(self.APP_DIR),
                capture_output=True,
                text=True
            )
            if resultado.returncode == 0:
                return resultado.stdout.strip().lstrip('v')
        except:
            pass
        return None
    
    def incrementar_versao(self, tipo: str = "patch") -> str:
        """
        Incrementa versão
        tipo: 'patch' (1.0.0 → 1.0.1), 'minor' (→ 1.1.0), 'major' (→ 2.0.0)
        """
        versao = self.versao_atual or "0.0.0"
        parts = [int(x) for x in versao.split('.')]
        
        if tipo == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif tipo == "minor":
            parts[1] += 1
            parts[2] = 0
        else:  # patch
            parts[2] += 1
        
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    
    def criar_tag(self, versao: str, mensagem: str = "") -> bool:
        """Cria tag e faz push para GitHub"""
        tag_name = f"v{versao}"
        mensagem = mensagem or f"Release {versao}"
        
        print(f"\n📌 Criando tag {tag_name}...")
        
        try:
            # Criar tag localmente
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", mensagem],
                cwd=str(self.APP_DIR),
                check=True,
                capture_output=True
            )
            print(f"✅ Tag criada: {tag_name}")
            
            # Push da tag
            print(f"📤 Fazendo push da tag...")
            subprocess.run(
                ["git", "push", "origin", tag_name],
                cwd=str(self.APP_DIR),
                check=True,
                capture_output=True
            )
            print(f"✅ Tag enviada para GitHub")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def menu_interativo(self):
        """Menu para criar release"""
        print("""
╔════════════════════════════════════════════════════════════════╗
║        Gerenciador de Releases - Sistema Hotel Santos        ║
╚════════════════════════════════════════════════════════════════╝
        """)
        
        if self.versao_atual:
            print(f"📦 Versão atual: {self.versao_atual}")
        else:
            print(f"📦 Nenhuma versão anterior encontrada")
        
        print("\n📋 Opções:")
        print("1. Criar versão PATCH (bug fix)       → 1.0.0 → 1.0.1")
        print("2. Criar versão MINOR (nova feature)  → 1.0.0 → 1.1.0")
        print("3. Criar versão MAJOR (mudança grande)→ 1.0.0 → 2.0.0")
        print("4. Criar versão MANUAL")
        print("5. Ver versão atual")
        print("6. Sair")
        
        opcao = input("\nEscolha (1-6): ").strip()
        
        if opcao == "1":
            versao = self.incrementar_versao("patch")
            self._criar_release(versao, "PATCH")
        elif opcao == "2":
            versao = self.incrementar_versao("minor")
            self._criar_release(versao, "MINOR")
        elif opcao == "3":
            versao = self.incrementar_versao("major")
            self._criar_release(versao, "MAJOR")
        elif opcao == "4":
            versao = input("Digite versão (X.Y.Z): ").strip()
            self._criar_release(versao)
        elif opcao == "5":
            print(f"Versão atual: {self.versao_atual or 'Nenhuma'}")
        elif opcao == "6":
            print("Até logo!")
            return
        else:
            print("❌ Opção inválida")
            return
    
    def _criar_release(self, versao: str, tipo: str = ""):
        """Processa criação de release"""
        # Validar versão
        valido, msg = self.validar_versao(versao)
        if not valido:
            print(f"❌ {msg}")
            return
        
        # Confirmar
        tipo_str = f" ({tipo})" if tipo else ""
        print(f"\n📝 Criando release v{versao}{tipo_str}")
        
        # Obter notas
        print("\n📝 Digite notas de release (deixe em branco para padrão):")
        notas = input("> ").strip()
        if not notas:
            notas = f"Release {versao}"
        
        # Confirmar antes de criar
        print(f"""
╔════════════════════════════════════════════════════════════════╗
║                      CONFIRMAR RELEASE                        ║
╠════════════════════════════════════════════════════════════════╣
║ Versão: v{versao}
║ Notas:  {notas[:50]}...
║
║ Isso vai:
║ 1. Criar tag v{versao} localmente
║ 2. Fazer push para GitHub
║ 3. Disparar GitHub Actions para build
║ 4. Gerar executáveis (Windows + Linux)
║ 5. Criar release com downloads
║
║ Tem certeza? (s/n)
╚════════════════════════════════════════════════════════════════╝
        """)
        
        confirmar = input("Continuar? (s/n): ").strip().lower()
        if confirmar != 's':
            print("❌ Cancelado")
            return
        
        # Criar tag
        if self.criar_tag(versao, notas):
            print(f"""
╔════════════════════════════════════════════════════════════════╗
║                     ✅ RELEASE CRIADA!                        ║
╚════════════════════════════════════════════════════════════════╝

Tag v{versao} foi criada e enviada para GitHub!

⏳ GitHub Actions está compilando...
   - Windows: SistemaHotelSantos-Windows.exe
   - Linux:   SistemaHotelSantos-Ubuntu

📊 Acompanhe em:
   https://github.com/gabriel-mendesr/develop/actions

⏱️  Tempo esperado: 5-10 minutos

🔄 Quando terminar:
   - Release será publicada em: Releases
   - App detectará atualização automaticamente
   - Usuários poderão atualizar no app

💡 Próximas vezes, basta:
   python3 release_manager.py

            """)
        else:
            print("❌ Erro ao criar release")


def main():
    """Função principal"""
    if len(sys.argv) > 1:
        # Modo linha de comando
        if sys.argv[1] == "--version":
            manager = ReleaseManager()
            print(f"Versão atual: {manager.versao_atual or 'Nenhuma'}")
        elif sys.argv[1] == "--create":
            if len(sys.argv) < 3:
                print("Uso: release_manager.py --create X.Y.Z")
                sys.exit(1)
            versao = sys.argv[2]
            manager = ReleaseManager()
            manager._criar_release(versao)
        else:
            print("Uso: release_manager.py [--version|--create X.Y.Z]")
    else:
        # Menu interativo
        manager = ReleaseManager()
        while True:
            try:
                manager.menu_interativo()
            except KeyboardInterrupt:
                print("\n\nCancelado")
                break
            except Exception as e:
                print(f"❌ Erro: {e}")


if __name__ == "__main__":
    main()
