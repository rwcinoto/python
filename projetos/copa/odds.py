import requests
import pandas as pd
from datetime import datetime

# CONFIGURAÇÕES
API_KEY = 'COLOQUE AQUI A SUA CHAVE DA API'
SPORT = 'soccer_fifa_world_cup'
REGION = 'eu' # Você pode usar 'us', 'uk', 'eu' ou 'au'
MARKET = 'h2h' # Odds de Vitória/Empate/Vitória (Mercado principal de cada jogo)
# pegar odds de todas as partidas da copa do mundo 2026 do site https://the-odds-api.com/

def buscar_odds_partidas():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds/'
    params = {
        'apiKey': API_KEY,
        'regions': REGION,
        'markets': MARKET,
        'oddsFormat': 'decimal'
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"Erro: {response.status_code}")
        return

    data = response.json()
    jogos_lista = []

    for jogo in data:
        home_team = jogo['home_team']
        away_team = jogo['away_team']
        start_time = jogo['commence_time']

        # Vamos pegar as odds da primeira casa de aposta disponível na lista
        if jogo['bookmakers']:
            bookmaker = jogo['bookmakers'][0] # Ex: Bet365, Pinnacle, etc.
            market_data = bookmaker['markets'][0]

            odds = {outcome['name']: outcome['price'] for outcome in market_data['outcomes']}

            # Cálculo de probabilidade implícita (opcional, mas bom para ver favoritismo)
            # Probabilidade = (1 / Odd) * 100
            prob_home = round((1 / odds.get(home_team, 1)) * 100, 2)
            prob_away = round((1 / odds.get(away_team, 1)) * 100, 2)
            prob_draw = round((1 / odds.get('Draw', 1)) * 100, 2)

            jogos_lista.append({
                'Data/Hora (UTC)': start_time,
                'Mandante': home_team,
                'Visitante': away_team,
                'Odd Mandante': odds.get(home_team),
                'Odd Empate': odds.get('Draw'),
                'Odd Visitante': odds.get(away_team),
                '% Favoritismo Mandante': prob_home,
                '% Favoritismo Visitante': prob_away,
                'Casa de Aposta': bookmaker['title']
            })

    # Criar DataFrame
    df = pd.DataFrame(jogos_lista)

    # Ordenar por data
    df = df.sort_values(by='Data/Hora (UTC)')

    # Salvar em CSV
    df.to_csv('jogos_fase_de_grupos_2026.csv', index=False, encoding='utf-8-sig')
    print("Arquivo 'jogos_fase_de_grupos_2026.csv' gerado!")
    print(df.head()) # Preview das primeiras partidas

if __name__ == "__main__":
    buscar_odds_partidas()