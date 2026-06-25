"""
Baixa os PDFs de notas de corte / relação candidato-vaga da FUVEST.

Uso:
    python baixar_pdfs.py
    python baixar_pdfs.py --ano-inicio 2010 --ano-fim 2026
    python baixar_pdfs.py --corte
    python baixar_pdfs.py --corte --ano-inicio 2005 --ano-fim 2008
"""

from __future__ import annotations

import argparse
import io
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from pypdf import PdfReader, PdfWriter

BASE_URL = "https://www.fuvest.br/wp-content/uploads/"
PASTA_PDFS = Path(__file__).resolve().parent / "pdfs"
PASTA_PDFS_CORTE = PASTA_PDFS / "corte"

# 2003–2011: PDF separado com notas de corte (pontos mínimo e máximo).
ANOS_CORTE = list(range(2003, 2012))

# 2003–2011: PDF de inscritos por região; só as últimas páginas têm C/V por curso.
FONTES_INSCRITOS_REGIAO: dict[int, int] = {
    **dict.fromkeys(range(2003, 2008), 2),
    **dict.fromkeys(range(2008, 2012), 3),
}

# Anos com nome de arquivo conhecido (descobertos por varredura no site).
ARQUIVOS_CONHECIDOS: dict[int, str] = {
    2018: "fuv2018_corte.pdf",
    2019: "fuvest_2019_notas_de_corte.pdf",
    2020: "fuvest_2020_nota_de_corte.pdf",  # singular: nota_de_corte
    2021: "fuvest_2021_notas_primeira_fase.pdf",
    2022: "fuvest_2022_notas_de_corte.pdf",
    2023: "fuvest2023_notas_de_corte.pdf",
    2024: "fuvest_2024_notas_de_corte.pdf",
    2025: "fuvest_2025_notas_de_corte.pdf",
    2026: "fuvest2026_notas_de_corte.pdf",
}


def nome_inscritos_por_regiao(ano: int) -> str:
    return f"fuvest_{ano}_inscritos_por_regiao.pdf"


def nome_arquivo_corte(ano: int) -> str:
    return f"fuvest_{ano}_corte.pdf"


def url_corte(ano: int) -> str:
    return BASE_URL + nome_arquivo_corte(ano)


def candidatos_por_ano(ano: int) -> list[str]:
    if ano in FONTES_INSCRITOS_REGIAO:
        return [nome_inscritos_por_regiao(ano)]

    if ano in ARQUIVOS_CONHECIDOS:
        return [ARQUIVOS_CONHECIDOS[ano]]

    y2 = str(ano)[-2:]
    y4 = str(ano)
    return [
        f"fuvest_{y4}_corte.pdf",
        f"fuvest_{y4}_notas_de_corte.pdf",
        f"fuvest{y4}_notas_de_corte.pdf",
        f"fuvest{y4}_corte.pdf",
        f"fuv{y2}_corte.pdf",
        f"fuvest_{y4}_nota_de_corte.pdf",
        f"fuvest{y4}_relacao_candidato_vaga.pdf",
    ]


def url_existe(url: str, ctx: ssl.SSLContext) -> bool:
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "Mozilla/5.0 (estudo pessoal)"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 405):
            req = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": "Mozilla/5.0 (estudo pessoal)"},
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=15):
                    return True
            except urllib.error.HTTPError:
                return False
        return False
    except urllib.error.URLError:
        return False


def baixar_bytes(url: str, ctx: ssl.SSLContext) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (estudo pessoal)"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        return resp.read()


def salvar_ultimas_paginas(conteudo: bytes, destino: Path, ultimas_paginas: int) -> None:
    reader = PdfReader(io.BytesIO(conteudo))
    total = len(reader.pages)
    if ultimas_paginas > total:
        raise ValueError(
            f"PDF tem {total} página(s), mas foram pedidas {ultimas_paginas} do final"
        )

    writer = PdfWriter()
    for pagina in reader.pages[total - ultimas_paginas :]:
        writer.add_page(pagina)

    with destino.open("wb") as f:
        writer.write(f)


