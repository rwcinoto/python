"""
Extrai dados de cursos dos PDFs da FUVEST.

Formatos suportados:
    1994–2002 e 2012–2018 (notas de corte):
        código + nome  vagas  inscritos  ausentes  convocados  c/v  máximo  mínimo
    2003–2011 (inscritos por região + PDF fuvest_{ano}_corte.pdf):
        código + nome  vagas  inscritos  2º incompleto  relação c/v
        (2004 não traz código; só o nome do curso; c/v usa inscritos − incompleto)
        Pontos mínimo e máximo vêm do PDF de corte (mesma ordem dos cursos).
    2019–2026 (por tipo de inscrito):
        1 linha com o curso + 3 linhas (ampla, escola pública, PPI)
        2019–2022: somar vagas e inscritos das 3 linhas; min/máx dos pontos
        2023–2026: vagas e inscritos na linha do curso; min/máx dos pontos nas 3 linhas

O nome do curso ignora o código numérico inicial. Cursos de treinamento
e oficiais da PM são ignorados na extração (não entram no CSV), pois
aparecem em ordens diferentes entre os PDFs de inscritos e de corte.
candidatos_por_vaga é calculado como inscritos / vagas (duas casas
decimais). perc_acertos é
pontos_minimo / total de questões da prova do ano (duas casas decimais).
Nos anos 2003–2011, pontos_minimo, pontos_maximo e perc_acertos vêm do PDF
de corte em pdfs/corte/{ano}.pdf (2003 usa só as 2 primeiras páginas).

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
PASTA_PDFS_CORTE = PASTA_PDFS / "corte"
ARQUIVO_SAIDA_PADRAO = Path(__file__).resolve().parent / "dados_cursos.csv"

# Notas de corte: vagas, inscritos, pontos mínimo e máximo por curso.
ANOS_FORMATO_CORTE = list(range(1994, 2003)) + list(range(2012, 2019))

# Inscritos por região: vagas e inscritos por curso (sem pontos).
ANOS_FORMATO_INSCRITOS = list(range(2003, 2012))

# Notas de corte por tipo de inscrito (4 linhas por curso).
ANOS_FORMATO_POR_TIPO = list(range(2019, 2027))
ANOS_POR_TIPO_CONSOLIDAR = list(range(2019, 2023))
ANOS_POR_TIPO_TOTAL_LINHA = list(range(2023, 2027))

ANOS_SUPORTADOS = sorted(
    set(ANOS_FORMATO_CORTE + ANOS_FORMATO_INSCRITOS + ANOS_FORMATO_POR_TIPO)
)

CAMPOS_CSV = [
    "ano",
    "curso",
    "vagas",
    "inscritos",
    "pontos_minimo",
    "pontos_maximo",
    "candidatos_por_vaga",
    "perc_acertos",
]

# Total de questões da prova objetiva por ano (FUVEST).
QUESTOES_POR_ANO: dict[int, int] = {
    1994: 72,
    1995: 160,
    1996: 160,
    1997: 160,
    1998: 160,
    1999: 160,
    2000: 160,
    2001: 160,
    2002: 160,
    2003: 100,
    2004: 100,
    2005: 100,
    2006: 100,
    2007: 90,
    2008: 90,
    2009: 90,
    2010: 90,
    2011: 90,
    2012: 90,
    2013: 90,
    2014: 90,
    2015: 90,
    2016: 90,
    2017: 90,
    2018: 90,
    2019: 90,
    2020: 90,
    2021: 90,
    2022: 90,
    2023: 90,
    2024: 90,
    2025: 90,
    2026: 90,
}

_RE_INICIO_CURSO = re.compile(r"^(\d+)[\u2212\-\s]*(.*)$")
_RE_LINHA_INSCRITOS_COM_CODIGO = re.compile(r"^(\d+)\s+(.*)$")
_RE_LINHA_INSCRITOS_SEM_CODIGO = re.compile(
    r"^([A-Za-zÀ-ÿ].*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.,]+)\s*$"
)
_RE_PRIMEIRA_LETRA = re.compile(r"[A-Za-zÀ-ÿ]")
_RE_SUFIXO_ASTERISCO = re.compile(r"\s*\(\*\)\s*$")
_RE_LINHA_DETALHE = re.compile(r"^[\u2212\-]\s*(.+)$")

_PREFIXOS_LINHA_IGNORAR = (
    "total",
    "codigo",
    "código",
    "fuvest",
    "relação",
    "inscritos",
    "carreira",
    "pag",
    "copyright",
)

_PREFIXOS_CURSO_IGNORAR = (
    "Treineiro",
    "Treinamento",
    "Treineros",
    "TREINAMENTO",
    "Oficial",
    "OFICIAL",
)


def normalizar_nome_curso(nome: str) -> str:
    nome = _RE_SUFIXO_ASTERISCO.sub("", nome)
    return nome.strip()


def eh_numero(valor: str) -> bool:
    if not valor or not re.search(r"\d", valor):
        return False
    try:
        float(valor.replace(",", "."))
        return True
    except ValueError:
        return False


def parse_inteiro_opcional(valor: str) -> int | None:
    if not eh_numero(valor):
        return None
    return int(valor)


def contar_numericos_finais(partes: list[str]) -> int:
    total = 0
    for parte in reversed(partes):
        if eh_numero(parte):
            total += 1
        else:
            break
    return total


def calcular_candidatos_por_vaga(inscritos: int, vagas: int) -> float:
    """inscritos / vagas com duas casas, arredondamento matemático (0,5 para cima)."""
    return float(
        (Decimal(inscritos) / Decimal(vagas)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def calcular_perc_acertos(pontos_minimo: int | str, ano: int) -> float | str:
    """pontos_minimo / questões da prova do ano, em percentual com duas casas."""
    if pontos_minimo == "" or pontos_minimo is None:
        return ""
    questoes = QUESTOES_POR_ANO.get(ano)
    if questoes is None:
        return ""
    return float(
        (Decimal(int(pontos_minimo)) / Decimal(questoes) * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def montar_registro_ano(ano: int, registro: dict[str, object]) -> dict[str, object]:
    return {
        "ano": ano,
        **registro,
        "perc_acertos": calcular_perc_acertos(registro.get("pontos_minimo", ""), ano),
    }


def extrair_texto_pdf(caminho: Path) -> str:
    reader = PdfReader(caminho)
    return "\n".join(pagina.extract_text() or "" for pagina in reader.pages)


def extrair_texto_corte(ano: int) -> str:
    caminho = PASTA_PDFS_CORTE / f"{ano}.pdf"
    if not caminho.exists():
        raise FileNotFoundError(f"PDF de corte não encontrado: {caminho}")

    reader = PdfReader(caminho)
    paginas = reader.pages[:2] if ano == 2003 else reader.pages
    return "\n".join(pagina.extract_text() or "" for pagina in paginas)


def curso_deve_ignorar(nome: str) -> bool:
    return normalizar_nome_curso(nome).startswith(_PREFIXOS_CURSO_IGNORAR)


def linha_deve_ignorar(linha: str) -> bool:
    linha = linha.strip()
    if not linha:
        return True
    lower = linha.lower()
    if any(lower.startswith(prefixo) for prefixo in _PREFIXOS_LINHA_IGNORAR):
        return True
    return bool(re.match(r"^\d{2}/", linha))


def extrair_incompleto_2004(valor: str) -> int:
    """No PDF de 2004, incompleto vem concatenado ao código do curso (3 dígitos finais)."""
    valor = valor.strip()
    if len(valor) <= 3:
        return int(valor or 0)
    return int(valor[:-3])


def montar_registro(
    nome: str,
    vagas: int,
    inscritos: int,
    *,
    pontos_minimo: int | str = "",
    pontos_maximo: int | str = "",
    inscritos_para_relacao: int | None = None,
) -> dict[str, object] | None:
    nome = normalizar_nome_curso(nome)
    if curso_deve_ignorar(nome) or vagas == 0:
        return None
    base_relacao = inscritos if inscritos_para_relacao is None else inscritos_para_relacao
    return {
        "curso": nome,
        "vagas": vagas,
        "inscritos": inscritos,
        "pontos_minimo": pontos_minimo,
        "pontos_maximo": pontos_maximo,
        "candidatos_por_vaga": calcular_candidatos_por_vaga(base_relacao, vagas),
    }


def parse_linha_corte(linha: str) -> dict[str, object] | None:
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
        nome = " ".join(partes[:-7])
    except ValueError:
        return None

    try:
        return montar_registro(
            nome,
            int(vagas),
            int(inscritos),
            pontos_minimo=int(pontos_minimo),
            pontos_maximo=int(pontos_maximo),
        )
    except ValueError:
        return None


def parse_linha_corte_inscritos_periodo(
    linha: str,
) -> tuple[int | str, int | str] | None:
    """Extrai mínimo e máximo dos convocados (colunas 4 e 5) do PDF de corte."""
    linha = linha.strip()
    if not linha or linha.lower().startswith("total"):
        return None
    if linha_deve_ignorar(linha):
        return None

    match = _RE_INICIO_CURSO.match(linha)
    if not match:
        return None

    resto = match.group(2)
    inicio_nome = _RE_PRIMEIRA_LETRA.search(resto)
    if not inicio_nome:
        return None

    partes = resto[inicio_nome.start() :].split()
    if len(partes) < 5:
        return None

    nome = normalizar_nome_curso(" ".join(partes[:-5]))
    if curso_deve_ignorar(nome):
        return None

    # Colunas finais: convocados, c/v, máximo, pontos possíveis, mínimo
    if not eh_numero(partes[-1]):
        return None
    if not eh_numero(partes[-3]):
        return None

    try:
        pontos_minimo = int(partes[-1])
        pontos_maximo = int(partes[-3])
    except ValueError:
        return None

    return pontos_minimo, pontos_maximo


def parse_linha_inscritos_com_codigo(linha: str) -> dict[str, object] | None:
    linha = linha.strip()
    if linha_deve_ignorar(linha) or linha.lower().startswith("total"):
        return None

    match = _RE_LINHA_INSCRITOS_COM_CODIGO.match(linha)
    if not match:
        return None

    resto = match.group(2)
    inicio_nome = _RE_PRIMEIRA_LETRA.search(resto)
    if not inicio_nome:
        return None

    partes = resto[inicio_nome.start() :].split()
    if len(partes) < 5:
        return None

    try:
        vagas, inscritos, _, _ = partes[-4:]
        nome = " ".join(partes[:-4])
        return montar_registro(nome, int(vagas), int(inscritos))
    except ValueError:
        return None


def extrair_pontos_corte_ano(ano: int) -> list[tuple[int | str, int | str]]:
    pontos: list[tuple[int, int]] = []
    for linha in extrair_texto_corte(ano).splitlines():
        item = parse_linha_corte_inscritos_periodo(linha)
        if item is not None:
            pontos.append(item)
    return pontos


def aplicar_pontos_corte(
    registros: list[dict[str, object]], ano: int
) -> list[dict[str, object]]:
    pontos = extrair_pontos_corte_ano(ano)
    if len(pontos) != len(registros):
        raise ValueError(
            f"{ano}: {len(registros)} cursos no PDF de inscritos, "
            f"mas {len(pontos)} no PDF de corte"
        )

    for registro, (pontos_minimo, pontos_maximo) in zip(registros, pontos, strict=True):
        registro["pontos_minimo"] = pontos_minimo
        registro["pontos_maximo"] = pontos_maximo
        registro["perc_acertos"] = calcular_perc_acertos(pontos_minimo, ano)

    return registros


def parse_linha_detalhe_tipo(linha: str) -> dict[str, int | None] | None:
    linha = linha.strip()
    match = _RE_LINHA_DETALHE.match(linha)
    if not match:
        return None

    partes = match.group(1).split()
    if len(partes) < 8:
        return None

    vagas, inscritos, _, _, _, pontos_maximo, pontos_minimo = partes[-7:]
    vagas_int = parse_inteiro_opcional(vagas)
    inscritos_int = parse_inteiro_opcional(inscritos)
    if vagas_int is None or inscritos_int is None:
        return None

    return {
        "vagas": vagas_int,
        "inscritos": inscritos_int,
        "pontos_maximo": parse_inteiro_opcional(pontos_maximo),
        "pontos_minimo": parse_inteiro_opcional(pontos_minimo),
    }


def parse_linha_cabecalho_curso(linha: str) -> dict[str, object] | None:
    linha = linha.strip()
    if linha_deve_ignorar(linha) or linha.lower() == "total":
        return None

    match = _RE_INICIO_CURSO.match(linha)
    if not match or len(match.group(1)) < 3:
        return None

    resto = match.group(2)
    inicio_nome = _RE_PRIMEIRA_LETRA.search(resto)
    if not inicio_nome:
        return None

    partes = resto[inicio_nome.start() :].split()
    numericos_finais = contar_numericos_finais(partes)
    if numericos_finais > 6:
        return None

    if numericos_finais == 6:
        try:
            vagas, inscritos, _, _, _, pontos_maximo = partes[-6:]
            nome = " ".join(partes[:-6])
            return {
                "nome": normalizar_nome_curso(nome.replace("...", "")),
                "tem_totais": True,
                "vagas": int(vagas),
                "inscritos": int(inscritos),
                "pontos_maximo": int(pontos_maximo),
            }
        except ValueError:
            return None

    nome = normalizar_nome_curso(resto[inicio_nome.start() :].replace("...", ""))
    return {"nome": nome, "tem_totais": False}


def montar_registro_por_tipo(
    nome: str,
    detalhes: list[dict[str, int | None]],
    *,
    consolidar: bool,
    cabecalho: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if len(detalhes) != 3:
        return None

    minimos = [item["pontos_minimo"] for item in detalhes if item["pontos_minimo"] is not None]
    maximos = [item["pontos_maximo"] for item in detalhes if item["pontos_maximo"] is not None]
    if not minimos:
        return None

    if consolidar:
        vagas = sum(item["vagas"] for item in detalhes)
        inscritos = sum(item["inscritos"] for item in detalhes)
        pontos_minimo = min(minimos)
        pontos_maximo = max(maximos) if maximos else min(minimos)
    else:
        if cabecalho is None or not cabecalho.get("tem_totais"):
            return None
        vagas = int(cabecalho["vagas"])
        inscritos = int(cabecalho["inscritos"])
        pontos_minimo = min(minimos)
        pontos_maximo = int(cabecalho["pontos_maximo"])

    return montar_registro(
        nome,
        vagas,
        inscritos,
        pontos_minimo=pontos_minimo,
        pontos_maximo=pontos_maximo,
    )


def extrair_dados_ano_por_tipo(ano: int) -> list[dict[str, object]]:
    consolidar = ano in ANOS_POR_TIPO_CONSOLIDAR
    registros: list[dict[str, object]] = []
    nome_curso: str | None = None
    cabecalho: dict[str, object] | None = None
    detalhes: list[dict[str, int | None]] = []
    apos_total = False

    def reiniciar_bloco() -> None:
        nonlocal nome_curso, cabecalho, detalhes
        nome_curso = None
        cabecalho = None
        detalhes = []

    def finalizar_bloco() -> None:
        nonlocal nome_curso, cabecalho, detalhes
        if nome_curso is None:
            reiniciar_bloco()
            return

        registro = montar_registro_por_tipo(
            nome_curso,
            detalhes,
            consolidar=consolidar,
            cabecalho=cabecalho,
        )
        if registro is not None:
            registros.append(montar_registro_ano(ano, registro))
        reiniciar_bloco()

    for linha in extrair_texto_pdf(PASTA_PDFS / f"{ano}.pdf").splitlines():
        linha = linha.strip()
        if not linha:
            continue

        if linha.lower() == "total":
            finalizar_bloco()
            apos_total = True
            continue

        if apos_total:
            continue

        if linha_deve_ignorar(linha):
            continue

        detalhe = parse_linha_detalhe_tipo(linha)
        if detalhe is not None:
            detalhes.append(detalhe)
            continue

        cabecalho_curso = parse_linha_cabecalho_curso(linha)
        if cabecalho_curso is not None:
            finalizar_bloco()
            nome_curso = str(cabecalho_curso["nome"])
            cabecalho = cabecalho_curso if cabecalho_curso["tem_totais"] else None

    finalizar_bloco()
    return registros


def parse_linha_inscritos_sem_codigo(linha: str) -> dict[str, object] | None:
    linha = linha.strip()
    if linha_deve_ignorar(linha) or linha.lower().startswith("total"):
        return None

    match = _RE_LINHA_INSCRITOS_SEM_CODIGO.match(linha)
    if not match:
        return None

    try:
        nome, vagas, inscritos, incompleto_bruto, _ = match.groups()
        vagas_int = int(vagas)
        inscritos_int = int(inscritos)
        incompleto = extrair_incompleto_2004(incompleto_bruto)
        return montar_registro(
            nome,
            vagas_int,
            inscritos_int,
            inscritos_para_relacao=inscritos_int - incompleto,
        )
    except ValueError:
        return None


def extrair_dados_ano(ano: int) -> list[dict[str, object]]:
    caminho = PASTA_PDFS / f"{ano}.pdf"
    if not caminho.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    if ano in ANOS_FORMATO_POR_TIPO:
        return extrair_dados_ano_por_tipo(ano)

    if ano in ANOS_FORMATO_CORTE:
        parse_linha = parse_linha_corte
    elif ano == 2004:
        parse_linha = parse_linha_inscritos_sem_codigo
    elif ano in ANOS_FORMATO_INSCRITOS:
        parse_linha = parse_linha_inscritos_com_codigo
    else:
        raise ValueError(f"Ano {ano} não possui extrator configurado")

    registros: list[dict[str, object]] = []
    for linha in extrair_texto_pdf(caminho).splitlines():
        curso = parse_linha(linha)
        if curso is None:
            continue
        registros.append(montar_registro_ano(ano, curso))

    if ano in ANOS_FORMATO_INSCRITOS:
        aplicar_pontos_corte(registros, ano)

    return registros


def extrair_dados(
    anos: list[int] | None = None,
) -> list[dict[str, object]]:
    anos_processar = anos if anos is not None else ANOS_SUPORTADOS
    dados: list[dict[str, object]] = []

    for ano in anos_processar:
        dados.extend(extrair_dados_ano(ano))

    return dados


def salvar_csv(registros: list[dict[str, object]], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=CAMPOS_CSV, delimiter=";")
        writer.writeheader()
        writer.writerows(registros)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai dados de cursos dos PDFs da FUVEST"
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=ARQUIVO_SAIDA_PADRAO,
        help=f"Arquivo CSV de saída (padrão: {ARQUIVO_SAIDA_PADRAO.name})",
    )
    parser.add_argument("--ano-inicio", type=int, default=min(ANOS_SUPORTADOS))
    parser.add_argument("--ano-fim", type=int, default=max(ANOS_SUPORTADOS))
    args = parser.parse_args()

    anos = [
        ano
        for ano in range(args.ano_inicio, args.ano_fim + 1)
        if ano in ANOS_SUPORTADOS
    ]
    if not anos:
        raise SystemExit(
            "Nenhum ano no intervalo possui extrator configurado "
            f"({min(ANOS_SUPORTADOS)}–{max(ANOS_SUPORTADOS)})."
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
