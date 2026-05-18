# Passo a passo do projeto
# Passo 1: Entrar no sistema da empresa manualmente e deixar o naegador ativo
import pyautogui
import time
time.sleep(5)

# Passo 2: Importar a base de pedidos
import pandas as pd
tabela = pd.read_csv("iso.csv")

# Passo 3: visitar cada pedido
for linha in tabela.index:
    # pegar da tabelo o id do pedido
    codigo = tabela.loc[linha, "id"]
    # ir para a barra de endereços
    pyautogui.hotkey("ctrl", "l")
    # acessar url do pedido
    pyautogui.write(f"https://portal.bellocopo.com.br/pedidosIsoforma/view/{codigo}")
    pyautogui.press("enter")
    # esperar o pedido carregar
    time.sleep(5)
    # Passo 4: Repetir o processo de acessar cada pedido até o fim
