# C.O.R.E.S. — Correlação de Ocorrências e Reconhecimento de Entidades para Segurança

> Esta aplicação tem como base o [ARCA](https://github.com/vcsa86/arca)

Plataforma local de análise estrutural de crimes de estelionato a partir de relatos policiais.  
Protótipo acadêmico para validação junto à Secretaria de Segurança Pública (SSP/PI).

## Funcionalidades atuais

- **Extração NER via LLM** (`src/extracao.py`)
	- Consome relatos em CSV e extrai entidades (pessoas, empresas, CPFs, CNPJs, telefones, emails, chaves PIX, redes sociais, bancos, contas bancárias, valores, datas, URLs e placas).
	- Usa modelos locais via Ollama (API compatível com OpenAI) e salva JSONs em `results/ner_extracao`.
	- Filtra relatos por natureza (ex.: “ESTELIONATO”) e suporta amostragem.

- **Normalização de entidades** (`src/normalizar.py`)
	- Padroniza CPFs, CNPJs, telefones, valores monetários, URLs, emails, nomes e bancos.
	- Reclassifica automaticamente empresas conhecidas como bancos.
	- Gera arquivos `_normalizado.json` em `results/ner_normalizado`.

- **Deduplicação por nr_registro** (`src/limpar_registros_duplicados.py`)
	- Aplicado no dataset principal utilizado no pipeline: DRCI - Delegacia de Repressão a Crimes de Informática
	- Mantém apenas o registro com relato mais completo quando há duplicidade de `nr_registro`.
	- Deve ser rodado antes da extração para não haver duplicatas.

## Pipeline atual (estado do projeto)

1. **Preparação do CSV**
	 - Entrada: `data/*.csv` (ex.: `bo_facil_limpo.csv`, `procedimentos_drci_limpo.csv`).
	 - Opcional: deduplicação por `nr_registro` com `src/limpar_registros_duplicados.py`.

2. **Extração de entidades (NER)**
	 - Script: `src/extracao.py`.
	 - Saída: `results/ner_extracao/NER_<arquivo>_<modelo>_amostraN.json`.

3. **Normalização**
	 - Script: `src/normalizar.py`.
	 - Saída: `results/ner_normalizado/NER_<arquivo>_<modelo>_amostraN_normalizado.json`.

## Próximos passos

- **Correlação entre boletins de ocorrência**
	- Construir grafos e/ou regras de similaridade para identificar vínculos entre BOs (mesmas pessoas, contas, valores, bancos, telefones e modus operandi).
- **Deduplicação por similaridade semântica**
	- Identificar relatos redundantes para outros tipos de dataset quando necessários.
- **Score de relevância e priorização**
	- Atribuir pontuação de risco/criticidade por ocorrência e por entidade.
- **Dashboard de análise**
	- Visualizações de rede, linhas do tempo e clusters por município/UF.

