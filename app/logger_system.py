"""
Sistema de Logging do Sistema Hotel Santos
Exporta logs, erros e especificações do sistema
"""

import logging  # noqa: I001
import json
import platform
import os
from pathlib import Path
from datetime import datetime


class LoggerSystem:
    """Gerencia logs e diagnósticos do sistema"""

    # noqa: W293
    def __init__(self, app_path=None):
        self.app_path = app_path or Path.home()
        self.log_dir = self.app_path / ".hotel_santos_logs"
        self.log_dir.mkdir(exist_ok=True)
        # noqa: W293
        self._setup_logging()

    # noqa: W293
    def _setup_logging(self):
        """Configura logging"""
        log_file = self.log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        # noqa: W293
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        # noqa: W293
        self.logger = logging.getLogger(__name__)
        self.logger.info("✅ Sistema de logging iniciado")

    # noqa: W293
    def exportar_diagnostico(self):
        """Exporta diagnóstico completo do sistema"""
        diag = {
            "timestamp": datetime.now().isoformat(),
            "sistema": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "machine": platform.machine(),
                "node": platform.node(),
            },
            "diretórios": {
                "home": str(Path.home()),
                "logs": str(self.log_dir),
                "app": str(self.app_path),
            },
            "variáveis_ambiente": dict(os.environ),
        }
        # noqa: W293
        # Salvar em JSON
        diag_file = self.log_dir / f"diagnostico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(diag_file, "w") as f:
            json.dump(diag, f, indent=2, default=str)
        # noqa: W293
        self.logger.info(f"📋 Diagnóstico exportado: {diag_file}")
        return diag_file

    # noqa: W293
    def log_erro(self, erro: Exception, contexto: str = ""):
        """Log de erro com contexto"""
        self.logger.error(f"❌ ERRO {contexto}: {str(erro)}", exc_info=True)

    # noqa: W293
    def log_info(self, mensagem: str):
        """Log de informação"""
        self.logger.info(f"ℹ️  {mensagem}")

    # noqa: W293
    def log_warning(self, mensagem: str):
        """Log de aviso"""
        self.logger.warning(f"⚠️  {mensagem}")
