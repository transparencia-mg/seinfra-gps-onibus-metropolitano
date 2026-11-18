Dados abertos das posições de GPS dos ônibus do transporte coletivo metropolitano da Região Metropolitana de Belo Horizonte (RMBH).

Os dados são publicados no [Portal de Dados Abertos de Minas Gerais](https://dados.mg.gov.br) em **um conjunto por ano** (`gps-onibus-metropolitano-AAAA`), com **um arquivo por dia** e uma **lista com o link de todos os arquivos do ano**, para quem quiser baixar tudo de uma vez.

Este repositório guarda apenas os scripts e os metadados (`AAAA/datapackage.json`). Os arquivos de dados são enviados direto ao portal e **não ficam no GitHub**: cada dia tem cerca de 3 milhões de linhas e 30 MB compactado.

- Passo a passo da publicação: [USAGE.md](USAGE.md)
- Estrutura das colunas: [schema.json](schema.json)
