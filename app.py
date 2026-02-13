#!/usr/bin/env python3
import os
from datetime import datetime

from flask import Flask, render_template, request

from main import (
    obter_dados_tecnicos,
    obter_dados_fundamentalistas,
    gerar_analise_ai,
    safe_float,
)


app = Flask(__name__)


def classificar_rsi(rsi):
    if rsi > 70:
        return "Sobrecomprado", "bad"
    if rsi < 30:
        return "Sobrevendido", "good"
    return "Neutro", "warn"


def classificar_tendencia(preco, sma20, sma50):
    if preco > sma20 > sma50:
        return "Tendência de Alta (Golden Cross)", "good"
    if preco < sma20 < sma50:
        return "Tendência de Baixa (Death Cross)", "bad"
    return "Tendência Indefinida", "warn"


def montar_metricas_fundamentos(fundamentos):
    pe = safe_float(fundamentos.get("pe_ratio"))
    roe = safe_float(fundamentos.get("roe"))
    roa = safe_float(fundamentos.get("roa"))
    margin = safe_float(fundamentos.get("net_margin"))
    growth = safe_float(fundamentos.get("revenue_growth"))
    debt = safe_float(fundamentos.get("debt_to_equity"))

    metricas = []

    if pe > 0:
        if pe < 15:
            aval, cls = "Barato", "good"
        elif pe > 30:
            aval, cls = "Caro", "bad"
        else:
            aval, cls = "Neutro", "warn"
        metricas.append({"nome": "P/L (Price/Earnings)", "valor": f"{pe:.2f}", "avaliacao": aval, "classe": cls})

    if roe != 0:
        if roe > 15:
            aval, cls = "Excelente", "good"
        elif roe > 10:
            aval, cls = "Bom", "warn"
        else:
            aval, cls = "Fraco", "bad"
        metricas.append({"nome": "ROE (Return on Equity)", "valor": f"{roe:.2f}%", "avaliacao": aval, "classe": cls})

    if roa != 0:
        metricas.append({"nome": "ROA (Return on Assets)", "valor": f"{roa:.2f}%", "avaliacao": "—", "classe": "muted"})

    if margin != 0:
        if margin > 15:
            aval, cls = "Alta", "good"
        elif margin > 5:
            aval, cls = "Média", "warn"
        else:
            aval, cls = "Baixa", "bad"
        metricas.append({"nome": "Margem Líquida", "valor": f"{margin:.2f}%", "avaliacao": aval, "classe": cls})

    if growth != 0:
        if growth > 0.05:
            aval, cls = "Crescendo", "good"
        elif growth > 0:
            aval, cls = "Estável", "warn"
        else:
            aval, cls = "Declinando", "bad"
        metricas.append({"nome": "Crescimento de Receita", "valor": f"{growth:.2f}%", "avaliacao": aval, "classe": cls})

    if debt != 0:
        if debt < 1:
            aval, cls = "Baixo", "good"
        elif debt < 2:
            aval, cls = "Médio", "warn"
        else:
            aval, cls = "Alto", "bad"
        metricas.append({"nome": "Dívida/Patrimônio", "valor": f"{debt:.2f}", "avaliacao": aval, "classe": cls})

    return metricas


@app.route("/", methods=["GET", "POST"])
def index():
    erro = None
    resultado = None

    if request.method == "POST":
        ticker = (request.form.get("ticker") or "").strip().upper()
        valor_raw = (request.form.get("valor") or "").strip().replace(",", ".")

        if not ticker:
            erro = "Ticker inválido. Exemplo: AAPL, MSFT, NVDA."
        else:
            try:
                valor = float(valor_raw)
                if valor <= 0:
                    raise ValueError
            except ValueError:
                erro = "Valor inválido. Use um número maior que zero."
                valor = None

        if not erro:
            dados = obter_dados_tecnicos(ticker)
            if not dados:
                erro = "Não foi possível obter dados de preço para esse ticker."
            else:
                fundamentos = obter_dados_fundamentalistas(ticker)
                analise = gerar_analise_ai(ticker, dados, fundamentos, valor)

                rsi = dados.get("rsi", 50)
                rsi_status, rsi_class = classificar_rsi(rsi)
                tendencia_txt, tendencia_class = classificar_tendencia(
                    dados["preco"], dados.get("sma_20", 0), dados.get("sma_50", 0)
                )

                minimo = dados.get("minimo_52w", 0)
                maximo = dados.get("maximo_52w", 0)
                posicao_52w = None
                if maximo > minimo:
                    posicao_52w = ((dados["preco"] - minimo) / (maximo - minimo)) * 100

                acoes = valor / dados["preco"]

                resultado = {
                    "ticker": ticker,
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "dados": dados,
                    "fundamentos": fundamentos,
                    "rsi": rsi,
                    "rsi_status": rsi_status,
                    "rsi_class": rsi_class,
                    "tendencia": tendencia_txt,
                    "tendencia_class": tendencia_class,
                    "minimo_52w": minimo,
                    "maximo_52w": maximo,
                    "posicao_52w": posicao_52w,
                    "acaoes": acoes,
                    "valor": valor,
                    "analise": analise,
                    "metricas": montar_metricas_fundamentos(fundamentos),
                }

    return render_template("index.html", erro=erro, resultado=resultado)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
