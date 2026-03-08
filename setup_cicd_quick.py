from pathlib import Path

projeto_root = Path("/home/gabrielmendes/develop/HotelSantos")
github_workflows = projeto_root / ".github" / "workflows"
github_workflows.mkdir(parents=True, exist_ok=True)

workflow_content = """name: Build & Release - Hotel Santos

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            nome_saida: SistemaHotelSantos-Windows.exe
          - os: ubuntu-latest
            nome_saida: SistemaHotelSantos-Ubuntu

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install --upgrade pip && pip install pyinstaller && pip install -r app/requirements.txt
      - run: cd app && pyinstaller --name=SistemaHotelSantos --onefile --windowed --clean --noconfirm app_gui.py
      - if: runner.os == 'Windows'
        run: cd app\\dist && ren SistemaHotelSantos.exe SistemaHotelSantos-Windows.exe
      - if: runner.os == 'Linux'
        run: cd app/dist && mv SistemaHotelSantos SistemaHotelSantos-Ubuntu && chmod +x SistemaHotelSantos-Ubuntu
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.nome_saida }}
          path: app/dist/${{ matrix.nome_saida }}
          retention-days: 30

  release:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: release_artifacts
      - uses: softprops/action-gh-release@v2
        with:
          files: release_artifacts/**/SistemaHotelSantos*
"""

(github_workflows / "build-release.yml").write_text(workflow_content)
print("✅ Workflow criado com sucesso!")
print("✅ Caminho: .github/workflows/build-release.yml")
