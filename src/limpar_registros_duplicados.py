import argparse
import csv
import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple


def _len_relato(row: Dict[str, str]) -> int:
	relato = row.get("relato_historico") or ""
	return len(relato)


def _normalizar_nr_registro(nr_registro: Optional[str]) -> str:
	if not nr_registro:
		return ""
	texto = str(nr_registro).strip()
	if re.match(r"^\d+(\.0+)?$", texto):
		texto = texto.split(".")[0]
	texto = re.sub(r"\D", "", texto)
	if not texto:
		return ""
	return texto.lstrip("0") or "0"


def _extrair_nr_bo_prefixo(relato: str) -> Optional[str]:
	padrao = r"^N do B\.O\.:\s*0*(\d+)"
	correspondencia = re.match(padrao, relato.strip())
	if not correspondencia:
		return None
	return _normalizar_nr_registro(correspondencia.group(1))


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


def remover_prefixo_nr_bo_duplicado(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
	indices: Dict[str, List[Dict[str, str]]] = {}
	for row in rows:
		chave = _normalizar_nr_registro(row.get("nr_registro"))
		indices.setdefault(chave, []).append(row)

	filtrados: List[Dict[str, str]] = []
	for row in rows:
		relato = row.get("relato_historico") or ""
		nr_prefixo = _extrair_nr_bo_prefixo(relato)
		if nr_prefixo:
			possiveis = indices.get(nr_prefixo, [])
			if any(outro is not row for outro in possiveis):
				continue
		filtrados.append(row)

	return filtrados


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


def _extrair_ids_removidos(antes: List[Dict[str, str]], depois: List[Dict[str, str]]) -> List[str]:
	ids_depois = {row.get("id_procedimento") for row in depois}
	removidos = [row.get("id_procedimento") for row in antes if row.get("id_procedimento") not in ids_depois]
	return [identificador for identificador in removidos if identificador]


def salvar_log_ids(removidos: List[str], caminho: str, encoding: str) -> None:
	os.makedirs(os.path.dirname(caminho), exist_ok=True)
	with open(caminho, "w", encoding=encoding) as arquivo:
		for identificador in removidos:
			arquivo.write(f"{identificador}\n")


def executar_deduplicacao(
	entrada: str,
	saida: str,
	delimiter: str,
	encoding: str,
	log: bool = False,
	log_path: Optional[str] = None,
) -> None:
	rows, fieldnames = ler_csv(entrada, delimiter, encoding)
	deduplicados = deduplicar_por_nr_registro(rows)
	sem_prefixo = remover_prefixo_nr_bo_duplicado(deduplicados)
	escrever_csv(saida, sem_prefixo, fieldnames, delimiter, encoding)
	if log and log_path:
		removidos = _extrair_ids_removidos(rows, sem_prefixo)
		salvar_log_ids(removidos, log_path, encoding)


def executar_exemplo() -> None:
	conteudo = (
		"id_procedimento,nr_registro,naturezas,relato_historico,qtd_envolvidos,envolvidos_resumo\n"
		"1,ABC,furto,Relato curto,1,\"A. B.\"\n"
		"2,ABC,furto,Relato bem mais longo com mais detalhes,1,\"A. B.\"\n"
		"4,20264,furto,\"N do B.O.:00140394/2024 --------------------------------------------------------- O comunicante relata que, ...\",1,\"A. B.\"\n"
		"5,140394,furto,\"O comunicante relata que, ...\",1,\"A. B.\"\n"
		"3,XYZ,roubo,Outro relato,2,\"C. D.\"\n"
	)
	with tempfile.TemporaryDirectory() as temp_dir:
		entrada = os.path.join(temp_dir, "entrada.csv")
		saida = os.path.join(temp_dir, "saida.csv")
		with open(entrada, "w", newline="", encoding="utf-8") as arquivo:
			arquivo.write(conteudo)
		log_path = os.path.join(temp_dir, "log_ids_removidos.txt")
		executar_deduplicacao(entrada, saida, ",", "utf-8", log=True, log_path=log_path)
		with open(saida, "r", encoding="utf-8") as arquivo:
			print(arquivo.read())
		with open(log_path, "r", encoding="utf-8") as arquivo:
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
	parser.add_argument(
		"--log",
		action="store_true",
		help="Salva em .txt os id_procedimento removidos",
	)
	parser.add_argument(
		"--lpath",
		default="logs/log.txt",
		help="Caminho do log de ids removidos (usado com --log)",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if args.exemplo:
		executar_exemplo()
		return

	if not args.entrada or not args.saida:
		raise SystemExit("Informe --entrada e --saida, ou use --exemplo.")

	executar_deduplicacao(
		args.entrada,
		args.saida,
		args.delimiter,
		args.encoding,
		log=args.log,
		log_path=args.lpath,
	)


if __name__ == "__main__":
	main()
