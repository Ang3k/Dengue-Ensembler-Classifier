# Compatibilidade dos dados SINAN de chikungunya com o pipeline de dengue

Data da auditoria: 2026-07-04

Fontes:

- [Sinan/Febre de Chikungunya](https://dadosabertos.saude.gov.br/dataset/arboviroses-febre-de-chikungunya)
- [Dicionário de dados de chikungunya](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Chikungunya/dic_dados_chikungunya.pdf)

## Conclusão

Os dados são utilizáveis para construir um classificador de chikungunya com a
mesma arquitetura geral do projeto de dengue, mas o pipeline atual não pode ser
executado sem alterações.

O recorte recomendado é:

- 2015-2016: somente auditoria histórica; os arquivos têm 38 colunas e não
  possuem os 12 sintomas usados pelo modelo;
- 2017-2023: treino;
- 2024: validação, tuning, early stopping, pesos e limiares;
- 2025: teste final;
- 2026: não usar no desenvolvimento ou teste, pois é um ano incompleto.

Após exigir que o ano de `SEM_NOT` coincida com a partição, esse recorte fornece
1.150.714 casos para treino, 393.413 para validação e 235.703 para teste.

## Esquemas encontrados

| Período | Colunas brutas | Mesmo conjunto de colunas dentro do período | Compatível com as 33 colunas exigidas pelo ETL de dengue |
|---|---:|---|---|
| 2015-2016 | 38 | Sim | Não |
| 2017-2020 | 116 | Sim | Sim |
| 2021-2026 | 122 | Sim | Sim |

Há somente uma mudança de ordem das colunas em 2019. Como o ETL seleciona por
nome, ela não tem efeito.

Na comparação direta com os ZIPs de dengue já fixados no projeto:

- em 2017-2019, as 116 colunas de chikungunya são um subconjunto exato das 119
  colunas de dengue; só faltam `CS_FLXRET`, `DT_NASC` e `FLXRECEBI`, que não
  entram no modelo;
- em 2020, as 116 colunas também são um subconjunto exato das 121 de dengue; as
  cinco ausentes são metadados que não entram no modelo;
- em 2021, chikungunya contém todas as 121 colunas de dengue e acrescenta
  `NU_LOTE_I`.

Portanto, de 2017 em diante, as diferenças na quantidade total de colunas não
afetam o contrato efetivamente consumido pelo modelo.

## Volumes e alvo

`Elegíveis` considera os rótulos válidos para cada geração do sistema e remove
registros marcados como duplicidade em `NDUPLIC_N`.

| Ano | Colunas | Brutos | Elegíveis | Positivos | Negativos | Positivos |
|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 38 | 53.271 | 33.538 | 18.747 | 14.791 | 55,90% |
| 2016 | 38 | 316.602 | 237.772 | 160.273 | 77.499 | 67,41% |
| 2017 | 116 | 247.662 | 225.979 | 166.345 | 59.634 | 73,61% |
| 2018 | 116 | 118.779 | 105.249 | 74.562 | 30.687 | 70,84% |
| 2019 | 116 | 178.147 | 149.927 | 103.579 | 46.348 | 69,09% |
| 2020 | 116 | 102.496 | 72.471 | 43.973 | 28.498 | 60,68% |
| 2021 | 122 | 128.991 | 110.854 | 69.195 | 41.659 | 62,42% |
| 2022 | 122 | 274.331 | 248.184 | 148.605 | 99.579 | 59,88% |
| 2023 | 122 | 266.442 | 238.240 | 130.196 | 108.044 | 54,65% |
| 2024 | 122 | 426.214 | 394.223 | 232.047 | 162.176 | 58,86% |
| 2025 | 122 | 253.674 | 237.344 | 110.473 | 126.871 | 46,55% |
| 2026 | 122 | 98.802 | 83.965 | 41.496 | 42.469 | 49,42% |

Total auditado: 2.465.411 registros brutos e 2.137.746 registros rotulados.

### Mapeamento correto do alvo

Os códigos não são os mesmos usados pelo classificador de dengue:

- 2015-2016, exportação de transição: `{1, 13} -> positivo` e
  `{2, 5} -> negativo`;
- 2017 em diante: `{13} -> positivo` e `{5} -> negativo`;
- vazio, `0`, `8`, códigos de dengue e valores inválidos: remover e auditar.

Os anos de transição contêm simultaneamente as convenções antiga e nova. Apesar
de ser possível harmonizar os rótulos, 2015-2016 continuam inadequados para o
modelo atual porque não possuem as variáveis de sintomas.

O `DengueDataCleaner` atual não pode ser reutilizado sem essa alteração. Em uma
amostra de 10.000 linhas de 2017, ele reteve apenas 2.563 descartados e removeu
os 5.218 positivos de chikungunya, pois não reconhece o código `13`. A partir de
2022, ele também interrompe o processamento por limitar os anos aceitos a 2021.

## Completude das variáveis

Entre os casos elegíveis de 2017-2026:

- os 12 sintomas estão informados em 99,995% a 100% dos registros;
- idade, data de notificação, data de início dos sintomas, semana
  epidemiológica e UF de residência estão completos;
- sexo, raça e município de residência têm ausência próxima de zero;
- escolaridade tem 10,85% a 25,33% de ausência;
- ocupação tem 52,38% a 78,23% de ausência;
- região de saúde de residência varia bastante: 2,62% a 62,17% de ausência;
- `ID_UNIDADE` está 100% ausente em 2019, mas esse campo não é feature do
  modelo;
- hospitalização e UF de hospitalização são muito incompletas, mas já ficam
  fora das features para prevenir vazamento.

O padrão de sintomas é melhor que o observado nos anos antigos de dengue. Os
modelos atuais aceitam categorias ausentes, portanto escolaridade, ocupação e
região não impedem o uso, mas a variação temporal deve ser monitorada.

## Recorte temporal

Os arquivos são organizados por semana epidemiológica, não estritamente pelo
ano civil. Datas do final de dezembro pertencentes à semana epidemiológica 1 do
ano seguinte são normais e devem ser mantidas.

Há também pequenas anomalias reais de partição:

| Arquivo | Casos elegíveis cujo ano de `SEM_NOT` não coincide |
|---:|---:|
| 2022 | 111 |
| 2023 | 79 |
| 2024 | 810 |
| 2025 | 1.641 |

O arquivo de 2025 chega a conter registros da semana epidemiológica de 2026.
Usar apenas o nome do arquivo como ano introduziria dados futuros no teste.

Regra recomendada: manter apenas registros em que
`SEM_NOT // 100 == source_year`. Não se deve filtrar pelo ano civil de
`DT_NOTIFIC`, pois isso excluiria corretamente notificações de dezembro que
pertencem à primeira semana epidemiológica do ano seguinte.

## Alterações necessárias no pipeline

1. Criar uma configuração/cleaner de chikungunya, sem alterar silenciosamente o
   contrato de dengue.
2. Usar o mapeamento de alvo de chikungunya (`13` versus `5`) e manter auditoria
   dos demais códigos.
3. Restringir o ETL de modelagem a 2017-2025 e filtrar o ano de `SEM_NOT`;
   manter 2015-2016 apenas no relatório histórico e excluir 2026.
4. Normalizar `ID_AGRAVO` (`A92.0`, `A920` e `A92.` aparecem nos arquivos).
5. Excluir `NDUPLIC_N == 2`. Só dois casos rotulados de 2015 estão marcados
   assim no snapshot atual, mas a regra faz parte do contrato do SINAN.
6. Reutilizar as 12 features de sintomas e suas interações, mas trocar
   `IMPORTANT_SYMPTOMS = ("rash", "retro_orbital_pain")`, específico de dengue,
   por uma definição de chikungunya centrada em artralgia/artrite.
7. Gerar lookups de densidade e positividade, manifestos, artefatos e caminhos
   separados para chikungunya.
8. Continuar excluindo exames, critério de confirmação, `CLINC_CHIK`, evolução,
   encerramento e outras informações posteriores à triagem. Incluí-las causaria
   vazamento do alvo.

## Veredito

É viável reaproveitar a maior parte da implementação: leitura em chunks,
normalização demográfica, datas e semanas epidemiológicas, 12 sintomas,
interações, contexto local, divisão temporal, modelos e avaliação. O núcleo
reutilizável começa em 2017.

Não é seguro somente trocar os URLs no pipeline de dengue. As mudanças de alvo,
ano epidemiológico, período, sintomas importantes e separação dos artefatos são
obrigatórias.
