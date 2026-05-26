import argparse
import json
import os
from typing import Any, Dict, List


def limpar_registro(registro: Dict[str, Any]) -> Dict[str, Any]:
	id_relato = registro.get("id_relato")
	entidades = registro.get("entidades", {})
	relato_original = registro.get("relato_original", "")

	return {
		"id_relato": id_relato,
		"entidades": entidades,
		"relato_original": relato_original,
	}


def limpar_lista(registros: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	return [limpar_registro(r) for r in registros if isinstance(r, dict)]


def executar_limpeza(entrada: str, saida: str) -> None:
	with open(entrada, "r", encoding="utf-8") as arquivo:
		registros = json.load(arquivo)

	if not isinstance(registros, list):
		raise ValueError("JSON de entrada deve ser uma lista de registros.")

	registros_limpos = limpar_lista(registros)

	os.makedirs(os.path.dirname(saida), exist_ok=True)
	with open(saida, "w", encoding="utf-8") as arquivo:
		json.dump(registros_limpos, arquivo, ensure_ascii=False, indent=2)


def executar_exemplo() -> None:
	exemplo = [
		{
			"id_relato": 1,
			"modelo": "qwen3.5:9b",
			"entidades": {"pessoas": [], "empresas": ["ACME"]},
			"relato_original": "Exemplo de relato.",
		},
		{"id_relato": 2, "erro": "timeout", "relato_original": "Outro."},
	]

	print(json.dumps(limpar_lista(exemplo), ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Mantém apenas entidades e relato_original no JSON de extração."
	)
	parser.add_argument("--entrada", help="Caminho do JSON de entrada")
	parser.add_argument("--saida", help="Caminho do JSON de saída")
	parser.add_argument(
		"--exemplo",
		action="store_true",
		help="Executa um exemplo interno e imprime o JSON resultante",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if args.exemplo:
		executar_exemplo()
		return

	if not args.entrada or not args.saida:
		raise SystemExit("Informe --entrada e --saida, ou use --exemplo.")

	executar_limpeza(args.entrada, args.saida)


if __name__ == "__main__":
	main()
