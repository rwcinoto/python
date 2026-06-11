"""
Extrai dados de cursos dos PDFs de notas de corte da FUVEST.

Formato suportado (1994–2002 e 2012–2018):
    código + nome  vagas  inscritos  ausentes  convocados  c/v  máximo  mínimo

O nome do curso ignora o código numérico inicial. candidatos_por_vaga é
calculado como inscritos / vagas (duas casas decimais).

Uso:
    python extrairDados.py
    python extrairDados.py --saida dados.csv --ano-inicio 2012 --ano-fim 2018
"""

from __future__ import annotations

import argparse
import csv
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pypdf import PdfReader

PASTA_PDFS = Path(__file__).resolve().parent / "pdfs"
ARQUIVO_SAIDA_PADRAO = Path(__file__).resolve().parent / "dados_cursos.csv"

# Anos com o mesmo layout de tabela (vagas, inscritos, pontos e c/v por curso).
ANOS_FORMATO_PADRAO = list(range(1994, 2003)) + list(range(2012, 2019))

CAMPOS_CSV = [
    "ano",
    "curso",
    "vagas",
    "inscritos",
    "pontos_minimo",
    "pontos_maximo",
    "candidatos_por_vaga",
]

_RE_INICIO_CURSO = re.compile(r"^(\d+)[\u2212\-\s]*(.*)$")
_RE_PRIMEIRA_LETRA = re.compile(r"[A-Za-zÀ-ÿ]")
_RE_SUFIXO_ASTERISCO = re.compile(r"\s*\(\*\)\s*$")


def normalizar_nome_curso(nome: str) -> str:
    nome = _RE_SUFIXO_ASTERISCO.sub("", nome)
    return nome.strip()


def calcular_candidatos_por_vaga(inscritos: int, vagas: int) -> float:
    """inscritos / vagas com duas casas, arredondamento matemático (0,5 para cima)."""
    return float(
        (Decimal(inscritos) / Decimal(vagas)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def extrair_texto_pdf(caminho: Path) -> str:
    reader = PdfReader(caminho)
    return "\n".join(pagina.extract_text() or "" for pagina in reader.pages)


def parse_linha_curso(linha: str) -> dict[str, object] | None:
    linha = linha.strip()
    if not linha or linha.lower().startswith("total"):
        return None

    match = _RE_INICIO_CURSO.match(linha)
    if not match:
        return None

    resto = match.group(2)
    inicio_nome = _RE_PRIMEIRA_LETRA.search(resto)
    if not inicio_nome:
        return None

    partes = resto[inicio_nome.start() :].split()
    if len(partes) < 8:
        return None

    try:
        vagas, inscritos, _, _, _, pontos_maximo, pontos_minimo = partes[-7:]
        nome = normalizar_nome_curso(" ".join(partes[:-7]))
    except ValueError:
        return None

    try:
        vagas_int = int(vagas)
        inscritos_int = int(inscritos)
        if vagas_int == 0:
            return None
        return {
            "curso": nome,
            "vagas": vagas_int,
            "inscritos": inscritos_int,
            "pontos_minimo": int(pontos_minimo),
            "pontos_maximo": int(pontos_maximo),
            "candidatos_por_vaga": calcular_candidatos_por_vaga(
                inscritos_int, vagas_int
            ),
        }
    except ValueError:
        return None


def extrair_dados_ano(ano: int) -> list[dict[str, object]]:
    caminho = PASTA_PDFS / f"{ano}.pdf"
    if not caminho.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    registros: list[dict[str, object]] = []
    for linha in extrair_texto_pdf(caminho).splitlines():
        curso = parse_linha_curso(linha)
        if curso is None:
            continue
        registros.append({"ano": ano, **curso})

    return registros


def extrair_dados(
    anos: list[int] | None = None,
) -> list[dict[str, object]]:
    anos_processar = anos if anos is not None else ANOS_FORMATO_PADRAO
    dados: list[dict[str, object]] = []

    for ano in anos_processar:
        dados.extend(extrair_dados_ano(ano))

    return dados


def salvar_csv(registros: list[dict[str, object]], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=CAMPOS_CSV)
        writer.writeheader()
        writer.writerows(registros)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai dados de cursos dos PDFs da FUVEST (formato padrão)"
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=ARQUIVO_SAIDA_PADRAO,
        help=f"Arquivo CSV de saída (padrão: {ARQUIVO_SAIDA_PADRAO.name})",
    )
    parser.add_argument("--ano-inicio", type=int, default=min(ANOS_FORMATO_PADRAO))
    parser.add_argument("--ano-fim", type=int, default=max(ANOS_FORMATO_PADRAO))
    args = parser.parse_args()

    anos = [
        ano
        for ano in range(args.ano_inicio, args.ano_fim + 1)
        if ano in ANOS_FORMATO_PADRAO
    ]
    if not anos:
        raise SystemExit(
            "Nenhum ano no intervalo possui o formato padrão suportado "
            f"({min(ANOS_FORMATO_PADRAO)}–{max(ANOS_FORMATO_PADRAO)}, "
            f"exceto 2003–2011)."
        )

    registros: list[dict[str, object]] = []
    for ano in anos:
        dados_ano = extrair_dados_ano(ano)
        print(f"{ano}: {len(dados_ano)} cursos")
        registros.extend(dados_ano)

    salvar_csv(registros, args.saida)
    print()
    print(f"Salvo: {args.saida} ({len(registros)} linhas)")


if __name__ == "__main__":
    main()
