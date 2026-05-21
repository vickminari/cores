import json
import os
import re
import argparse
from typing import Dict, Any

# =========================
# CAMINHOS
# =========================

def setup_caminhos(pasta_in: str | None = None, pasta_out: str | None = None):
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if pasta_in:
        path_in = pasta_in if os.path.isabs(pasta_in) else os.path.join(base_dir, "..", pasta_in)
    else:
        path_in = os.path.join(base_dir, "..", "results", "ner_extracao")

    if pasta_out:
        path_out = pasta_out if os.path.isabs(pasta_out) else os.path.join(base_dir, "..", pasta_out)
    else:
        path_out = os.path.join(base_dir, "..", "results", "ner_normalizado")

    return os.path.normpath(path_in), os.path.normpath(path_out)


BANCOS_CONHECIDOS = {
    "NUBANK",
    "BANCO INTER",
    "MERCADO PAGO",
    "CAIXA ECONÔMICA FEDERAL",
    "BRADESCO",
    "ITAÚ",
    "SANTANDER",
    "BANCO DO BRASIL"
}

# =========================
# UTILIDADES
# =========================

def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v)

# =========================
# FORMATADORES
# =========================

def formatar_cpf(v: str) -> str | None:
    d = so_digitos(v)
    if len(d) != 11:
        return None
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"

def formatar_cnpj(v: str) -> str | None:
    d = so_digitos(v)
    if len(d) != 14:
        return None
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"

def formatar_telefone(v: str) -> str | None:
    d = so_digitos(v)

    if len(d) == 11:
        return f"({d[0:2]}) {d[2]}{d[3:7]}-{d[7:11]}"

    if len(d) == 10:
        return f"({d[0:2]}) {d[2:6]}-{d[6:10]}"

    if len(d) in {8, 9}:
        if len(d) == 9:
            return f"(**) {d[0]}{d[1:5]}-{d[5:9]}"
        return f"(**) {d[0:4]}-{d[4:8]}"

    return None

def formatar_valor(v: str) -> str | None:
    v = v.lower().replace("r$", "").strip()
    v = v.replace(".", "").replace(",", ".")
    try:
        num = float(v)
        inteiro, decimal = f"{num:.2f}".split(".")
        inteiro = "{:,}".format(int(inteiro)).replace(",", ".")
        return f"R$ {inteiro},{decimal}"
    except ValueError:
        return None

def normalizar_email(v: str) -> str:
    return v.strip().lower()

def normalizar_url(v: str) -> str:
    v = v.strip().lower()
    v = re.sub(r"^https?://", "", v)
    return v.rstrip("/")

def normalizar_nome(v: str) -> str:
    v = re.sub(r"\s+", " ", v.strip())
    return v.upper()

def normalizar_agencia(v: str) -> str | None:
    d = so_digitos(v)
    return d or None

def normalizar_numero_conta(v: str) -> str | None:
    v = v.strip().upper()
    v = re.sub(r"\s+", "", v)
    v = re.sub(r"\D", "", v)
    return v or None

def normalizar_banco(v: str) -> str:
    v_original = re.sub(r"\s+", " ", v.strip()).upper()

    mapa_marcas = {
        "BANCO DO BRASIL": "BANCO DO BRASIL",
        "BB": "BANCO DO BRASIL",
        "NUBANK": "NUBANK",
        "NU BANK": "NUBANK",
        "NU PAGAMENTOS": "NUBANK",
        "NU PAGAMENTOS S.A.": "NUBANK",
        "MERCADO PAGO": "MERCADO PAGO",
        "PAGSEGURO": "PAGSEGURO",
        "STONE": "STONE",
        "BANCO INTER": "BANCO INTER",
        "INTER": "BANCO INTER",
        "CAIXA ECONÔMICA FEDERAL": "CAIXA ECONÔMICA FEDERAL",
        "CAIXA ECONOMICA FEDERAL": "CAIXA ECONÔMICA FEDERAL",
        "BRADESCO": "BRADESCO",
        "ITAÚ": "ITAÚ",
        "ITA UNIBANCO": "ITAÚ",
        "SANTANDER": "SANTANDER",
        "PICPAY": "PICPAY",
        "BANCO SANTANDER S.A.": "SANTANDER"
    }

    # 1️⃣ Match exato ou parcial antes de limpar
    for chave in mapa_marcas:
        if chave in v_original:
            return mapa_marcas[chave]

    # 2️⃣ Limpeza jurídica apenas se não houver match
    v_limpo = re.sub(r"\b(S\.A\.?|LTDA|EIRELI|S/A|ME|EPP)\b", "", v_original)
    v_limpo = re.sub(r"\s+", " ", v_limpo).strip()

    return v_limpo
    
def normalizar_rede_social(v: str) -> str:
    v = re.sub(r"\s+", " ", v.strip()).lower()

    mapa = {
        "whatsapp": "WHATSAPP",
        "face": "FACEBOOK",
        "facebook": "FACEBOOK",
        "insta": "INSTAGRAM",
        "instagram": "INSTAGRAM",
        "telegram": "TELEGRAM",
        "tiktok": "TIKTOK",
        "twitter": "TWITTER",
        "x": "TWITTER"
    }

    return mapa.get(v, v.upper())

# =========================
# DISPATCH POR CLASSE
# =========================

