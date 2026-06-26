# IML-Dengue

Projeto de dengue usando dados do SINAN. A ideia é tratar os dados, fazer análises e depois usar um modelo de machine learning junto com um site de triagem.

## Organização

```text
dengue_pipeline/       código Python usado na limpeza
notebooks/
  cleaning/            notebooks de limpeza
  analysis/            análise exploratória
  modeling/            testes dos modelos
data/
  raw/
    parquet/           dados originais em Parquet
    csv/               dados originais em CSV
  processed/           bases geradas pelo tratamento
docs/
  references/          documentos do SINAN
  plans/               planos de alterações
reports/figures/       gráficos gerados pela análise
src/                   código do site em React
public/                arquivos públicos do site
```

Os notebooks servem para executar e visualizar as etapas. O código reutilizável fica em `dengue_pipeline/`.

## Dados

Foram usados os arquivos de dengue de 2017, 2018 e 2019:

```text
data/raw/parquet/DENGBR17.parquet
data/raw/parquet/DENGBR18.parquet
data/raw/parquet/DENGBR19.parquet
```

As versões em CSV ficam em `data/raw/csv/`.

## Tratamento de dados

Os arquivos principais são:

```text
dengue_pipeline/cleaner.py
dengue_pipeline/sinan_mappings.py
dengue_pipeline/cbo_map.py
dengue_pipeline/paths.py
notebooks/cleaning/tratamento_dados_dengue.ipynb
```

A classe principal é `DengueDataCleaner`. Ela junta as limpezas feitas pelos membros e gera o dataframe final.

No tratamento:

- As colunas do SINAN foram renomeadas para nomes mais fáceis.
- Foram criadas labels para sexo, raça, gestação, escolaridade, UF e classificação final.
- Foi adicionado o mapeamento CBO das ocupações.
- Foram mantidos o código e o nome da ocupação.
- Foram mantidas as datas de notificação e início dos sintomas.
- Foi criada a coluna `days_to_notification`.
- Foram removidas colunas de encerramento que poderiam causar vazamento de dados.
- A classificação final foi convertida para `0 = descartado` e `1 = confirmado`.

O tratamento para machine learning gera:

```text
data/processed/dengue_tratado_ml.parquet
```

## Como rodar a limpeza

Instalar as dependências:

```powershell
py -3.11 -m pip install pandas numpy pyarrow
```

Testar a classe:

```powershell
py -3.11 -c "from dengue_pipeline import DengueDataCleaner; df = DengueDataCleaner().transformar_analise(); print(df.shape)"
```

Também é possível abrir os notebooks da pasta `notebooks/`.

## Análise exploratória

O notebook está em:

```text
notebooks/analysis/analise_exploratoria_dengue.ipynb
```

Os gráficos gerados são salvos em `reports/figures/`. Essa mesma pasta é usada pela página de gráficos do site.

## Site

O site foi feito com React, TypeScript e Vite.

Rotas:

```text
/          página inicial
/triagem   formulário de triagem
/graphics  página com os gráficos da análise
```

A triagem ainda usa regras simples de `src/services/dengueRules.ts`. Ela ainda não está conectada a um modelo real.

## Como abrir o site

```powershell
npm install
npm run dev
```

O endereço normalmente é `http://localhost:5173`.

Para testar o build:

```powershell
npm run build
```

## Próximos passos

- Corrigir e analisar os outliers de `days_to_notification`.
- Finalizar o tratamento para machine learning.
- Treinar e comparar os modelos.
- Conectar o modelo escolhido ao site.
