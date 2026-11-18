# Uso (tudo pelo computador)

## 1. Baixar o repositório (primeira vez)

```bash
git clone https://github.com/transparencia-mg/seinfra-gps-onibus-metropolitano.git
cd seinfra-gps-onibus-metropolitano
python -m venv venv
. venv/Scripts/activate
pip install -r requirements.txt
copy .env.exemplo .env
```

Abra o `.env` e preencha `CKAN_HOST`, `CKAN_KEY` (a **sua** chave do dados.mg) e `OWNER_ORG`. O `.env` fica só no seu computador e nunca vai para o GitHub.

## 2. Atualizar o repositório (toda vez, antes de começar)

```bash
cd seinfra-gps-onibus-metropolitano
. venv/Scripts/activate
git pull
```

## 3. Preparar os arquivos

```bash
python scripts/preparar_gps.py "L:\caminho\arquivo.zip"    # um arquivo
python scripts/preparar_gps.py "L:\caminho\pasta"          # vários dias: todos os .zip/.csv da pasta
```

Se precisar refazer um dia já preparado, acrescente `--substituir`.

## 4. Publicar no dados.mg (o datapackage.json é atualizado junto)

```bash
python scripts/publicar_gps.py --ano 2026                         # simulação: só confere
python scripts/publicar_gps.py --ano 2026 --executar              # todos os dias preparados
python scripts/publicar_gps.py --ano 2026 --mes 2026-09 --executar      # só um mês
python scripts/publicar_gps.py --ano 2026 --so 2026-09-19 --executar    # só um dia
```

## 5. Atualizar o GitHub

```bash
python scripts/atualizar_github.py
```
