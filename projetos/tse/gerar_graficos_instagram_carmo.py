"""
Gera imagens com gráficos de pizza (Brasil × Carmo/RJ) para post no Instagram.

Uso (na pasta estatisticas/tse):
    python gerar_graficos_instagram_carmo.py

Requer: comparativo_vencedor_mun_58238.csv
        (rode a célula de comparativo no tse3.ipynb antes, se ainda não existir)

Saída: pasta imagens_instagram/
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PASTA = Path(__file__).resolve().parent
ARQUIVO_DADOS = PASTA / "comparativo_vencedor_mun_58238.csv"
PASTA_SAIDA = PASTA / "imagens_instagram"
SEPARADOR = ";"
ENCODING = "latin-1"
NM_MUNICIPIO = "Carmo/RJ"

CORES_PARTIDO = {
    "PSDB": "#0057A8",
    "PT": "#C4122E",
    "PSL": "#009C3B",
    "PL": "#009C3B",
}

COL_PCT_BR = "% de votos do vencedor no Brasil"
COL_PCT_MUN = "% de votos do vencedor no município 58238"

# Reserva: dados do comparativo (Carmo/RJ — CD 58238) se os CSVs não estiverem na pasta
DADOS_FALLBACK = [
    (1994, 1, "PSDB", "FHC", 54.28, 60.16),
    (1998, 1, "PSDB", "FHC", 53.06, 57.44),
    (2002, 1, "PT", "LULA", 46.44, 40.34),
    (2002, 2, "PT", "LULA", 61.27, 64.21),
    (2006, 1, "PT", "LULA", 48.60, 52.45),
    (2006, 2, "PT", "LULA", 60.83, 65.76),
    (2010, 1, "PT", "DILMA", 46.91, 53.71),
    (2010, 2, "PT", "DILMA", 56.05, 61.60),
    (2014, 1, "PT", "DILMA", 41.59, 47.91),
    (2014, 2, "PT", "DILMA", 51.64, 58.35),
    (2018, 1, "PSL", "BOLSONARO", 46.03, 47.67),
    (2018, 2, "PSL", "BOLSONARO", 55.13, 53.34),
    (2022, 1, "PT", "LULA", 48.43, 51.90),
    (2022, 2, "PT", "LULA", 50.90, 54.63),
]


def carregar_dados() -> pd.DataFrame:
    if ARQUIVO_DADOS.exists() and ARQUIVO_DADOS.stat().st_size > 10:
        df = pd.read_csv(ARQUIVO_DADOS, sep=SEPARADOR, encoding=ENCODING)
        if len(df) > 0:
            df["ano"] = df["ano"].astype(int)
            df["turno"] = df["turno"].astype(int)
            return df
    return _montar_dados_de_votos_mun()


def _montar_dados_de_votos_mun(cd_municipio: str = "58238") -> pd.DataFrame:
    """Monta a tabela a partir dos votos_mun_*.csv (mesma lógica do tse3)."""
    votos_invalidos = {"95", "96", "97"}
    partido_fb = {
        (1994, "1", "45"): "PSDB",
        (1998, "1", "45"): "PSDB",
        (2002, "1", "13"): "PT",
        (2002, "2", "13"): "PT",
        (2006, "1", "13"): "PT",
        (2006, "2", "13"): "PT",
        (2010, "1", "13"): "PT",
        (2010, "2", "13"): "PT",
        (2014, "1", "13"): "PT",
        (2014, "2", "13"): "PT",
        (2018, "1", "17"): "PSL",
        (2018, "2", "17"): "PSL",
        (2022, "1", "13"): "PT",
        (2022, "2", "13"): "PT",
    }

    def norm(serie):
        return serie.astype(str).str.strip().str.lstrip("0").replace("", "0")

    def pct_turno(votos, turno):
        val = votos[
            (votos["NR_TURNO"] == str(turno))
            & (~votos["NR_VOTAVEL"].isin(votos_invalidos))
        ]
        totais = val.groupby("NR_VOTAVEL")["QT_VOTOS"].sum()
        if totais.empty or totais.sum() == 0:
            return None, None
        pct = totais / totais.sum() * 100
        return totais.idxmax(), pct

    linhas = []
    arquivos = sorted(
        PASTA.glob("votos_mun_*.csv"),
        key=lambda p: int(p.stem.split("_")[-1]),
    )
    if not arquivos:
        print("  (votos_mun não encontrados — usando tabela embutida)")
        return _dataframe_fallback(cd_municipio)

    col_pct_mun = f"% de votos do vencedor no município {cd_municipio}"
    for arq in arquivos:
        ano = int(arq.stem.split("_")[-1])
        votos = pd.read_csv(arq, sep=SEPARADOR, encoding=ENCODING, dtype=str)
        votos["CD_MUNICIPIO"] = norm(votos["CD_MUNICIPIO"])
        votos["QT_VOTOS"] = pd.to_numeric(votos["QT_VOTOS"], errors="coerce").fillna(0)
        if cd_municipio not in set(votos["CD_MUNICIPIO"]):
            continue
        for turno in sorted(votos["NR_TURNO"].dropna().unique(), key=lambda x: int(x)):
            venc, pct_nac = pct_turno(votos, turno)
            if venc is None:
                continue
            mun = votos[
                (votos["NR_TURNO"] == str(turno))
                & (votos["CD_MUNICIPIO"] == cd_municipio)
                & (~votos["NR_VOTAVEL"].isin(votos_invalidos))
            ]
            total = mun["QT_VOTOS"].sum()
            pv = mun.loc[mun["NR_VOTAVEL"] == venc, "QT_VOTOS"].sum()
            nome = mun.loc[mun["NR_VOTAVEL"] == venc, "NM_VOTAVEL"].iloc[0]
            linhas.append(
                {
                    "ano": ano,
                    "turno": int(turno),
                    "partido do vencedor": partido_fb.get(
                        (ano, str(turno), str(venc)), ""
                    ),
                    "nome do vencedor": nome,
                    COL_PCT_BR: arredondar_pct(float(pct_nac[venc]), 2),
                    col_pct_mun: arredondar_pct(float(pv / total * 100), 2),
                }
            )

    if not linhas:
        return _dataframe_fallback(cd_municipio)
    return pd.DataFrame(linhas)


def _dataframe_fallback(cd_municipio: str = "58238") -> pd.DataFrame:
    col_mun = f"% de votos do vencedor no município {cd_municipio}"
    return pd.DataFrame(
        [
            {
                "ano": ano,
                "turno": turno,
                "partido do vencedor": partido,
                "nome do vencedor": nome,
                COL_PCT_BR: pct_br,
                col_mun: pct_mun,
            }
            for ano, turno, partido, nome, pct_br, pct_mun in DADOS_FALLBACK
        ]
    )


def cor_partido(sigla: str) -> str:
    return CORES_PARTIDO.get(str(sigla).strip().upper(), "#444444")


def arredondar_pct(valor: float, casas: int = 1) -> float:
    """Arredonda com 5 sempre para cima (evita erro de float, ex. 56.05 → 56.1)."""
    q = Decimal("0.1") if casas == 1 else Decimal(f"1e-{casas}")
    return float(Decimal(str(valor)).quantize(q, rounding=ROUND_HALF_UP))


def formatar_pct(valor: float, casas: int = 1) -> str:
    """Percentual com vírgula decimal (ex. 56,1)."""
    arred = arredondar_pct(valor, casas)
    return f"{arred:.{casas}f}".replace(".", ",")


def formatar_diferenca(pct_brasil: float, pct_municipio: float) -> str:
    dif = abs(float(pct_brasil) - float(pct_municipio))
    return f"Diferença {formatar_pct(dif)}%"


def anotar_diferenca_entre_graficos(
    fig, ax_esquerda, ax_direita, pct_brasil: float, pct_municipio: float
) -> None:
    """Texto entre os dois pizzas da mesma linha (Brasil × município)."""
    texto = formatar_diferenca(pct_brasil, pct_municipio)
    pos_e = ax_esquerda.get_position()
    pos_d = ax_direita.get_position()
    x = (pos_e.x1 + pos_d.x0) / 2
    y = (pos_e.y0 + pos_e.y1) / 2
    fig.text(
        x,
        y,
        texto,
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#333333",
    )


def nome_curto(nome: str, max_len: int = 22) -> str:
    nome = str(nome).strip().title()
    if len(nome) <= max_len:
        return nome
    partes = nome.split()
    if len(partes) >= 2:
        return f"{partes[0]} {partes[-1]}"
    return nome[: max_len - 1] + "…"


def desenhar_pizza(ax, pct_vencedor: float, partido: str, nome: str, titulo: str) -> None:
    pct_raw = float(pct_vencedor)
    outros_raw = max(0.0, 100.0 - pct_raw)
    cor = cor_partido(partido)
    nome_exibir = nome_curto(nome, max_len=20)
    tam_fonte = 8 if len(nome_exibir) > 16 else 9

    _, textos = ax.pie(
        [pct_raw, outros_raw],
        labels=[
            f"{nome_exibir}\n{formatar_pct(pct_raw)}%",
            f"Outros\n{formatar_pct(outros_raw)}%",
        ],
        colors=[cor, "#D8D8D8"],
        startangle=90,
        counterclock=False,
        labeldistance=0.58,
        wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
        textprops={"fontsize": tam_fonte, "fontweight": "bold", "ha": "center"},
    )
    textos[0].set_color("white")
    textos[1].set_color("#444444")
    ax.set_title(titulo, fontsize=11, fontweight="bold", pad=8)


def figura_2x2(
    df_ano: pd.DataFrame,
    ano: int,
    caminho: Path,
    *,
    titulo_geral: str | None = None,
) -> None:
    """Quatro pizzas: Brasil/Carmo × 1º/2º turno."""
    turnos = sorted(df_ano["turno"].unique())
    if len(turnos) != 2:
        raise ValueError(f"Ano {ano}: esperados 2 turnos, veio {turnos}")

    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    fig.patch.set_facecolor("#FAFAFA")

    for turno in turnos:
        linha = df_ano[df_ano["turno"] == turno].iloc[0]
        row = 0 if turno == turnos[0] else 1
        for col, local in enumerate(["Brasil", NM_MUNICIPIO]):
            pct = linha[COL_PCT_BR] if local == "Brasil" else linha[COL_PCT_MUN]
            titulo = f"{local} — {turno}º turno"
            desenhar_pizza(
                axes[row, col],
                pct,
                linha["partido do vencedor"],
                linha["nome do vencedor"],
                titulo,
            )
        anotar_diferenca_entre_graficos(
            fig,
            axes[row, 0],
            axes[row, 1],
            linha[COL_PCT_BR],
            linha[COL_PCT_MUN],
        )

    titulo = titulo_geral or f"Eleição presidencial — {ano}"
    fig.suptitle(titulo, fontsize=15, fontweight="bold", y=0.98)
    plt.subplots_adjust(hspace=0.35, wspace=0.28, top=0.90, bottom=0.08)
    fig.savefig(caminho, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  {caminho.name}")


def figura_1994_1998(df: pd.DataFrame, caminho: Path) -> None:
    """Quatro pizzas: 1994 e 1998 (só 1º turno), Brasil e Carmo."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    fig.patch.set_facecolor("#FAFAFA")

    for row, ano in enumerate([1994, 1998]):
        linha = df[(df["ano"] == ano) & (df["turno"] == 1)].iloc[0]
        for col, local in enumerate(["Brasil", NM_MUNICIPIO]):
            pct = linha[COL_PCT_BR] if local == "Brasil" else linha[COL_PCT_MUN]
            titulo = f"{local} — {ano}"
            desenhar_pizza(
                axes[row, col],
                pct,
                linha["partido do vencedor"],
                linha["nome do vencedor"],
                titulo,
            )
        anotar_diferenca_entre_graficos(
            fig,
            axes[row, 0],
            axes[row, 1],
            linha[COL_PCT_BR],
            linha[COL_PCT_MUN],
        )

    fig.suptitle(
        "Eleições presidenciais — 1994 e 1998 (1º turno)",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )
    plt.subplots_adjust(hspace=0.35, wspace=0.28, top=0.90, bottom=0.08)
    fig.savefig(caminho, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  {caminho.name}")


def main() -> None:
    df = carregar_dados()
    PASTA_SAIDA.mkdir(exist_ok=True)

    print(f"Gerando imagens em {PASTA_SAIDA.resolve()} ...")
    print(f"  {len(df)} registros (ano × turno)")

    df94_98 = df[df["ano"].isin([1994, 1998])]
    figura_1994_1998(df94_98, PASTA_SAIDA / "instagram_carmo_1994_1998.png")

    for ano in sorted(df["ano"].unique()):
        if ano in (1994, 1998):
            continue
        df_ano = df[df["ano"] == ano]
        if df_ano["turno"].nunique() != 2:
            print(f"  (pulando {ano}: não tem 2 turnos)")
            continue
        figura_2x2(df_ano, ano, PASTA_SAIDA / f"instagram_carmo_{ano}.png")

    print("\nConcluído.")


if __name__ == "__main__":
    main()
