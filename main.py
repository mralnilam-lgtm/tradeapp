#!/usr/bin/env python3
"""
ANÁLISE TÉCNICA + FUNDAMENTALISTA (TRADIER + FINNHUB + ALPHA VANTAGE + FMP + NEWSAPI + CLAUDE)
Versão estável — com NewsAPI integrado para mais notícias.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic

# ================= CONFIGURAÇÃO =================
load_dotenv()

TRADIER_KEY = os.getenv("TRADIER_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY")
FMP_KEY = os.getenv("FMP_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # ✅ ADICIONADO
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ================= CORES ANSI =================
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"


# ================= FUNÇÕES AUXILIARES =================
def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def print_header(text, color=CYAN):
    """Imprime cabeçalho bonito"""
    print(f"\n{BOLD}{color}{'═'*100}{RESET}")
    print(f"{BOLD}{color}{text.center(100)}{RESET}")
    print(f"{BOLD}{color}{'═'*100}{RESET}")


def print_section(text, color=BLUE):
    """Imprime seção bonita"""
    print(f"\n{BOLD}{color}┌{'─'*98}┐{RESET}")
    print(f"{BOLD}{color}│  {text.ljust(96)}│{RESET}")
    print(f"{BOLD}{color}└{'─'*98}┘{RESET}")


def print_box(text, color=GREEN):
    """Imprime caixa destacada"""
    print(f"\n{BOLD}{color}╔{'═'*98}╗{RESET}")
    print(f"{BOLD}{color}║  {text.ljust(96)}║{RESET}")
    print(f"{BOLD}{color}╚{'═'*98}╝{RESET}")


def print_separator():
    """Imprime separador"""
    print(f"{BOLD}{CYAN}{'─'*100}{RESET}")


def limpar_markdown(texto):
    """Remove formatação markdown do texto"""
    import re
    # Remove asteriscos de negrito e itálico
    texto = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', texto)  # ***texto***
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)      # **texto**
    texto = re.sub(r'\*(.+?)\*', r'\1', texto)          # *texto*
    texto = re.sub(r'__(.+?)__', r'\1', texto)          # __texto__
    texto = re.sub(r'_(.+?)_', r'\1', texto)            # _texto_
    # Remove hashtags de títulos mas mantém o texto
    texto = re.sub(r'^#{1,6}\s+', '', texto, flags=re.MULTILINE)
    return texto


# ================= DADOS TÉCNICOS =================
def get_candles_finnhub(symbol, days=180):
    """Candles diários via Finnhub."""
    end = int(time.time())
    start = int((datetime.now() - timedelta(days=days)).timestamp())
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": symbol, "resolution": "D", "from": start, "to": end, "token": FINNHUB_KEY}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get("s") == "ok":
        df = pd.DataFrame({
            "date": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"]
        })
        return df
    return None


def get_sma_alpha(symbol, period=20):
    """SMA via Alpha Vantage (backup)."""
    if not ALPHA_KEY:
        return None
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "SMA",
            "symbol": symbol,
            "interval": "daily",
            "time_period": period,
            "series_type": "close",
            "apikey": ALPHA_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json().get("Technical Analysis: SMA", {})
        values = [safe_float(v["SMA"]) for v in data.values()]
        return values[-1] if values else None
    except:
        return None


def obter_dados_tecnicos(ticker):
    """Combina Tradier (tempo real) + Finnhub (candles) + Alpha Vantage (backup SMA)."""
    dados = {"ticker": ticker.upper(), "fonte": None}

    print(f"\n{CYAN}🔍 Buscando dados técnicos de {BOLD}{ticker}{RESET}{CYAN}...{RESET}")

    # --- Tradier tempo real ---
    if TRADIER_KEY:
        try:
            headers = {"Authorization": f"Bearer {TRADIER_KEY}", "Accept": "application/json"}
            url = "https://api.tradier.com/v1/markets/quotes"
            r = requests.get(url, headers=headers, params={"symbols": ticker}, timeout=10)
            if r.status_code == 200:
                q = r.json().get("quotes", {}).get("quote", {})
                if q and q.get("last") is not None:
                    preco = safe_float(q.get("last"))
                    variacao = safe_float(q.get("change_percentage"))
                    var_color = GREEN if variacao >= 0 else RED
                    
                    dados.update({
                        "preco": preco,
                        "variacao": variacao,
                        "volume": safe_int(q.get("volume")),
                        "abertura": safe_float(q.get("open")),
                        "alta": safe_float(q.get("high")),
                        "baixa": safe_float(q.get("low")),
                        "fechamento_anterior": safe_float(q.get("prevclose")),
                        "moeda": "USD",
                        "fonte": "Tradier (tempo real)"
                    })
                    print(f"{GREEN}✅ Tradier: {BOLD}{ticker}{RESET} {CYAN}${preco:.2f}{RESET} ({var_color}{variacao:+.2f}%{RESET})")
        except Exception as e:
            print(f"{YELLOW}⚠️  Tradier falhou: {e}{RESET}")

    # --- Finnhub candles para indicadores ---
    try:
        hist = get_candles_finnhub(ticker)
        if hist is not None and len(hist) > 20:
            dados["sma_20"] = hist["close"].rolling(20).mean().iloc[-1]
            dados["sma_50"] = hist["close"].rolling(50).mean().iloc[-1] if len(hist) >= 50 else dados["sma_20"]
            delta = hist["close"].diff()
            ganho = (delta.where(delta > 0, 0)).rolling(14).mean()
            perda = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = ganho / perda
            dados["rsi"] = 100 - (100 / (1 + rs.iloc[-1])) if perda.iloc[-1] > 0 else 50
            dados["minimo_52w"] = float(hist["low"].min())
            dados["maximo_52w"] = float(hist["high"].max())
            print(f"{GREEN}✅ Indicadores técnicos calculados{RESET}")
        else:
            print(f"{YELLOW}⚠️  Finnhub sem dados — tentando Alpha Vantage{RESET}")
            sma20 = get_sma_alpha(ticker, 20)
            sma50 = get_sma_alpha(ticker, 50)
            dados["sma_20"] = sma20 or dados.get("preco", 0.0)
            dados["sma_50"] = sma50 or dados.get("preco", 0.0)
            dados["rsi"] = 50.0
            dados["minimo_52w"] = dados.get("baixa", 0.0)
            dados["maximo_52w"] = dados.get("alta", 0.0)
    except Exception as e:
        print(f"{YELLOW}⚠️  Falha indicadores: {e}{RESET}")
        dados["sma_20"] = dados.get("preco", 0.0)
        dados["sma_50"] = dados.get("preco", 0.0)
        dados["rsi"] = 50.0

    if not dados.get("preco"):
        print(f"{RED}❌ Sem dados válidos de preço{RESET}")
        return None

    return dados


# ================= FUNDAMENTOS =================
def obter_dados_fundamentalistas(ticker):
    print(f"\n{CYAN}📊 Buscando fundamentos de {BOLD}{ticker}{RESET}{CYAN}...{RESET}")
    fundamentos = {}

    # Finnhub
    if FINNHUB_KEY:
        try:
            url = "https://finnhub.io/api/v1/stock/metric"
            params = {"symbol": ticker, "metric": "all", "token": FINNHUB_KEY}
            r = requests.get(url, params=params, timeout=10)
            data = r.json().get("metric", {})
            if data:
                fundamentos.update({
                    "pe_ratio": data.get("peBasicExclExtraTTM"),
                    "pb_ratio": data.get("pbQuarterly"),
                    "roe": data.get("roeTTM"),
                    "roa": data.get("roaTTM"),
                    "net_margin": data.get("netProfitMarginTTM"),
                    "debt_to_equity": data.get("totalDebt/totalEquityQuarterly"),
                    "revenue_growth": data.get("revenueGrowthTTMYoy"),
                    "fonte_fundamental": "Finnhub"
                })
                print(f"{GREEN}✅ Finnhub: fundamentos carregados{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠️  Finnhub fundamentos: {e}{RESET}")

    # FMP (backup)
    if FMP_KEY and not fundamentos:
        try:
            url = f"https://financialmodelingprep.com/api/v3/ratios/{ticker}"
            params = {"apikey": FMP_KEY}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if data and len(data) > 0:
                d = data[0]
                fundamentos.update({
                    "pe_ratio": d.get("priceEarningsRatio"),
                    "pb_ratio": d.get("priceToBookRatio"),
                    "roe": d.get("returnOnEquity"),
                    "roa": d.get("returnOnAssets"),
                    "net_margin": d.get("netProfitMargin"),
                    "debt_to_equity": d.get("debtEquityRatio"),
                    "revenue_growth": None,
                    "fonte_fundamental": "FMP"
                })
                print(f"{GREEN}✅ FMP: fundamentos carregados{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠️  FMP fundamentos: {e}{RESET}")

    # Calcular score
    score = 50
    if safe_float(fundamentos.get("pe_ratio")) > 0:
        pe = safe_float(fundamentos.get("pe_ratio"))
        if pe < 15:
            score += 10
        elif pe > 30:
            score -= 10
    if safe_float(fundamentos.get("roe")) > 15:
        score += 15
    elif safe_float(fundamentos.get("roe")) < 5:
        score -= 10
    if safe_float(fundamentos.get("net_margin")) > 15:
        score += 10
    if safe_float(fundamentos.get("debt_to_equity")) < 1:
        score += 10
    if safe_float(fundamentos.get("revenue_growth")) > 0.1:
        score += 10

    fundamentos["score_fundamental"] = max(0, min(100, score))
    
    if score >= 70:
        fundamentos["avaliacao"] = "excelente"
        fundamentos["cor_avaliacao"] = GREEN
    elif score >= 50:
        fundamentos["avaliacao"] = "bom"
        fundamentos["cor_avaliacao"] = YELLOW
    else:
        fundamentos["avaliacao"] = "fraco"
        fundamentos["cor_avaliacao"] = RED

    return fundamentos


# ================= NOTÍCIAS =================
def obter_noticias_finnhub(ticker):
    """Busca últimas notícias via Finnhub."""
    if not FINNHUB_KEY:
        return []
    try:
        url = "https://finnhub.io/api/v1/company-news"
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        params = {"symbol": ticker, "from": from_date, "to": to_date, "token": FINNHUB_KEY}
        r = requests.get(url, params=params, timeout=10)
        noticias = r.json()[:5]  # Últimas 5
        print(f"{GREEN}✅ Finnhub: {len(noticias)} notícias encontradas{RESET}")
        return noticias
    except Exception as e:
        print(f"{YELLOW}⚠️  Finnhub notícias: {e}{RESET}")
        return []


def obter_noticias_newsapi(ticker):
    """Busca notícias via NewsAPI."""
    if not NEWSAPI_KEY:
        return []
    try:
        # NewsAPI busca por query (nome da empresa ou ticker)
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": ticker,
            "apiKey": NEWSAPI_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        
        if data.get("status") == "ok":
            articles = data.get("articles", [])
            print(f"{GREEN}✅ NewsAPI: {len(articles)} notícias encontradas{RESET}")
            
            # Converter para formato similar ao Finnhub
            noticias = []
            for article in articles:
                noticias.append({
                    "headline": article.get("title", "N/A"),
                    "datetime": article.get("publishedAt", "N/A"),
                    "source": article.get("source", {}).get("name", "NewsAPI"),
                    "url": article.get("url", "")
                })
            return noticias
        else:
            print(f"{YELLOW}⚠️  NewsAPI: {data.get('message', 'Erro desconhecido')}{RESET}")
            return []
    except Exception as e:
        print(f"{YELLOW}⚠️  NewsAPI notícias: {e}{RESET}")
        return []


def obter_noticias(ticker):
    """Combina notícias de Finnhub + NewsAPI."""
    print(f"\n{CYAN}📰 Buscando notícias de {BOLD}{ticker}{RESET}{CYAN}...{RESET}")
    
    noticias_finnhub = obter_noticias_finnhub(ticker)
    noticias_newsapi = obter_noticias_newsapi(ticker)
    
    # Combinar e remover duplicatas
    todas_noticias = noticias_finnhub + noticias_newsapi
    
    # Limitar a 10 notícias mais recentes
    todas_noticias = todas_noticias[:10]
    
    print(f"{CYAN}📊 Total: {len(todas_noticias)} notícias coletadas{RESET}")
    
    return todas_noticias


# ================= ANÁLISE IA =================
def gerar_analise_ai(ticker, dados, fundamentos, valor):
    if not client:
        print(f"{RED}❌ Claude API não configurada{RESET}")
        return None

    print(f"\n{CYAN}🤖 Gerando análise com Claude AI...{RESET}")

    # Obter notícias
    noticias = obter_noticias(ticker)
    if noticias:
        noticias_texto = "\n".join([
            f"- {n.get('headline', 'N/A')} ({n.get('datetime', 'N/A')}) [Fonte: {n.get('source', 'N/A')}]" 
            for n in noticias
        ])
    else:
        noticias_texto = "Nenhuma notícia recente disponível."

    prompt = f"""Analise a ação {ticker} com base nos dados:

