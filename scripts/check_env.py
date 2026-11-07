#!/usr/bin/env python3
"""Valida se as variáveis exigidas por .env.example estão definidas.

Fora do CI, a ausência apenas avisa; com CI=true, é erro fatal.
"""

import os
import sys

with open(".env.example") as f:
    REQUIRED = [
        line.split("=")[0].strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

missing = [v for v in REQUIRED if not os.getenv(v)]

if missing:
    print(f"Aviso local, variáveis ausentes: {missing}")
else:
    print("Variáveis de ambiente verificadas")

# No CI, variáveis ausentes são erro fatal.
if missing and os.getenv("CI") == "true":
    print(f"Variáveis obrigatórias ausentes no CI: {missing}")
    sys.exit(1)

print("check_env.py: OK")
