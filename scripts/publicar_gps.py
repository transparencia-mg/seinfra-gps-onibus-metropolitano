#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica no dados.mg os arquivos diários de GPS dos ônibus metropolitanos.

Organização no portal: UM CONJUNTO POR ANO (gps-onibus-metropolitano-AAAA), com
um recurso por dia e um recurso lista-de-arquivos-AAAA.txt com o link de todos os dias.
Os arquivos vão DIRETO do seu computador para o portal (dpckan); não passam pelo GitHub.

  1. Conferência prévia: confere tamanho (limite do portal), colunas e o que já existe
     no portal. Se algo estiver errado, PARA antes de publicar qualquer coisa.
  2. Para cada dia:
       - se o dia já existe no portal e o arquivo mudou: substitui (mesmo ID, links não mudam)
       - se o dia já existe e o arquivo é igual: pula
       - se não existe: cria o recurso e grava o ID no datapackage.json
     Se o conjunto do ano ainda não existe no portal, ele é criado.
  3. Atualiza a lista-de-arquivos-AAAA.txt no portal.

Uso (raiz do repositório, venv ativado):
  python scripts/publicar_gps.py --ano 2026                          # simulação: só confere
  python scripts/publicar_gps.py --ano 2026 --executar               # todos os dias de 2026/data
  python scripts/publicar_gps.py --ano 2026 --so 2026-09-19 --executar   # um dia só
  python scripts/publicar_gps.py --ano 2026 --mes 2026-09 --executar     # um mês
  python scripts/publicar_gps.py --ano 2026 --forcar --executar      # reenvia mesmo sem mudança
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# ------------------------------------------------------------------ configuração
ORGANIZACAO = "PREENCHER"   # 'name' da organização no dados.mg (ex.: controladoria-geral-do-estado-cge)
PREFIXO = "gps-onibus-metropolitano"
LIMITE_MB = 300             # tamanho máximo de upload aceito hoje pelo dados.mg
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
RAIZ = Path(__file__).resolve().parent.parent
PADRAO = re.compile(rf"{PREFIXO}-(\d{{4}}-\d{{2}}-\d{{2}})\.csv\.gz$")


def carregar_env(arquivo=RAIZ / ".env"):
    if Path(arquivo).exists():
        for linha in Path(arquivo).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


carregar_env()
HOST = (os.environ.get("CKAN_HOST") or "https://dados.mg.gov.br").rstrip("/")
KEY = os.environ.get("CKAN_KEY")