COTAÇÃO ATUAL:
- Preço: ${dados['preco']:.2f}
- Variação: {dados['variacao']:+.2f}%
- Volume: {dados.get('volume', 0):,}

INDICADORES TÉCNICOS:
- RSI (14): {dados.get('rsi', 50):.2f}
- SMA 20: ${dados.get('sma_20', 0):.2f}
- SMA 50: ${dados.get('sma_50', 0):.2f}
- Range 52W: ${dados.get('minimo_52w', 0):.2f} - ${dados.get('maximo_52w', 0):.2f}

FUNDAMENTOS:
- P/L: {safe_float(fundamentos.get('pe_ratio'))}
- ROE: {safe_float(fundamentos.get('roe'))}%
- Margem Líquida: {safe_float(fundamentos.get('net_margin'))}%
- Crescimento Receita: {safe_float(fundamentos.get('revenue_growth'))}%
- Score Fundamental: {fundamentos['score_fundamental']}/100

NOTÍCIAS RECENTES:
{noticias_texto}

INVESTIMENTO:
- Capital disponível: ${valor:,.2f}
- Ações possíveis: {valor/dados['preco']:.2f}

Forneça uma análise concisa (máximo 300 palavras) com:
1. Avaliação técnica e fundamentalista
2. Impacto das notícias recentes no preço e sentimento
3. Riscos principais
4. Recomendação (COMPRAR/MANTER/VENDER) justificada

