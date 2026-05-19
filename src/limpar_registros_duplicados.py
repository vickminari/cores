import argparse
import csv
import os
import tempfile
from typing import Dict, List, Tuple


def _len_relato(row: Dict[str, str]) -> int:
	relato = row.get("relato_historico") or ""
	return len(relato)


def deduplicar_por_nr_registro(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
	selecionados: Dict[str, Tuple[int, Dict[str, str]]] = {}
	ordem: List[str] = []
	for row in rows:
		chave = row.get("nr_registro") or ""
		if chave not in selecionados:
			selecionados[chave] = (_len_relato(row), row)
			ordem.append(chave)
			continue

		tamanho_atual = _len_relato(row)
		tamanho_escolhido, _ = selecionados[chave]
		if tamanho_atual > tamanho_escolhido:
			selecionados[chave] = (tamanho_atual, row)

	return [selecionados[chave][1] for chave in ordem]


def ler_csv(entrada: str, delimiter: str, encoding: str) -> Tuple[List[Dict[str, str]], List[str]]:
	with open(entrada, "r", newline="", encoding=encoding) as arquivo:
		leitor = csv.DictReader(arquivo, delimiter=delimiter)
		if leitor.fieldnames is None:
			raise ValueError("CSV sem cabeçalho.")
		rows = list(leitor)
		return rows, list(leitor.fieldnames)


def escrever_csv(saida: str, rows: List[Dict[str, str]], fieldnames: List[str], delimiter: str, encoding: str) -> None:
	with open(saida, "w", newline="", encoding=encoding) as arquivo:
		escritor = csv.DictWriter(arquivo, fieldnames=fieldnames, delimiter=delimiter)
		escritor.writeheader()
		escritor.writerows(rows)


def executar_deduplicacao(entrada: str, saida: str, delimiter: str, encoding: str) -> None:
	rows, fieldnames = ler_csv(entrada, delimiter, encoding)
	deduplicados = deduplicar_por_nr_registro(rows)
	escrever_csv(saida, deduplicados, fieldnames, delimiter, encoding)


def executar_exemplo() -> None:
	conteudo = (
		"id_procedimento,nr_registro,naturezas,relato_historico,qtd_envolvidos,envolvidos_resumo\n"
		"1,ABC,furto,Relato curto,1,\"A. B.\"\n"
		"2,ABC,furto,Relato bem mais longo com mais detalhes,1,\"A. B.\"\n"
		"3,XYZ,roubo,Outro relato,2,\"C. D.\"\n"
	)
	with tempfile.TemporaryDirectory() as temp_dir:
		entrada = os.path.join(temp_dir, "entrada.csv")
		saida = os.path.join(temp_dir, "saida.csv")
		with open(entrada, "w", newline="", encoding="utf-8") as arquivo:
			arquivo.write(conteudo)
		executar_deduplicacao(entrada, saida, ",", "utf-8")
		with open(saida, "r", encoding="utf-8") as arquivo:
			print(arquivo.read())


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Remove linhas com mesmo nr_registro mantendo o maior relato_historico."
	)
	parser.add_argument("--entrada", help="Caminho do CSV de entrada")
	parser.add_argument("--saida", help="Caminho do CSV de saída")
	parser.add_argument("--delimiter", default=",", help="Delimitador do CSV")
	parser.add_argument("--encoding", default="utf-8", help="Encoding do CSV")
	parser.add_argument(
		"--exemplo",
		action="store_true",
		help="Executa um exemplo interno e imprime o CSV resultante",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if args.exemplo:
		executar_exemplo()
		return

	if not args.entrada or not args.saida:
		raise SystemExit("Informe --entrada e --saida, ou use --exemplo.")

	executar_deduplicacao(args.entrada, args.saida, args.delimiter, args.encoding)


if __name__ == "__main__":
	main()
