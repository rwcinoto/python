"""
Script simples para baixar vídeo do YouTube com yt-dlp.

Antes de rodar, edite:
1) VIDEO_URL (link do vídeo)
2) PASTA_DESTINO (onde o arquivo será salvo)
"""

from pathlib import Path

import yt_dlp

# Cole aqui a URL do vídeo que você quer baixar.
VIDEO_URL = "https://www.youtube.com/watch?v=cpybv9c6x1k"

# Defina aqui a pasta onde o vídeo será salvo.
# Exemplo no Windows: r"D:\Downloads\videos"
PASTA_DESTINO = r"D:\cursos\python"

def baixar_video(url: str, pasta_destino: str) -> None:
    """
    Baixa o vídeo na melhor qualidade disponível.
    """
    destino = Path(pasta_destino)
    destino.mkdir(parents=True, exist_ok=True)

    opcoes = {
        # Formato único (vídeo+áudio juntos), para funcionar sem ffmpeg.
        # Tenta MP4 primeiro, depois qualquer melhor formato único.
        "format": "best[ext=mp4]/best",
        # Nome final do arquivo: titulo.extensao
        "outtmpl": str(destino / "%(title)s.%(ext)s"),
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        ydl.download([url])

if __name__ == "__main__":
    if "SEU_ID_AQUI" in VIDEO_URL:
        print("Edite a variável VIDEO_URL com o link do vídeo antes de executar.")
    else:
        baixar_video(VIDEO_URL, PASTA_DESTINO)
        print("Download concluído.")
