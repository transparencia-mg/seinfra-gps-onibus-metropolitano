#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepara os arquivos de GPS dos ônibus metropolitanos recebidos do órgão para publicação.

O que faz:
  1. Lê o arquivo recebido (.zip com o CSV dentro, ou o próprio .csv), em partes,
     sem carregar tudo na memória.
  2. Confere se as colunas são as esperadas.
  3. Corrige latitude/longitude estragadas pelo Excel
     (ex.: '-1.987.577' -> '-19.87577'; '-4.378.705' -> '-43.78705').
  4. Converte data_referencia e data_escala para AAAA-MM-DD.
  5. Separa um arquivo por dia (pela coluna data_referencia) e grava compactado em
        data/gps-onibus-metropolitano-AAAA-MM-DD.csv.gz
  6. Mostra um resumo e PARA se houver problema.

Uso (raiz do repositório, venv ativado):
  python scripts/preparar_gps.py "L:\\caminho\\arquivo.zip"        # um arquivo
  python scripts/preparar_gps.py "L:\\caminho\\pasta"              # todos os .zip/.csv da pasta
  python scripts/preparar_gps.py "arquivo.zip" --substituir         # refaz dias já preparados

Se a variável REDE_GPS estiver no .env, dá para informar só o nome do arquivo.
"""
import argparse
import csv
import gzip
import io
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd

COLUNAS = [
    "data_referencia", "cod_linha", "nome_atendimento", "consorcio", "posicao", "sentido",
    "prefixo_veiculo", "data_escala", "inicio_viagem_realizado", "fim_viagem_realizado",
    "data_hora_gps", "latitude", "longitude", "id_ponto", "entrada_ponto",
]
PREFIXO = "gps-onibus-metropolitano"
RAIZ = Path(__file__).resolve().parent.parent
PARTE = 500_000                       # linhas lidas por vez
LIMITE_PROBLEMAS = 0.01               # para se mais de 1% das linhas tiver problema
# Região Metropolitana de BH, com folga
FAIXA_LAT = (-21.0, -18.5)
FAIXA_LON = (-45.0, -43.0)


def carregar_env(arquivo=RAIZ / ".env"):
    if Path(arquivo).exists():
        for linha in Path(arquivo).read_text(encoding="utf-8-sig").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ------------------------------------------------------------------ correções
def corrigir_coordenada(serie):
    """Recupera a coordenada a partir dos dígitos.
    Na RMBH a latitude é sempre -19,x ou -20,x e a longitude -43,x ou -44,x:
    sempre 2 dígitos antes da vírgula. Funciona também se o valor já vier certo
    ('-19.875345' ou '-19,875345')."""
    digitos = serie.str.replace(r"[^0-9]", "", regex=True).str[:9]
    valor = "-" + digitos.str[:2] + "." + digitos.str[2:]
    numero = pd.to_numeric(valor.where(digitos.str.len() >= 3), errors="coerce").round(6)
    texto = numero.map(lambda x: "" if pd.isna(x) else f"{x:.6f}".rstrip("0").rstrip("."))
    return numero, texto


def data_iso(serie):
    """'19/09/2026' -> '2026-09-19' (aceita também valores já em AAAA-MM-DD)."""
    br = pd.to_datetime(serie, format="%d/%m/%Y", errors="coerce")
    iso = pd.to_datetime(serie, format="%Y-%m-%d", errors="coerce")
    d = br.fillna(iso)
    return d.dt.strftime("%Y-%m-%d").fillna("")


# ------------------------------------------------------------------ leitura
def abrir_entradas(caminho):
    """Gera (nome, arquivo-texto) para cada CSV dentro do .zip ou o próprio .csv."""
    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX")]
            if not csvs:
                sys.exit(f"ERRO: {caminho.name} não tem nenhum .csv dentro.")
            for nome in csvs:
                with z.open(nome) as bruto:
                    yield f"{caminho.name} > {nome}", io.TextIOWrapper(bruto, encoding="utf-8-sig", newline="")
    else:
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            yield caminho.name, f


def listar_entradas(alvo):
    p = Path(alvo)
    if not p.exists() and os.environ.get("REDE_GPS"):
        p = Path(os.environ["REDE_GPS"]) / alvo
    if not p.exists():
        sys.exit(f"ERRO: não encontrei {alvo}")
    if p.is_dir():
        arquivos = sorted(f for f in p.iterdir() if f.suffix.lower() in (".zip", ".csv"))
        if not arquivos:
            sys.exit(f"ERRO: nenhum .zip ou .csv em {p}")
        return arquivos
    return [p]


# ------------------------------------------------------------------ principal
def main():
    carregar_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", help="arquivo .zip/.csv recebido ou pasta com vários")
    ap.add_argument("--substituir", action="store_true", help="refaz dias que já têm arquivo preparado")
    ap.add_argument("--forcar", action="store_true",
                    help=f"grava mesmo com mais de {LIMITE_PROBLEMAS:.0%} de linhas com problema")
    args = ap.parse_args()

    saidas = {}          # dia -> (arquivo gzip aberto, writer, caminho final, caminho parcial)
    contagem = {}        # dia -> linhas
    problemas = {"data_referencia inválida": 0, "latitude fora da RMBH ou vazia": 0,
                 "longitude fora da RMBH ou vazia": 0, "entrada_ponto diferente de true/false": 0}
    total = 0

    try:
        for caminho in listar_entradas(args.entrada):
            for nome, texto in abrir_entradas(caminho):
                print(f"Lendo {nome} ...", flush=True)
                leitor = pd.read_csv(texto, sep=";", dtype=str, keep_default_na=False,
                                     chunksize=PARTE, quoting=csv.QUOTE_MINIMAL)
                for i, df in enumerate(leitor):
                    if i == 0 and list(df.columns) != COLUNAS:
                        falta = [c for c in COLUNAS if c not in df.columns]
                        sobra = [c for c in df.columns if c not in COLUNAS]
                        sys.exit(f"ERRO em {nome}: colunas diferentes do esperado.\n"
                                 f"  faltando: {falta or '-'}\n  a mais: {sobra or '-'}\n"
                                 f"  (se só a ordem mudou, peça ao órgão para manter a ordem original)")
                    total += len(df)

                    df["data_referencia"] = data_iso(df["data_referencia"])
                    df["data_escala"] = data_iso(df["data_escala"])
                    lat, df["latitude"] = corrigir_coordenada(df["latitude"])
                    lon, df["longitude"] = corrigir_coordenada(df["longitude"])

                    ruim_data = df["data_referencia"] == ""
                    ruim_lat = ~lat.between(*FAIXA_LAT)
                    ruim_lon = ~lon.between(*FAIXA_LON)
                    ruim_ent = ~df["entrada_ponto"].isin(["true", "false", ""])
                    for chave, m in zip(problemas, (ruim_data, ruim_lat, ruim_lon, ruim_ent)):
                        problemas[chave] += int(m.sum())
                    ruins = ruim_lat | ruim_lon
                    df.loc[ruins, ["latitude", "longitude"]] = ""   # não publica coordenada errada

                    for dia, parte in df[~ruim_data].groupby("data_referencia", sort=False):
                        if dia not in saidas:
                            pasta = RAIZ / "data"
                            pasta.mkdir(parents=True, exist_ok=True)
                            (pasta / ".gitkeep").touch()
                            final = pasta / f"{PREFIXO}-{dia}.csv.gz"
                            if final.exists() and not args.substituir:
                                sys.exit(f"ERRO: {final} já existe. Use --substituir para refazer esse dia.")
                            parcial = final.with_name(final.name + ".parcial")
                            gz = gzip.open(parcial, "wt", encoding="utf-8", newline="", compresslevel=6)
                            gz.write(";".join(COLUNAS) + "\n")
                            saidas[dia] = (gz, final, parcial)
                            contagem[dia] = 0
                        parte.to_csv(saidas[dia][0], sep=";", index=False, header=False, lineterminator="\n")
                        contagem[dia] += len(parte)
                    print(f"   {total:,} linhas".replace(",", "."), flush=True)
    finally:
        for gz, _, _ in saidas.values():
            gz.close()

    # ---------- resumo ----------
    print("\n" + "=" * 60)
    print(f"Linhas lidas: {total:,}".replace(",", "."))
    for dia in sorted(contagem):
        print(f"  {dia}: {contagem[dia]:,} linhas".replace(",", "."))
    n_prob = max(problemas.values()) if problemas else 0
    print("\nProblemas encontrados:")
    for k, v in problemas.items():
        print(f"  {k}: {v:,}".replace(",", ".") + (f" ({v / total:.2%})" if total and v else ""))
    if any(problemas.values()):
        print("  -> coordenadas fora da região foram deixadas em branco; linhas sem data foram descartadas.")

    if total == 0 or (total and n_prob / total > LIMITE_PROBLEMAS and not args.forcar):
        for _, _, parcial in saidas.values():
            Path(parcial).unlink(missing_ok=True)
        sys.exit(f"\nPAROU: mais de {LIMITE_PROBLEMAS:.0%} das linhas com problema (ou arquivo vazio). "
                 "Nada foi gravado. Verifique o arquivo com o órgão "
                 "(ou rode de novo com --forcar se tiver certeza).")

    for _, final, parcial in saidas.values():
        os.replace(parcial, final)
    print("\nArquivos prontos:")
    for dia in sorted(saidas):
        final = saidas[dia][1]
        print(f"  {final.relative_to(RAIZ)}  ({final.stat().st_size / 1e6:.1f} MB)")
    print("\nPróximo passo: python scripts/publicar_gps.py   (simulação) e depois com --executar")


if __name__ == "__main__":
    main()
