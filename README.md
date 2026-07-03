# Dengue Sense Classifier

Aplicação full stack de apoio à triagem de dengue com dados públicos do SINAN.
O projeto processa as notificações, constrói 107 features, treina três
classificadores e disponibiliza o ensemble por uma API FastAPI e uma interface
React.

O resultado exibido é um **score do classificador**, não uma probabilidade
clínica calibrada e nem um diagnóstico. A ferramenta não substitui avaliação
médica.

## Estado atual

- frontend React 19, TypeScript e Vite;
- API FastAPI com MLP, XGBoost e LightGBM;
- simulação anonimizada com casos do teste temporal de 2021;
- formulário com referências de ocupação, município e região de saúde;
- artefatos versionados e validados por esquema, período e SHA-256;
- pipeline reproduzível de download, ETL, contexto epidemiológico, treino e
  avaliação.

## Recorte dos dados

| Uso | Anos | Casos rotulados |
|---|---:|---:|
| Processamento e auditoria | 2014–2021 | 9.995.416 |
| Treino | 2017–2019 | 2.874.235 |
| Validação, tuning, early stopping, pesos e limiares | 2020 | 1.331.664 |
| Teste final e simulação histórica | 2021 | 940.304 |
| Total bruto baixado | 2014–2021 | 11.441.770 |

Os anos de 2014 a 2016 são processados e auditados, mas não treinam os modelos:
2014 não possui os 12 sintomas selecionados, 2015 tem esses campos quase
inteiramente ausentes e 2016 ainda é parcial. O treino começa em 2017, período
que também usa a mesma definição moderna do alvo.

A classificação final é harmonizada assim:

- 2014–2016: `{1, 2, 3, 4, 10, 11, 12} → 1` e `{5} → 0`;
- 2017–2021: `{10, 11, 12} → 1` e `{5} → 0`;
- `{0, 8, 9, vazio, inesperado} → removido e auditado`.

O snapshot oficial, os hashes, os esquemas e as contagens esperadas ficam em
`data/dengue_manifest.json`.

## Features e prevenção de vazamento

O esquema `2.2.0` possui 107 features:

- idade, escolaridade, ocupação e localização;
- sexo, raça/cor e gestação;
- 12 sintomas, contagens e interações entre sintomas;
- mês e semana epidemiológica em representação cíclica;
- intervalo entre início dos sintomas e notificação;
- densidade local de notificações nas quatro semanas anteriores;
- positividade local entre casos rotulados das quatro semanas anteriores.

Nenhuma informação de exame, encerramento, evolução, hospitalização ou sinal
posterior do **caso atual** entra no modelo. A positividade local é uma feature
agregada de contexto e depende de classificações de semanas anteriores; em uso
operacional, sua disponibilidade pode sofrer atraso até esses casos serem
encerrados.

No dataset de cada ano, densidade e positividade usam apenas semanas passadas do
mesmo ano. Para uma nova notificação isolada, a API consulta valores sazonais
médios construídos somente com os anos de treino (2017–2019). A simulação usa o
valor histórico exato calculado para o caso de 2021.

## Modelos e resultado em 2021

Os pesos do ensemble são os recalls normalizados na validação de 2020. O ponto
de operação publicado usa limiar manual `0,30`, escolhido para priorizar
sensibilidade. Os limiares individuais maximizam balanced accuracy em 2020.

| Modelo | Limiar | Precisão | Recall | Especificidade | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| MLP | 0,54 | 0,784 | 0,619 | 0,840 | 0,692 | 0,820 | 0,809 |
| XGBoost | 0,59 | 0,788 | 0,632 | 0,840 | 0,701 | 0,828 | 0,821 |
| LightGBM | 0,60 | 0,793 | 0,618 | 0,848 | 0,695 | 0,828 | 0,820 |
| Ensemble | 0,30 | 0,661 | 0,871 | 0,580 | 0,752 | 0,829 | 0,820 |

O ensemble acertou 72,1% dos 940.304 registros de teste. As métricas completas,
curvas e matrizes de confusão estão em `reports/metrics/modeling/` e
`reports/figures/modeling/evaluation/`.

## Estrutura

```text
api.py                              API, validação dos artefatos e simulação
src/                                frontend React
dengue_pipeline/cleaner.py          limpeza por chunks e harmonização do alvo
dengue_pipeline/features.py         esquema único das 107 features
dengue_pipeline/datasets.py         carregamento das partições temporais
dengue_pipeline/models/             MLP, XGBoost e LightGBM
scripts/prepare_dengue_data.py      download validado e ETL
scripts/augment_local_density.py    contexto epidemiológico e lookups de serving
scripts/prepare_reference_data.py   municípios/regiões usados pelo formulário
scripts/train_models.py             treino 2017–2019 e validação 2020
scripts/evaluate_models.py          calibração em 2020 e teste final em 2021
artifacts/models/                   modelos, lookups e manifestos
data/dengue_manifest.json           snapshot e contrato dos dados oficiais
data/municipios.json                referência de municípios
data/regioes_saude.json             regiões compatíveis com os códigos do treino
tests/                              testes do pipeline, modelos e API
```

