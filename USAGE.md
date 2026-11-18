# Passo a passo: publicação do GPS dos ônibus metropolitanos no dados.mg

Os comandos devem ser digitados no **Git Bash**.

## Configuração (uma vez só)

### 1. Instalar os programas

- Python: https://www.python.org/downloads (na instalação, marque **Add Python to PATH**)
- Git: https://git-scm.com/downloads

### 2. Pedir os acessos

- Usuário no dados.mg incluído na organização da SEINFRA como **Editor** (pedir à CGE).
- Permissão de escrita no repositório `transparencia-mg/seinfra-gps-onibus-metropolitano` no GitHub (pedir à CGE).

### 3. Identificar-se no Git

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu.email@infraestrutura.mg.gov.br"
```

### 4. Baixar o repositório

```bash
cd /c/
git clone https://github.com/transparencia-mg/seinfra-gps-onibus-metropolitano.git
cd seinfra-gps-onibus-metropolitano
```

### 5. Criar o ambiente Python

```bash
python -m venv venv
. venv/Scripts/activate
pip install -r requirements.txt
```

### 6. Gerar a chave de API no dados.mg

- Entrar em https://dados.mg.gov.br com o seu usuário.
- Clicar no seu nome > **API Tokens** > dar um nome (ex.: `gps`) > **Create API Token**.
- Copiar a chave gerada.

### 7. Criar o arquivo .env

```bash
cp .env.exemplo .env
notepad .env
```

Deixar o conteúdo exatamente assim, colando a sua chave, e salvar:

```
CKAN_HOST=https://dados.mg.gov.br
CKAN_KEY=cole-aqui-a-sua-chave
OWNER_ORG=secretaria-de-estado-de-infraestrutura-e-mobilidade-de-minas-gerais-seinfra
```

## Publicação (a cada arquivo)

### 1. Abrir a pasta e ativar o ambiente

```bash
cd /c/seinfra-gps-onibus-metropolitano
. venv/Scripts/activate
```

### 2. Atualizar o repositório

```bash
git pull
```

### 3. Preparar o arquivo

Um arquivo:

```bash
python scripts/preparar_gps.py "/c/Users/SEU_USUARIO/Downloads/NOME_DO_ARQUIVO.zip"
```

Vários dias (todos os .zip de uma pasta):

```bash
python scripts/preparar_gps.py "/c/caminho/da/pasta"
```

### 4. Conferir

```bash
python scripts/publicar_gps.py
```

### 5. Publicar no dados.mg

```bash
python scripts/publicar_gps.py --executar
```

### 6. Atualizar o GitHub

```bash
python scripts/atualizar_github.py
```

### 7. Conferir no portal

https://dados.mg.gov.br/dataset/gps-onibus-metropolitano

## Corrigir um dia já publicado

```bash
python scripts/preparar_gps.py "/c/caminho/arquivo_corrigido.zip" --substituir
python scripts/publicar_gps.py --so 2026-09-19 --executar
python scripts/atualizar_github.py
```
