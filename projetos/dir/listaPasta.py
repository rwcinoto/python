import os, csv

tamanhos_pastas = {}
for root, dirs, files in os.walk("C:\\", topdown=False):
    tamanho = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f)))
    if tamanho > 10000000:
        tamanhos_pastas[root] = tamanho
linhas = sorted([{"caminho": c, "tam_bytes": t} for c, t in tamanhos_pastas.items()],
                key=lambda x: x["tam_bytes"], reverse=True)
with open(f"pastasTam.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.DictWriter(f, fieldnames=["caminho", "tam_bytes"], delimiter=";").writerows(linhas)