Os ZIPs oficiais e os Parquets completos ficam fora do Git. O repositório
versiona os modelos finais, os lookups, o pool reduzido da simulação, as
referências do formulário, as métricas e os relatórios.

## Requisitos e instalação

- Python 3.11;
- Node.js `^20.19.0` ou `>=22.12.0`;
- CUDA para o comando de treino padrão da MLP e do XGBoost. A API faz inferência
  em CPU quando CUDA não está disponível.

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
```

## Executar a aplicação

Terminal da API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api:app --reload
```

Terminal do frontend:

```powershell
npm run dev
```

Por padrão, o frontend usa `http://localhost:8000`. Para outro endereço:

```powershell
$env:VITE_API_URL="https://api.exemplo.com"
npm run build
```

No backend, libere explicitamente a origem do frontend:

```powershell
$env:DENGUE_CORS_ORIGINS="https://app.exemplo.com"
python -m uvicorn api:app
```

`VITE_API_URL` é incorporada durante o build. Como o frontend usa
`BrowserRouter`, a hospedagem estática também precisa redirecionar rotas como
`/triagem`, `/pipeline` e `/graphics` para `index.html`.

## Pipeline completo

### 1. Baixar, conferir e preparar

```powershell
python scripts/prepare_dengue_data.py
```

O script baixa os oito ZIPs oficiais, exige os SHA-256 fixados, lê chunks de
100.000 linhas e grava uma partição de análise e uma de ML por ano. Divergências
de hash, tamanho, cabeçalho, contagem, classes ou esquema interrompem o processo.
O relatório fica em `reports/data/dengue_data_audit.csv`.

### 2. Calcular o contexto epidemiológico

```powershell
python scripts/augment_local_density.py
```

Esse passo preenche `local_density` e `local_positivity` nos Parquets de ML e
gera os dois lookups usados pela API. Ele deve rodar depois do ETL e antes do
treino.

### 3. Regenerar a referência de regiões

```powershell
python scripts/prepare_reference_data.py
```

Os nomes vêm da referência de [Macrorregião e Região de Saúde do
OpenDataSUS](https://opendatasus.saude.gov.br/pt_PT/dataset/macrorregiao-de-saude).
Os códigos enviados ao modelo são os códigos internos observados no período de
treino. A referência atual cobre 4.642 municípios; municípios sem ocorrência
válida no treino permanecem sem região e são tratados como categoria ausente.

### 4. Treinar

```powershell
python scripts/train_models.py --n-trials 200 --max-epochs 150 --tuning-sample-size 200000
```

Para treinar MLP e XGBoost em CPU, acrescente `--device cpu`. O LightGBM usa CPU
por padrão. Encoders e medianas da MLP são ajustados apenas em 2017–2019. Optuna
e early stopping usam 2020; 2021 não participa de nenhuma decisão.

O treino falha se as partições, as features de contexto ou as contagens
temporais não forem as esperadas, e registra pico de memória no
`model_manifest.json`.

### 5. Avaliar e publicar o ensemble

```powershell
python scripts/evaluate_models.py --threshold-step 0.01 --ensemble-threshold 0.3
```

Todas as decisões são congeladas com 2020 antes de abrir o teste de 2021. O
comando atualiza as métricas, figuras e `ensemble_config.json`.

## API

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health` | modelos, períodos, hashes, lookups e ensemble |
| `POST` | `/predict` | score de uma nova triagem |
| `POST` | `/api/v1/simulations/random` | caso anonimizado e resultado histórico de 2021 |
| `GET` | `/api/v1/triage/options` | opções gerais do formulário |
| `GET` | `/api/v1/references/occupations` | busca de ocupações CBO |
| `GET` | `/api/v1/references/municipalities` | busca de municípios por nome e UF |
| `GET` | `/api/v1/references/health-regions` | região compatível com o código do modelo |

`POST /predict` aceita campos ausentes. Sintomas usam `1` para sim, `0` para não
e `null` para não informado. A API converte o código IBGE de município com sete
dígitos para o código SINAN de seis dígitos antes de consultar os modelos e os
lookups.

## Verificação

```powershell
python -m unittest discover -s tests -v
npm run lint
npm run build
python -m pip check
npm audit
```

Além dos comandos acima, a aplicação pode ser conferida em `/health` e pelas
quatro rotas do frontend. O build de produção não inicia a API; ambos precisam
ser implantados separadamente.
