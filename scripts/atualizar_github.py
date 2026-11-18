#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envia para o GitHub as alterações do repositório (datapackage.json de cada ano, README,
schemas, scripts), SEM arquivos de dados (.csv, .gz, .zip, .txt da pasta data).

Uso (na raiz do repositório):
  python scripts/atualizar_github.py
  python scripts/atualizar_github.py -m "mensagem do commit"
"""
import argparse
import subprocess
import sys
from datetime import date

PROIBIDOS = (".csv", ".gz", ".zip", ".xls", ".xlsx", ".parcial")


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"ERRO no git {' '.join(args)}:\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--mensagem", default=f"Atualiza publicação de GPS em {date.today():%d/%m/%Y}")
    args = ap.parse_args()

    git("add", "-A")
    preparados = [f for f in git("diff", "--cached", "--name-only").splitlines() if f]
    perigosos = [f for f in preparados
                 if f.lower().endswith(PROIBIDOS)
                 or ("/data/" in f.replace("\\", "/") and not f.endswith(".gitkeep"))]
    if perigosos:
        git("reset")
        sys.exit("ERRO: arquivos de dados iam para o GitHub e o envio foi cancelado:\n  "
                 + "\n  ".join(perigosos) + "\nConfira o .gitignore.")
    if not preparados:
        print("Nada a enviar: o GitHub já está atualizado.")
        return
    print("Arquivos enviados:\n  " + "\n  ".join(preparados))
    git("commit", "-m", args.mensagem)
    git("pull", "--rebase")
    git("push")
    print("GitHub atualizado.")


if __name__ == "__main__":
    main()
