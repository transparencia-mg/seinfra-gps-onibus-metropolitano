Posições de GPS dos ônibus do transporte coletivo metropolitano da Região Metropolitana de Belo Horizonte (RMBH) em {ANO}.

Cada registro é uma posição enviada por um veículo durante uma viagem, com a linha, o consórcio, o sentido, o horário, a latitude e a longitude (WGS 84) e o ponto de parada, quando houver.

## Como os arquivos estão organizados

- **Um arquivo por dia**, chamado `gps-onibus-metropolitano-AAAA-MM-DD.csv.gz`.
- Os arquivos são **CSV compactados (.gz)**, com separador `;` e codificação UTF-8. Para abrir, basta descompactar (7-Zip, WinRAR ou o próprio Windows 11). Python, R, QGIS e DuckDB leem o `.gz` diretamente, sem descompactar.
- Cada dia tem cerca de 3 milhões de linhas. **O Excel abre no máximo 1.048.576 linhas**, então ele não consegue abrir um dia inteiro. Use Python, R, Power BI, QGIS ou DuckDB.
- O recurso **lista-de-arquivos-{ANO}.txt** traz o link de todos os arquivos do ano, um por linha.

## Como baixar o ano inteiro de uma vez

Baixe o recurso `lista-de-arquivos-{ANO}.txt` e use um dos comandos abaixo, na mesma pasta.

**Windows (PowerShell):**

```powershell
Get-Content lista-de-arquivos-{ANO}.txt | ForEach-Object { Invoke-WebRequest $_ -OutFile (Split-Path $_ -Leaf) }
```

**Linux ou macOS:**

```bash
wget -i lista-de-arquivos-{ANO}.txt
```

**Python (sem baixar, consultando direto do portal com DuckDB):**

```python
import duckdb
urls = open("lista-de-arquivos-{ANO}.txt").read().split()
duckdb.sql(f"""
    SELECT cod_linha, data_referencia, count(*) AS registros
    FROM read_csv({urls}, delim=';', header=true)
    GROUP BY ALL ORDER BY ALL
""").show()
```

**R:**

```r
urls <- readLines("lista-de-arquivos-{ANO}.txt")
for (u in urls) download.file(u, basename(u), mode = "wb")
```

## Observações

- As coordenadas estão em graus decimais, sistema WGS 84 (EPSG:4326), com **ponto** como separador decimal.
- Coordenadas fora da RMBH, provavelmente erros de registro do equipamento, foram deixadas em branco.
