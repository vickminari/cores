import pandas as pd
import ollama
from openai import OpenAI
import json
import time
import re
import os
import argparse
from typing import Dict, Any

# =========================
# CONFIGURAÇÃO GERAL
# =========================

LISTA_MODELOS = [
    #"gemma3:12b",
    # "qwen3:8b",
    #"qwen3:14b",
    "qwen3.5:9b"
]

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)  

TAMANHO_AMOSTRA = 99999 # Todos os relatospyth
# FILENAME_INPUT = "procedimentos_drci_limpo.csv"
FILENAME_INPUT = "bo_facil_limpo.csv"

# =========================
# CAMINHOS
# =========================

def setup_caminhos(filename_input: str, output_dir: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isabs(filename_input):
        path_input = filename_input
    else:
        path_input = os.path.join(base_dir, "..", "data", filename_input)

    if os.path.isabs(output_dir):
        path_output = output_dir
    else:
        path_output = os.path.join(base_dir, "..", "results", output_dir)
    return os.path.normpath(path_input), os.path.normpath(path_output)

# =========================
# PROMPT 
# =========================

def construir_system_prompt() -> str:
    return """Você é um sistema de Extração de Entidades Nomeadas (NER) aplicado a relatos policiais brasileiros.

REGRAS OBRIGATÓRIAS:
- Extraia SOMENTE entidades explicitamente mencionadas no texto.
- NÃO infira, deduza, normalize ou complete informações.
- NÃO crie entidades implícitas.
- Responda EXCLUSIVAMENTE no formato JSON especificado.
- Não inclua comentários, explicações ou texto fora do JSON.

PAPÉIS VÁLIDOS PARA PESSOAS (use APENAS estes):
- VITIMA
- COMUNICANTE
- SUPOSTO_INFRATOR
- ENVOLVIDO

FORMATOS OBRIGATÓRIOS:
- "empresas"            → lista de strings     Ex: ["Magazine Luiza", "Bradesco"]
- "datas"               → lista de strings     Ex: ["20/06/2025", "17:30h"]
- "valores_monetarios"  → lista de strings     Ex: ["R$ 3.955,60"]
- "contas_bancarias"    → lista de objetos     Ex: [{"agencia": "1234", "numero_conta": "56789-0", "tipo_conta": "corrente", "titular": "João Silva", "banco": "Bradesco"}]

ERROS PROIBIDOS:
- ERRADO:  "empresas": [{"nome": "Magazine Luiza", "papeis": ["EMPRESA"]}]
  CORRETO: "empresas": ["Magazine Luiza"]

- ERRADO:  "datas": [{"data": "25/12/2025", "papel": "DATA"}]
  CORRETO: "datas": ["25/12/2025", "17:30h"]

- ERRADO:  {"nome": "Paloma", "papeis": ["FILHA"]}
  CORRETO: {"nome": "Paloma", "papeis": ["ENVOLVIDO"]}
  OBS: caso não identificado o papel, coloque "ENVOLVIDO"

SCHEMA JSON OBRIGATÓRIO:
{
  "entidades": {
    "pessoas": [
      {"nome": "string", "papeis": ["VITIMA|COMUNICANTE|SUPOSTO_INFRATOR|ENVOLVIDO"]}
    ],
    "empresas": [],
    "cpfs": [],
    "cnpjs": [],
    "telefones": [],
    "emails": [],
    "chaves_pix": [],
    "redes_sociais": [],
    "bancos": [],
    "contas_bancarias": [
      {"agencia": null, "numero_conta": null, "tipo_conta": null, "titular": null, "banco": null}
    ],
    "valores_monetarios": [],
    "datas": [],
    "urls": [],
    "placas_veiculos": []
  }
}""".strip()


def construir_user_prompt(relato: str, envolvidos_resumo: str = "") -> str:
    pessoas_pre = parsear_envolvidos(envolvidos_resumo)
    pessoas_json = json.dumps(pessoas_pre, ensure_ascii=False)

    partes = []

    if pessoas_pre:
        partes.append(f"""PESSOAS PRÉ-IDENTIFICADAS (use exatamente no campo "pessoas", não altere):
{pessoas_json}""")

    partes.append(f"""RELATO:
\"\"\"{relato}\"\"\"

Extraia as entidades do relato acima seguindo o schema e regras definidos.""")

    return "\n\n".join(partes)

def validar_schema(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garante que todas as chaves esperadas existam,
    tratando listas abertas para chaves_pix e redes_sociais.
    """

    CONTA_BANCARIA_PADRAO = {
        "agencia": None,
        "numero_conta": None,
        "tipo_conta": None,
        "titular": None,
        "banco": None
    }

    entidades = dados.get("entidades", {})
    resultado = {}

    # --- pessoas: lista de objetos ---
    pessoas_raw = entidades.get("pessoas", [])
    resultado["pessoas"] = pessoas_raw if isinstance(pessoas_raw, list) else []

    # --- listas simples ---
    listas_simples = [
        "empresas", "cpfs", "cnpjs", "telefones", "emails",
        "chaves_pix", "redes_sociais", "bancos",
        "valores_monetarios", "datas", "urls", "placas_veiculos"
    ]
    for chave in listas_simples:
        valor = entidades.get(chave, [])
        resultado[chave] = valor if isinstance(valor, list) else []

    # --- contas_bancarias: lista de objetos estruturados ---
    contas_raw = entidades.get("contas_bancarias", [])
    contas_validadas = []

    if isinstance(contas_raw, list):
        for conta in contas_raw:
            if isinstance(conta, dict):
                contas_validadas.append({
                    chave: conta.get(chave, None)
                    for chave in CONTA_BANCARIA_PADRAO
                })
    
    resultado["contas_bancarias"] = contas_validadas

    return resultado

# MÉTRICAS
# =========

def contar_entidades(entidades: Dict[str, Any]) -> int:
    return sum(len(v) for v in entidades.values() if isinstance(v, list))

# PROCESSAMENTO POR MODELO
# =========================

MAPA_PAPEIS = {
    "VÍTIMA": "VITIMA",
    "VITIMA": "VITIMA",
    "COMUNICANTE": "COMUNICANTE",
    "SUPOSTO AUTOR/INFRATOR": "SUPOSTO_INFRATOR",
    "ENV": "ENVOLVIDO",
}

def parsear_envolvidos(envolvidos_resumo: str) -> list[dict]:
    if not envolvidos_resumo or not envolvidos_resumo.strip():
        return []

    pessoas = []
    for bloco in envolvidos_resumo.split("#"):
        bloco = bloco.strip()
        match = re.match(r"^(.+?)\s*\(([^)]+)\)$", bloco)
        if not match:
            continue

        nome = match.group(1).strip()

        # ignora desconhecidos
        if re.match(r"(?i)^desconhecido\b", nome):
            continue

        papeis_raw = [p.strip() for p in match.group(2).split(",")]
        papeis = [MAPA_PAPEIS.get(p.upper(), p) for p in papeis_raw]

        pessoas.append({"nome": nome, "papeis": papeis})

    return pessoas

def _extrair_campo_geo(row: pd.Series, campo: str) -> str | None:
    valor = row.get(campo, None)
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    return str(valor).strip().upper()


def processar_modelo(df: pd.DataFrame, modelo: str, pasta_saida: str, nome_entrada: str):
    print(f"\n🚀 Processando modelo: {modelo}")
    resultados = []

    for i, (idx, row) in enumerate(df.iterrows(), start=1):
        relato = row.get("relato_historico", "")
        municipio = _extrair_campo_geo(row, "municipio")
        uf = _extrair_campo_geo(row, "uf")
        id = row.get("id_procedimento", idx)
        envolvidos_resumo = row.get("envolvidos_resumo", "")

        print(f"  [{i}/{len(df)}] Extraindo entidades...", end=" ")

        inicio = time.time()

        try:
            # response = ollama.chat(
            #     model=modelo,
            #     format="json",
            #     messages=[{"role": "user", "content": construir_prompt(relato)}]
            # )

            response = client.chat.completions.create(
                model=modelo,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": construir_system_prompt()},
                    {"role": "user", "content": construir_user_prompt(relato, envolvidos_resumo)}
                ],
                reasoning_effort="none",
            )

            conteudo = response.choices[0].message.content or ""
            conteudo = re.sub(r"```json|```", "", conteudo).strip()
            bruto = json.loads(conteudo)

            entidades = validar_schema(bruto)
            qtd = contar_entidades(entidades)

            resultados.append({
                "id_relato": int(id),
                "modelo": modelo,
                "municipio": municipio,
                "uf": uf,
                "tempo_execucao": round(time.time() - inicio, 2),
                "quantidade_entidades": qtd,
                "entidades": entidades,
                "relato_original": relato
            })

            print(f"✅ {qtd} entidades ({time.time() - inicio:.1f}s)")

        except Exception as e:
            print(f"❌ erro: {e}")
            resultados.append({
                "id_relato": int(id),
                "modelo": modelo,
                "municipio": municipio,
                "uf": uf,
                "erro": str(e),
                "relato_original": relato
            })

    os.makedirs(pasta_saida, exist_ok=True)
    nome_arquivo = f"NER_{nome_entrada}_{modelo.replace(':', '_')}_amostra{len(df)}.json"
    path_saida = os.path.join(pasta_saida, nome_arquivo)

    with open(path_saida, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"💾 Resultado salvo em: {path_saida}")

# MAIN
# ======

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrai entidades com LLM a partir de relatos em CSV."
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=TAMANHO_AMOSTRA,
        help="Tamanho da amostra de relatos a processar",
    )
    parser.add_argument(
        "--entrada",
        default=FILENAME_INPUT,
        help="Nome do arquivo CSV em data/",
    )
    parser.add_argument(
        "--saida",
        default="ner_extracao",
        help="Pasta de saída dentro de results (ou caminho absoluto)",
    )
    parser.add_argument(
        "--models",
        default=",".join(LISTA_MODELOS),
        help="Lista de modelos separados por vírgula",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    path_in, path_out = setup_caminhos(args.entrada, args.saida)
    modelos = [m.strip() for m in args.models.split(",") if m.strip()]
    if not modelos:
        raise SystemExit("Informe ao menos um modelo em --models.")

    try:
        df = pd.read_csv(path_in, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path_in, encoding="latin1")

    df = df[
        df["naturezas"].str.contains("ESTELIONATO", case=False, na=False)
    ].dropna(subset=["relato_historico"])

    df_amostra = df.sample(
        n=min(args.amostra, len(df)),
        random_state=42
    )

    print(f"\n📊 Amostra selecionada: {len(df_amostra)} relatos\n")

    nome_entrada = os.path.basename(args.entrada)
    for modelo in modelos:
        try:
            ollama.show(modelo)
            processar_modelo(df_amostra, modelo, path_out, nome_entrada)
        except Exception:
            print(f"⚠️ Modelo não disponível: {modelo}")