# ------------------------------------------------------------------ utilidades
def api_get(acao):
    """Devolve o 'result' da API do CKAN, ou None se o conjunto não existir (404)."""
    req = urllib.request.Request(f"{HOST}/api/3/action/{acao}")
    if KEY:
        req.add_header("Authorization", KEY)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)["result"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return "sha256:" + h.hexdigest()


def cabecalho_gz(caminho):
    with gzip.open(caminho, "rt", encoding="utf-8-sig") as f:
        return f.readline().rstrip("\r\n").split(";")


def nome_arquivo(url):
    return (url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]


def nome_conjunto(ano):
    return f"{PREFIXO}-{ano}"


def pasta_do_ano(ano):
    return RAIZ / str(ano)


def caminho_dp(ano):
    return pasta_do_ano(ano) / "datapackage.json"


def ler_dp(ano):
    return json.loads(caminho_dp(ano).read_text(encoding="utf-8"))


def gravar_dp(ano, dp):
    dp["resources"].sort(key=lambda r: r["name"])
    caminho_dp(ano).write_text(json.dumps(dp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preparar_pasta_do_ano(ano):
    """Cria AAAA/datapackage.json, README.md, schema.json e dialect.json se ainda não existirem."""
    pasta = pasta_do_ano(ano)
    (pasta / "data").mkdir(parents=True, exist_ok=True)
    for f in ("schema.json", "dialect.json"):
        shutil.copyfile(RAIZ / f, pasta / f)          # sempre a versão atual da raiz
    readme = pasta / "README.md"
    if not readme.exists():
        readme.write_text((RAIZ / "modelo" / "README.md").read_text(encoding="utf-8")
                          .replace("{ANO}", str(ano)), encoding="utf-8")
    if not caminho_dp(ano).exists():
        gravar_dp(ano, {
            "profile": "data-package",
            "name": nome_conjunto(ano),
            "title": f"GPS dos ônibus metropolitanos da RMBH - {ano}",
            "description": f"Posições de GPS dos ônibus do transporte coletivo metropolitano da RMBH em {ano}.",
            "owner_org": ORGANIZACAO,
            "keywords": ["transporte", "ônibus", "GPS", "mobilidade", "RMBH"],
            "private": "false",
            "state": "active",
            "version": "0.1.0",
            "licenses": [{"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0",
                          "path": "https://creativecommons.org/licenses/by/4.0/"}],
            "resources": [],
        })
        print(f"Criado {caminho_dp(ano).relative_to(RAIZ)}")


def recurso_do_dia(dia, arquivo):
    d = date.fromisoformat(dia)
    return {
        "name": f"gps-{dia}",
        "path": f"data/{arquivo.name}",
        "title": f"GPS - {d:%d/%m/%Y} ({DIAS_SEMANA[d.weekday()]})",
        "description": f"Posições de GPS dos ônibus metropolitanos em {d:%d/%m/%Y}. CSV compactado (.gz), separador ';', UTF-8.",
        "profile": "tabular-data-resource",
        "format": "csv",
        "compression": "gz",
        "mediatype": "text/csv",
        "encoding": "utf-8",
        "schema": "schema.json",
        "dialect": "dialect.json",
    }


def recurso_lista(ano):
    return {
        "name": "lista-de-arquivos",
        "path": f"data/lista-de-arquivos-{ano}.txt",
        "title": f"Lista de arquivos de {ano} (para baixar o ano inteiro)",
        "description": "Link de todos os arquivos diários do ano, um por linha. Veja na descrição do conjunto como usar.",
        "profile": "data-resource",
        "format": "txt",
        "mediatype": "text/plain",
        "encoding": "utf-8",
    }


def dpckan(ano, *args):
    """Roda o dpckan com o datapackage do ano. Devolve True se deu certo."""
    env = dict(os.environ, CKAN_HOST=HOST, CKAN_KEY=KEY or "")
    cmd = ["dpckan", "--datapackage", str(caminho_dp(ano).relative_to(RAIZ)), "--exit-code", *args]
    return subprocess.run(cmd, cwd=RAIZ, env=env).returncode == 0


def recursos_no_portal(ano):
    pacote = api_get(f"package_show?id={nome_conjunto(ano)}")
    if pacote is None or pacote.get("state") == "deleted":
        return None
    return {nome_arquivo(r.get("url")): r for r in pacote["resources"]}


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ano", required=True, type=int)
    ap.add_argument("--executar", action="store_true", help="publica de fato (sem isso só confere)")
    ap.add_argument("--so", metavar="AAAA-MM-DD", help="só este dia")
    ap.add_argument("--mes", metavar="AAAA-MM", help="só este mês")
    ap.add_argument("--forcar", action="store_true", help="reenvia mesmo os dias sem alteração")
    ap.add_argument("--pausa", type=int, default=3, help="segundos entre envios")
    args = ap.parse_args()
    ano = args.ano

    if ORGANIZACAO == "PREENCHER":
        sys.exit("ERRO: preencha ORGANIZACAO no início de scripts/publicar_gps.py "
                 "(nome da organização no dados.mg).")
    preparar_pasta_do_ano(ano)
    schema = json.loads((RAIZ / "schema.json").read_text(encoding="utf-8"))
    colunas = [f["name"] for f in schema["fields"]]

    arquivos = {}
    for f in sorted((pasta_do_ano(ano) / "data").glob("*.csv.gz")):
        m = PADRAO.fullmatch(f.name)
        if m and m.group(1).startswith(str(ano)):
            arquivos[m.group(1)] = f
    if args.so:
        arquivos = {d: f for d, f in arquivos.items() if d == args.so}
    elif args.mes:
        arquivos = {d: f for d, f in arquivos.items() if d.startswith(args.mes)}
    if not arquivos:
        sys.exit(f"ERRO: nenhum arquivo para publicar em {ano}/data "
                 "(rode antes scripts/preparar_gps.py).")

    # ---------- 1. conferência prévia ----------
    print(f"Portal: {HOST}   Conjunto: {nome_conjunto(ano)}")
    try:
        portal = recursos_no_portal(ano)
    except Exception as e:
        sys.exit(f"ERRO ao consultar o portal: {e}")
    if portal is None:
        print("O conjunto deste ano AINDA NÃO EXISTE no portal: será criado.")
        portal = {}

    dp = ler_dp(ano)
    no_dp = {r["name"]: r for r in dp["resources"]}
    problemas, plano = [], []
    for dia, arq in arquivos.items():
        mb = arq.stat().st_size / 1e6
        if mb > LIMITE_MB:
            problemas.append(f"{dia}: {mb:.0f} MB, acima do limite de {LIMITE_MB} MB do portal")
            continue
        if cabecalho_gz(arq) != colunas:
            problemas.append(f"{dia}: colunas diferentes do schema.json (prepare de novo com preparar_gps.py)")
            continue
        rec = no_dp.get(f"gps-{dia}")
        remoto = portal.get(arq.name)
        if remoto:
            hash_atual = sha256(arq)
            if rec and rec.get("hash") == hash_atual and not args.forcar:
                print(f"  {dia}: sem alteração, pulado")
                continue
            plano.append((dia, arq, remoto["id"], "update"))
            print(f"  {dia}: {arq.name} ({mb:.1f} MB) -> substituir (ID {remoto['id']})")
        else:
            plano.append((dia, arq, None, "create"))
            print(f"  {dia}: {arq.name} ({mb:.1f} MB) -> CRIAR")

    if problemas:
        print("\nPROBLEMAS - nada foi publicado. Corrija e rode de novo:")
        for p in problemas:
            print(f"  - {p}")
        sys.exit(1)
    total_mb = sum(a.stat().st_size for _, a, _, _ in plano) / 1e6
    print(f"\nConferência OK: {sum(p[3] == 'create' for p in plano)} para criar, "
          f"{sum(p[3] == 'update' for p in plano)} para substituir ({total_mb:,.0f} MB a enviar).")
    if not plano:
        print("Nada a publicar.")
        return
    if not args.executar:
        print("SIMULAÇÃO - nada foi feito. Rode de novo com --executar.")
        return
    if not KEY:
        sys.exit("ERRO: CKAN_KEY não encontrada no .env.")

    # ---------- 2. publicação ----------
    falhas = []
    if not portal:
        # conjunto novo: cria já com o primeiro dia (o dpckan exige ao menos um recurso)
        dia, arq, _, _ = plano.pop(0)
        dp = ler_dp(ano)
        dp["resources"] = [{**recurso_do_dia(dia, arq), "hash": sha256(arq)}]  # os demais voltam abaixo
        gravar_dp(ano, dp)
        print(f"\nCriando o conjunto {nome_conjunto(ano)} com {dia} ...")
        if not dpckan(ano, "dataset", "create"):
            sys.exit("ERRO ao criar o conjunto. Nada mais foi publicado.")
        time.sleep(args.pausa)

    for i, (dia, arq, rid, acao) in enumerate(plano, 1):
        nome = f"gps-{dia}"
        print(f"\n[{i}/{len(plano)}] {nome} ({acao})", flush=True)
        try:
            dp = ler_dp(ano)
            dp["resources"] = [r for r in dp["resources"] if r["name"] != nome]
            rec = {**recurso_do_dia(dia, arq), "hash": sha256(arq)}
            if rid:
                rec["id"] = rid
            dp["resources"].append(rec)
            gravar_dp(ano, dp)
            ok = dpckan(ano, "resource", nome, "update", rid) if acao == "update" \
                else dpckan(ano, "resource", nome, "create")
            if not ok:
                print("   ERRO no dpckan")
                falhas.append(dia)
                continue
            print("   OK")
            time.sleep(args.pausa)
        except Exception as e:
            print(f"   ERRO inesperado: {e} - os próximos dias continuam.")
            falhas.append(dia)

    # grava os IDs dos recursos como estão no portal
    portal = recursos_no_portal(ano) or {}
    dp = ler_dp(ano)
    for r in dp["resources"]:
        remoto = portal.get(Path(r["path"]).name)
        if remoto:
            r["id"] = remoto["id"]
    gravar_dp(ano, dp)

    # ---------- 3. lista de arquivos do ano ----------
    urls = sorted(r["url"] for n, r in portal.items() if PADRAO.fullmatch(n))
    lista = pasta_do_ano(ano) / "data" / f"lista-de-arquivos-{ano}.txt"
    lista.write_text("\n".join(urls) + "\n", encoding="utf-8")
    dp = ler_dp(ano)
    dp["resources"] = [r for r in dp["resources"] if r["name"] != "lista-de-arquivos"]
    rec = recurso_lista(ano)
    remoto = portal.get(lista.name)
    if remoto:
        rec["id"] = remoto["id"]
    dp["resources"].append(rec)
    gravar_dp(ano, dp)
    print(f"\nAtualizando {lista.name} ({len(urls)} dias) ...")
    ok = dpckan(ano, "resource", "lista-de-arquivos", "update", remoto["id"]) if remoto \
        else dpckan(ano, "resource", "lista-de-arquivos", "create")
    if not ok:
        print("   ERRO ao publicar a lista de arquivos (os dias foram publicados).")
    elif not remoto:
        novo = (recursos_no_portal(ano) or {}).get(lista.name)
        if novo:
            dp = ler_dp(ano)
            next(r for r in dp["resources"] if r["name"] == "lista-de-arquivos")["id"] = novo["id"]
            gravar_dp(ano, dp)

    print(f"\nConcluído. Falhas: {', '.join(falhas) or 'nenhuma'}")
    if falhas:
        print("Rode o mesmo comando de novo: os dias que já foram publicados serão pulados.")
    print("Próximo passo: python scripts/atualizar_github.py")


if __name__ == "__main__":
    main()
