"""Configuração compartilhada dos testes."""

import sys
from pathlib import Path

# scripts/ não é um pacote instalável; os testes importam os módulos direto.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