def resolver_arquivo(ano: int, ctx: ssl.SSLContext) -> tuple[str | None, str | None]:
    for nome in candidatos_por_ano(ano):
        url = BASE_URL + nome
        if url_existe(url, ctx):
            return nome, url
        time.sleep(0.15)
    return None, None


def baixar_pdfs_corte(
    ano_inicio: int,
    ano_fim: int,
    *,
    forcar: bool,
    ctx: ssl.SSLContext,
) -> None:
    """Baixa fuvest_{ano}_corte.pdf (2003–2011) para pdfs/corte/{ano}.pdf."""
    PASTA_PDFS_CORTE.mkdir(parents=True, exist_ok=True)

    anos = [
        ano
        for ano in range(ano_inicio, ano_fim + 1)
        if ano in ANOS_CORTE
    ]
    if not anos:
        raise SystemExit(
            "Nenhum ano no intervalo possui PDF de corte separado (2003–2011)."
        )

    encontrados = 0
    falhas: list[int] = []

    for ano in anos:
        destino = PASTA_PDFS_CORTE / f"{ano}.pdf"
        if destino.exists() and not forcar:
            print(f"{ano}: já existe em corte/{destino.name}, pulando")
            encontrados += 1
            continue

        url = url_corte(ano)
        nome = nome_arquivo_corte(ano)
        if not url_existe(url, ctx):
            print(f"{ano}: {nome} não encontrado")
            falhas.append(ano)
            continue

        print(f"{ano}: baixando {nome}...")
        destino.write_bytes(baixar_bytes(url, ctx))
        print(f"{ano}: salvo em corte/{destino.name}")
        encontrados += 1
        time.sleep(0.3)

    total = len(anos)
    print()
    print(f"Concluído: {encontrados}/{total} anos com arquivo de corte local")
    if falhas:
        print(f"Anos não encontrados: {', '.join(map(str, falhas))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa PDFs de corte da FUVEST")
    parser.add_argument("--ano-inicio", type=int, default=1994)
    parser.add_argument("--ano-fim", type=int, default=2026)
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Baixa novamente mesmo se o arquivo local já existir",
    )
    parser.add_argument(
        "--corte",
        action="store_true",
        help="Baixa PDFs de notas de corte de 2003 a 2011 (pdfs/corte/)",
    )
    args = parser.parse_args()

    ctx = ssl.create_default_context()

    if args.corte:
        baixar_pdfs_corte(
            args.ano_inicio,
            args.ano_fim,
            forcar=args.forcar,
            ctx=ctx,
        )
        return

    PASTA_PDFS.mkdir(parents=True, exist_ok=True)

    encontrados = 0
    falhas: list[int] = []

    for ano in range(args.ano_inicio, args.ano_fim + 1):
        destino = PASTA_PDFS / f"{ano}.pdf"
        if destino.exists() and not args.forcar:
            print(f"{ano}: já existe em {destino.name}, pulando")
            encontrados += 1
            continue

        nome, url = resolver_arquivo(ano, ctx)
        if not url:
            print(f"{ano}: não encontrado (tente confirmar manualmente no acervo)")
            falhas.append(ano)
            continue

        ultimas_paginas = FONTES_INSCRITOS_REGIAO.get(ano)
        if ultimas_paginas:
            print(
                f"{ano}: baixando {nome} "
                f"(salvando {ultimas_paginas} última(s) página(s))..."
            )
            conteudo = baixar_bytes(url, ctx)
            salvar_ultimas_paginas(conteudo, destino, ultimas_paginas)
        else:
            print(f"{ano}: baixando {nome}...")
            destino.write_bytes(baixar_bytes(url, ctx))

        print(f"{ano}: salvo em {destino}")
        encontrados += 1
        time.sleep(0.3)

    total = args.ano_fim - args.ano_inicio + 1
    print()
    print(f"Concluído: {encontrados}/{total} anos com arquivo local")
    if falhas:
        print(f"Anos não encontrados: {', '.join(map(str, falhas))}")


if __name__ == "__main__":
    main()
