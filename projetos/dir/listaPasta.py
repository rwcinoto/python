import os, csv

tamanhos = {}
for root, dirs, files in os.walk(f"C:\\", topdown=False):
    tamanho = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f)))
    tamanhos[root] = tamanho
linhas = [{"caminho": c, "tam_bytes": t} for c, t in tamanhos.items() if t > 10000000]
linhas.sort(key=lambda x: x["tam_bytes"], reverse=True)
with open(f"pastasTam.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["caminho", "tam_bytes"], delimiter=";")
    writer.writeheader()
    writer.writerows(linhas)
