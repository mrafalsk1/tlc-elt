import os
import sys

REQUIRED = [
    l.split("=")[0].strip()
    for l in open(".env.example")
    if l.strip() and not l.startswith("#")
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
