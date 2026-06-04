import os, csv

def salvar_csv(tipo, dados):
    linhas = sorted([{"caminho": c, "tam_bytes": t} for c, t in dados.items()],
                    key=lambda x: x["tam_bytes"], reverse=True)
    with open(f"{tipo}Tam.csv", "w", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=["caminho", "tam_bytes"], delimiter=";").writerows(linhas)

MIN_TAM, tamanhos_pastas, tamanhos_arquivos = 10000000, {}, {}

for root, dirs, files in os.walk("C:\\", topdown=False):
    if tamanho := sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f))):
        if tamanho > MIN_TAM:
            tamanhos_pastas[root] = tamanho

    for f in files:
        if os.path.exists(caminho := os.path.join(root, f)) and (tamanho := os.path.getsize(caminho)) > MIN_TAM:
            tamanhos_arquivos[caminho] = tamanho

salvar_csv("pastas", tamanhos_pastas); salvar_csv("arq", tamanhos_arquivos)