Seja objetivo e direto."""

    try:
        resposta = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        print(f"{GREEN}✅ Análise gerada com sucesso{RESET}")
        return resposta.content[0].text
    except Exception as e:
        print(f"{RED}❌ Erro IA: {e}{RESET}")
        return None


# ================= EXIBIR RELATÓRIO =================
def exibir_relatorio(ticker, dados, fundamentos, analise, valor):
    """Exibe relatório formatado e colorido"""
    
    print_header(f"📊 RELATÓRIO DE ANÁLISE — {ticker}", MAGENTA)
    print(f"{BOLD}📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}{RESET}".center(100))
    
    # SEÇÃO 1: COTAÇÃO
    print_section("💰 COTAÇÃO ATUAL", CYAN)
    print(f"\n{'─'*100}")
    
    var_color = GREEN if dados['variacao'] >= 0 else RED
    print(f"{BOLD}Ticker:{RESET}               {CYAN}{ticker}{RESET}")
    print(f"{BOLD}Preço Atual:{RESET}          {CYAN}${dados['preco']:.2f} USD{RESET}")
    print(f"{BOLD}Variação:{RESET}             {var_color}{dados['variacao']:+.2f}%{RESET}")
    print(f"{BOLD}Volume:{RESET}               {dados.get('volume', 0):,}")
    print(f"{BOLD}Abertura:{RESET}             ${dados.get('abertura', 0):.2f}")
    print(f"{BOLD}Máxima do Dia:{RESET}        ${dados.get('alta', 0):.2f}")
    print(f"{BOLD}Mínima do Dia:{RESET}        ${dados.get('baixa', 0):.2f}")
    print(f"{BOLD}Fechamento Anterior:{RESET}  ${dados.get('fechamento_anterior', 0):.2f}")
    print(f"{BOLD}Fonte:{RESET}                {dados.get('fonte', 'N/A')}")
    
    # SEÇÃO 2: INDICADORES TÉCNICOS
    print_section("📈 INDICADORES TÉCNICOS", BLUE)
    print(f"\n{'─'*100}")
    
    # RSI
    rsi = dados.get('rsi', 50)
    if rsi > 70:
        rsi_status = f"{RED}Sobrecomprado{RESET}"
        rsi_color = RED
    elif rsi < 30:
        rsi_status = f"{GREEN}Sobrevendido{RESET}"
        rsi_color = GREEN
    else:
        rsi_status = f"{YELLOW}Neutro{RESET}"
        rsi_color = YELLOW
    
    print(f"{BOLD}RSI (14):{RESET}             {rsi_color}{rsi:.2f}{RESET} — {rsi_status}")
    
    # Médias Móveis
    sma20 = dados.get('sma_20', 0)
    sma50 = dados.get('sma_50', 0)
    preco = dados['preco']
    
    if preco > sma20 > sma50:
        tendencia = f"{GREEN}Tendência de Alta (Golden Cross){RESET}"
    elif preco < sma20 < sma50:
        tendencia = f"{RED}Tendência de Baixa (Death Cross){RESET}"
    else:
        tendencia = f"{YELLOW}Tendência Indefinida{RESET}"
    
    print(f"{BOLD}SMA 20:{RESET}               ${sma20:.2f}")
    print(f"{BOLD}SMA 50:{RESET}               ${sma50:.2f}")
    print(f"{BOLD}Tendência:{RESET}            {tendencia}")
    
    # Range 52 semanas
    minimo = dados.get('minimo_52w', 0)
    maximo = dados.get('maximo_52w', 0)
    if maximo > minimo:
        posicao_52w = ((preco - minimo) / (maximo - minimo)) * 100
        pos_color = GREEN if posicao_52w > 50 else RED
        print(f"{BOLD}52W Range:{RESET}           ${minimo:.2f} - ${maximo:.2f}")
        print(f"{BOLD}Posição no Range:{RESET}    {pos_color}{posicao_52w:.1f}%{RESET}")
    
    # SEÇÃO 3: FUNDAMENTOS
    print_section("📊 ANÁLISE FUNDAMENTALISTA", MAGENTA)
    print(f"\n{'─'*100}")
    
    score = fundamentos['score_fundamental']
    cor = fundamentos['cor_avaliacao']
    
    print(f"{BOLD}Score Fundamentalista:{RESET}  {cor}{score}/100{RESET} — {cor}{fundamentos['avaliacao'].upper()}{RESET}")
    print(f"\n{BOLD}Métricas:{RESET}")
    
    pe = safe_float(fundamentos.get('pe_ratio'))
    pb = safe_float(fundamentos.get('pb_ratio'))
    roe = safe_float(fundamentos.get('roe'))
    roa = safe_float(fundamentos.get('roa'))
    margin = safe_float(fundamentos.get('net_margin'))
    growth = safe_float(fundamentos.get('revenue_growth'))
    debt = safe_float(fundamentos.get('debt_to_equity'))
    
    # Tabela de fundamentos
    print(f"{'─'*100}")
    print(f"{'MÉTRICA':<30} {'VALOR':<20} {'AVALIAÇÃO':<40}")
    print(f"{'─'*100}")
    
    # P/L
    if pe > 0:
        pe_aval = f"{GREEN}Barato{RESET}" if pe < 15 else (f"{RED}Caro{RESET}" if pe > 30 else f"{YELLOW}Neutro{RESET}")
        print(f"{'P/L (Price/Earnings)':<30} {pe:<20.2f} {pe_aval}")
    
    # ROE
    if roe != 0:
        roe_aval = f"{GREEN}Excelente{RESET}" if roe > 15 else (f"{YELLOW}Bom{RESET}" if roe > 10 else f"{RED}Fraco{RESET}")
        print(f"{'ROE (Return on Equity)':<30} {roe:<20.2f}% {roe_aval}")
    
    # ROA
    if roa != 0:
        print(f"{'ROA (Return on Assets)':<30} {roa:<20.2f}%")
    
    # Margem
    if margin != 0:
        margin_aval = f"{GREEN}Alta{RESET}" if margin > 15 else (f"{YELLOW}Média{RESET}" if margin > 5 else f"{RED}Baixa{RESET}")
        print(f"{'Margem Líquida':<30} {margin:<20.2f}% {margin_aval}")
    
    # Crescimento
    if growth != 0:
        growth_aval = f"{GREEN}Crescendo{RESET}" if growth > 0.05 else (f"{YELLOW}Estável{RESET}" if growth > 0 else f"{RED}Declinando{RESET}")
        print(f"{'Crescimento de Receita':<30} {growth:<20.2f}% {growth_aval}")
    
    # Dívida
    if debt != 0:
        debt_aval = f"{GREEN}Baixo{RESET}" if debt < 1 else (f"{YELLOW}Médio{RESET}" if debt < 2 else f"{RED}Alto{RESET}")
        print(f"{'Dívida/Patrimônio':<30} {debt:<20.2f} {debt_aval}")
    
    print(f"{'─'*100}")
    print(f"\n{BOLD}Fonte:{RESET} {fundamentos.get('fonte_fundamental', 'N/A')}")
    
    # SEÇÃO 4: INVESTIMENTO
    print_section("💵 SIMULAÇÃO DE INVESTIMENTO", GREEN)
    print(f"\n{'─'*100}")
    
    acoes = valor / preco
    print(f"{BOLD}Capital Disponível:{RESET}    {CYAN}${valor:,.2f} USD{RESET}")
    print(f"{BOLD}Preço por Ação:{RESET}        {CYAN}${preco:.2f}{RESET}")
    print(f"{BOLD}Quantidade de Ações:{RESET}   {CYAN}{acoes:.4f}{RESET} (~{int(acoes)} ações inteiras)")
    print(f"{BOLD}Valor Total:{RESET}           {CYAN}${acoes * preco:,.2f}{RESET}")
    
    # SEÇÃO 5: ANÁLISE IA
    if analise:
        print_box("🤖 ANÁLISE INTELIGENTE (CLAUDE AI)", YELLOW)
        print()
        
        # Limpar formatação markdown
        analise_limpa = limpar_markdown(analise)
        
        # Quebrar análise em linhas
        linhas = analise_limpa.split('\n')
        for linha in linhas:
            if len(linha) <= 95:
                print(f"  {linha}")
            else:
                # Quebrar linhas longas
                palavras = linha.split()
                linha_atual = ""
                for palavra in palavras:
                    if len(linha_atual) + len(palavra) + 1 <= 95:
                        linha_atual += palavra + " "
                    else:
                        print(f"  {linha_atual.strip()}")
                        linha_atual = palavra + " "
                if linha_atual:
                    print(f"  {linha_atual.strip()}")
    
    # RODAPÉ
    print(f"\n{BOLD}{CYAN}{'═'*100}{RESET}")
    print(f"{BOLD}{GREEN}✅ Análise concluída com sucesso!{RESET}".center(110))
    print(f"{BOLD}{CYAN}{'═'*100}{RESET}\n")


# ================= MAIN =================
def main():
    print_header("📊 ANALISADOR DE AÇÕES", CYAN)
    print(f"{BOLD}{WHITE}FINNHUB + ALPHA VANTAGE + TRADIER + FMP + NEWSAPI + CLAUDE AI{RESET}".center(110))
    
    print(f"\n{BOLD}Configuração:{RESET}")
    print(f"  {'✅' if TRADIER_KEY else '❌'} Tradier API")
    print(f"  {'✅' if FINNHUB_KEY else '❌'} Finnhub API")
    print(f"  {'✅' if ALPHA_KEY else '❌'} Alpha Vantage API")
    print(f"  {'✅' if FMP_KEY else '❌'} FMP API")
    print(f"  {'✅' if NEWSAPI_KEY else '❌'} NewsAPI")
    print(f"  {'✅' if ANTHROPIC_KEY else '❌'} Anthropic API (Claude)")
    
    print_separator()
    
    ticker = input(f"\n{BOLD}{CYAN}🔍 Digite o ticker (ex: AAPL, MSFT, NVDA):{RESET} ").strip().upper()
    if not ticker:
        print(f"{RED}❌ Ticker inválido{RESET}")
        return
    
    try:
        valor = float(input(f"{BOLD}{CYAN}💰 Valor a investir (USD):{RESET} "))
        if valor <= 0:
            raise ValueError
    except ValueError:
        print(f"{RED}❌ Valor inválido{RESET}")
        return

    # Buscar dados
    dados = obter_dados_tecnicos(ticker)
    if not dados:
        return
    
    fundamentos = obter_dados_fundamentalistas(ticker)
    
    analise = gerar_analise_ai(ticker, dados, fundamentos, valor)
    
    # Exibir relatório formatado
    exibir_relatorio(ticker, dados, fundamentos, analise, valor)


if __name__ == "__main__":
    main()