def normalizar_entidade(classe: str, valor: str) -> str | None:
    valor = valor.strip()

    if classe == "cpfs":
        return formatar_cpf(valor)

    if classe == "cnpjs":
        return formatar_cnpj(valor)

    if classe == "telefones":
        return formatar_telefone(valor)

    if classe == "contas_bancarias":
        return valor

    if classe == "valores_monetarios":
        return formatar_valor(valor)

    if classe == "emails":
        return normalizar_email(valor)

    if classe == "urls":
        return normalizar_url(valor)

    if classe == "redes_sociais":
        return normalizar_rede_social(valor)

    if classe == "bancos":
        return normalizar_banco(valor)

    if classe == "placas_veiculos":
        return re.sub(r"\s+", "", valor).upper()

    if classe in {"pessoas", "empresas"}:
        return normalizar_nome(valor)

    return valor or None

# =========================
# PROCESSAMENTO
# =========================

def normalizar_registro(registro: Dict[str, Any]) -> Dict[str, Any]:
    if "erro" in registro:
        return registro

    entidades = registro.get("entidades", {})
    entidades_norm = {
        classe: ([] if isinstance(valores, list) else valores)
        for classe, valores in entidades.items()
    }

    pessoas = []
    pessoas_raw = entidades.get("pessoas", [])
    if isinstance(pessoas_raw, list):
        for pessoa in pessoas_raw:
            if not isinstance(pessoa, dict):
                continue
            nome = pessoa.get("nome", "")
            nome_norm = normalizar_nome(nome) if isinstance(nome, str) else None
            papeis = pessoa.get("papeis", [])
            if not isinstance(papeis, list):
                papeis = []
            pessoas.append({
                "nome": nome_norm,
                "papeis": papeis
            })

    entidades_norm["pessoas"] = pessoas

    contas_norm = []
    contas_raw = entidades.get("contas_bancarias", [])
    if isinstance(contas_raw, list):
        for conta in contas_raw:
            if not isinstance(conta, dict):
                continue
            agencia = conta.get("agencia", None)
            numero_conta = conta.get("numero_conta", None)
            tipo_conta = conta.get("tipo_conta", None)
            titular = conta.get("titular", None)
            banco = conta.get("banco", None)

            contas_norm.append({
                "agencia": normalizar_agencia(str(agencia)) if isinstance(agencia, str) else None,
                "numero_conta": normalizar_numero_conta(str(numero_conta)) if isinstance(numero_conta, str) else None,
                "tipo_conta": tipo_conta.strip().upper() if isinstance(tipo_conta, str) and tipo_conta.strip() else None,
                "titular": normalizar_nome(titular) if isinstance(titular, str) and titular.strip() else None,
                "banco": normalizar_nome(banco) if isinstance(banco, str) and banco.strip() else None,
            })

    entidades_norm["contas_bancarias"] = contas_norm

    for classe, valores in entidades.items():
        if not isinstance(valores, list):
            continue

        if classe in {"pessoas", "contas_bancarias"}:
            continue

        for v in valores:
            if not isinstance(v, str) or not v.strip():
                continue

            nv = normalizar_entidade(classe, v)
            if not nv:
                continue

            # 🔎 Reclassificação ontológica
            if classe == "empresas" and nv in BANCOS_CONHECIDOS:
                classe_destino = "bancos"
            else:
                classe_destino = classe

            entidades_norm.setdefault(classe_destino, []).append(nv)

    # remover duplicatas por classe
    for classe in entidades_norm:
        if isinstance(entidades_norm[classe], list):
            if entidades_norm[classe] and all(isinstance(v, str) for v in entidades_norm[classe]):
                entidades_norm[classe] = list(dict.fromkeys(entidades_norm[classe]))

    registro["entidades"] = entidades_norm
    return registro

# =========================
# MAIN
# =========================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normaliza arquivos JSON de extração NER."
    )
    parser.add_argument(
        "--entrada",
        default=None,
        help="Arquivo ou pasta de entrada (relativa ao projeto ou caminho absoluto).",
    )
    parser.add_argument(
        "--saida",
        default=None,
        help="Pasta de saída (relativa ao projeto ou caminho absoluto).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    pasta_in, pasta_out = setup_caminhos(args.entrada, args.saida)
    os.makedirs(pasta_out, exist_ok=True)

    arquivos = []
    if os.path.isfile(pasta_in):
        arquivos = [pasta_in]
    else:
        arquivos = [
            os.path.join(pasta_in, a)
            for a in os.listdir(pasta_in)
            if a.startswith("NER_") and a.endswith(".json") and "_normalizado" not in a
        ]

    print(f"📄 Arquivos encontrados: {len(arquivos)}")

    for path_in in arquivos:
        arq = os.path.basename(path_in)
        path_out = os.path.join(
            pasta_out, arq.replace(".json", "_normalizado.json")
        )

        if os.path.exists(path_out):
            print(f"⏭️  Já normalizado, pulando: {arq}")
            continue

        with open(path_in, "r", encoding="utf-8") as f:
            registros = json.load(f)

        registros_norm = [normalizar_registro(r) for r in registros]

        with open(path_out, "w", encoding="utf-8") as f:
            json.dump(registros_norm, f, ensure_ascii=False, indent=2)

        print(f"✅ Normalizado: {path_out}")