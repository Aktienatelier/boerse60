"""Kursdaten (kostenlos über yfinance / Yahoo Finance) für eine Folge holen und cachen."""
from __future__ import annotations

import json
import math
import warnings
from datetime import date, datetime
from pathlib import Path

warnings.filterwarnings("ignore")

NAMEN = {
    "^GSPC": "S&P 500", "^NDX": "Nasdaq 100", "^IXIC": "Nasdaq", "^DJI": "Dow Jones",
    "^GDAXI": "DAX", "^MDAXI": "MDAX", "^STOXX50E": "Euro Stoxx 50", "^N225": "Nikkei 225",
    "^HSI": "Hang Seng", "^RUT": "Russell 2000", "^VIX": "VIX (Angst-Index)",
    "^TNX": "US-Rendite 10 J.", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
    "GC=F": "Gold", "SI=F": "Silber", "BZ=F": "Brent-Öl", "CL=F": "WTI-Öl",
    "EURUSD=X": "Euro / Dollar",
    "XLK": "Technologie", "XLF": "Finanzen", "XLV": "Gesundheit", "XLY": "Zyklischer Konsum",
    "XLC": "Kommunikation", "XLI": "Industrie", "XLP": "Basiskonsum", "XLE": "Energie",
    "XLU": "Versorger", "XLRE": "Immobilien", "XLB": "Rohstoffe",
    "NVDA": "Nvidia", "MSFT": "Microsoft", "AAPL": "Apple", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta", "TSLA": "Tesla", "AVGO": "Broadcom", "AMD": "AMD", "PLTR": "Palantir",
    "ORCL": "Oracle", "NFLX": "Netflix", "MU": "Micron", "INTC": "Intel", "CSCO": "Cisco",
    "CRM": "Salesforce", "ADBE": "Adobe", "QCOM": "Qualcomm", "TXN": "Texas Instruments",
    "JPM": "JPMorgan", "GS": "Goldman Sachs", "BAC": "Bank of America", "V": "Visa",
    "MA": "Mastercard", "XOM": "ExxonMobil", "CVX": "Chevron", "LLY": "Eli Lilly",
    "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson", "PFE": "Pfizer", "MRK": "Merck & Co.",
    "ABBV": "AbbVie", "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot", "MCD": "McDonald's",
    "NKE": "Nike", "KO": "Coca-Cola", "PEP": "PepsiCo", "DIS": "Disney", "BA": "Boeing",
    "CAT": "Caterpillar", "GE": "GE Aerospace", "UBER": "Uber", "SHOP": "Shopify",
    "COIN": "Coinbase", "SNOW": "Snowflake", "CRWD": "CrowdStrike", "PANW": "Palo Alto",
    "ARM": "Arm", "SMCI": "Super Micro", "DELL": "Dell", "IBM": "IBM", "ANET": "Arista",
    "MRVL": "Marvell", "LRCX": "Lam Research", "AMAT": "Applied Materials", "KLAC": "KLA",
    "ASML": "ASML", "TSM": "TSMC", "SAP": "SAP (ADR)", "NVO": "Novo Nordisk", "SBUX": "Starbucks",
    "PYPL": "PayPal", "ABNB": "Airbnb", "SPOT": "Spotify", "MSTR": "Strategy", "HOOD": "Robinhood",
    "SIE.DE": "Siemens", "SAP.DE": "SAP", "RHM.DE": "Rheinmetall", "ALV.DE": "Allianz",
    "DTE.DE": "Telekom", "BAS.DE": "BASF", "BAYN.DE": "Bayer", "MBG.DE": "Mercedes-Benz",
    "BMW.DE": "BMW", "VOW3.DE": "Volkswagen", "ADS.DE": "Adidas", "IFX.DE": "Infineon",
    "DBK.DE": "Deutsche Bank", "AIR.DE": "Airbus", "MUV2.DE": "Munich Re", "DHL.DE": "DHL",
    "EOAN.DE": "E.ON", "RWE.DE": "RWE", "HEN3.DE": "Henkel", "BEI.DE": "Beiersdorf",
    "CBK.DE": "Commerzbank", "CON.DE": "Continental", "DB1.DE": "Deutsche Börse",
    "DTG.DE": "Daimler Truck", "ENR.DE": "Siemens Energy", "FRE.DE": "Fresenius",
    "HEI.DE": "Heidelberg Mat.", "HNR1.DE": "Hannover Rück", "MRK.DE": "Merck KGaA",
    "MTX.DE": "MTU Aero", "QIA.DE": "Qiagen", "SHL.DE": "Siemens Healthineers",
    "SRT3.DE": "Sartorius", "SY1.DE": "Symrise", "VNA.DE": "Vonovia", "ZAL.DE": "Zalando",
    "G1A.DE": "GEA", "BNR.DE": "Brenntag", "P911.DE": "Porsche AG", "PAH3.DE": "Porsche SE",
    "SCMN.SW": "Swisscom",
}

EINHEIT = {"^TNX": "%", "EURUSD=X": "$", "^VIX": "Pkt."}
INDEX_PREFIX = "^"

SEKTOREN = {  # ungefähre Gewichte im S&P 500 (für die Kachelgröße)
    "XLK": 32, "XLF": 13, "XLV": 9.5, "XLY": 10.5, "XLC": 9.5, "XLI": 8.5,
    "XLP": 5, "XLE": 3, "XLU": 2.5, "XLRE": 2, "XLB": 2,
}

UNIVERSUM_US = ("NVDA MSFT AAPL AMZN GOOGL META TSLA AVGO AMD PLTR ORCL NFLX MU INTC CSCO CRM ADBE "
                "QCOM TXN JPM GS BAC V MA XOM CVX LLY UNH JNJ PFE MRK ABBV WMT COST HD MCD NKE KO "
                "PEP DIS BA CAT GE UBER SHOP COIN SNOW CRWD PANW ARM SMCI DELL IBM ANET MRVL LRCX "
                "AMAT KLAC ASML TSM NVO SBUX PYPL ABNB SPOT MSTR HOOD").split()
UNIVERSUM_DE = ("ADS AIR ALV BAS BAYN BEI BMW BNR CBK CON DB1 DBK DHL DTE DTG ENR EOAN FRE G1A HEI "
                "HEN3 HNR1 IFX MBG MRK MTX MUV2 QIA RHM RWE SAP SHL SIE SRT3 SY1 VNA VOW3 ZAL").split()
UNIVERSUM_DE = [t + ".DE" for t in UNIVERSUM_DE]

STANDARD_MARKT = ["^GSPC", "^NDX", "^GDAXI", "BTC-USD"]


def name_of(tk: str, info_name: str | None = None) -> str:
    return NAMEN.get(tk) or info_name or tk


def unit_of(tk: str, currency: str | None) -> str:
    if tk in EINHEIT:
        return EINHEIT[tk]
    if tk.startswith(INDEX_PREFIX):
        return "Pkt."
    return {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF", "JPY": "¥"}.get(currency or "", currency or "")


def _clean(v):
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except Exception:
        return None


def collect_tickers(ep: dict) -> dict:
    need = {"markt": set(), "detail": {}, "sektoren": False, "movers": []}
    for sz in ep.get("szenen", []):
        typ = sz.get("typ")
        if typ == "markt":
            need["markt"].update(sz.get("werte") or STANDARD_MARKT)
        elif typ in ("aktie", "zahl", "hook") and sz.get("ticker"):
            need["detail"][sz["ticker"]] = sz.get("chart", "intraday")
        elif typ == "sektoren":
            need["sektoren"] = True
        elif typ == "gewinner_verlierer":
            uni = sz.get("tickers") or (UNIVERSUM_DE if sz.get("markt") == "de" else UNIVERSUM_US)
            need["movers"].append(uni)
    return need


def fetch(ep: dict, verbose=True) -> dict:
    import yfinance as yf

    target = ep.get("datum")
    target_d = date.fromisoformat(target) if target else None
    need = collect_tickers(ep)
    out = {"abgerufen": datetime.now().isoformat(timespec="seconds"), "werte": {},
           "sektoren": {}, "movers": []}

    def day_change(hist):
        """Schluss am Zieltag gegenüber dem Vortag; Zieltag = Folgen-Datum oder letzter Handelstag."""
        c = hist["Close"].dropna()
        if len(c) < 2:
            return None
        idx = [i for i, ts in enumerate(c.index) if target_d is None or ts.date() <= target_d]
        if not idx:
            return None
        i = idx[-1]
        if i < 1:
            return None
        return {"datum": c.index[i].date().isoformat(), "kurs": float(c.iloc[i]),
                "vortag": float(c.iloc[i - 1]), "pct": (float(c.iloc[i]) / float(c.iloc[i - 1]) - 1) * 100,
                "i": i}

    def info_for(tk):
        try:
            fi = yf.Ticker(tk).fast_info
            return fi.get("currency")
        except Exception:
            return None

    def series_daily(hist, upto_i, n):
        c = hist["Close"].dropna()
        seg = c.iloc[max(0, upto_i - n + 1): upto_i + 1]
        return [[ts.date().isoformat(), float(v)] for ts, v in seg.items()]

    def intraday(tk, day_iso):
        try:
            h = yf.Ticker(tk).history(period="5d", interval="5m", prepost=False)
            h = h[[ts.date().isoformat() == day_iso for ts in h.index]]
            c = h["Close"].dropna()
            return [[ts.strftime("%H:%M"), float(v)] for ts, v in c.items()]
        except Exception:
            return []

    # Markt-Kacheln und Detail-Werte
    alle = set(need["markt"]) | set(need["detail"].keys())
    for tk in sorted(alle):
        try:
            hist = yf.Ticker(tk).history(period="1y", interval="1d", auto_adjust=False)
        except Exception as e:
            print(f"  ! {tk}: {e}")
            continue
        ch = day_change(hist)
        if not ch:
            print(f"  ! {tk}: keine Daten")
            continue
        cur = info_for(tk)
        rec = {"name": name_of(tk), "einheit": unit_of(tk, cur), "waehrung": cur, **ch}
        rec["intraday"] = intraday(tk, ch["datum"])
        rec["tage"] = series_daily(hist, ch["i"], 260)
        rec.pop("i", None)
        out["werte"][tk] = rec
        if verbose:
            print(f"  {rec['name']:<20} {ch['datum']}  {ch['kurs']:>12.2f}  {ch['pct']:+6.2f} %")

    if need["sektoren"]:
        h = yf.download(list(SEKTOREN), period="1mo", interval="1d", progress=False, auto_adjust=False)["Close"]
        for tk in SEKTOREN:
            ch = day_change(h[[tk]].rename(columns={tk: "Close"}))
            if ch:
                out["sektoren"][tk] = {"name": NAMEN[tk], "pct": ch["pct"], "gewicht": SEKTOREN[tk]}

    for uni in need["movers"]:
        h = yf.download(list(uni), period="1mo", interval="1d", progress=False, auto_adjust=False)["Close"]
        res = []
        for tk in uni:
            if tk not in h.columns:
                continue
            ch = day_change(h[[tk]].rename(columns={tk: "Close"}))
            if ch:
                res.append({"ticker": tk, "name": name_of(tk), "pct": ch["pct"], "kurs": ch["kurs"]})
        res.sort(key=lambda r: r["pct"])
        out["movers"].append(res)
        if verbose and res:
            print(f"  Flop: {res[0]['name']} {res[0]['pct']:+.2f} %   Top: {res[-1]['name']} {res[-1]['pct']:+.2f} %")

    for k in out["werte"].values():
        k["kurs"], k["vortag"] = _clean(k["kurs"]), _clean(k["vortag"])
    return out


def load_or_fetch(ep_path: Path, ep: dict, refresh=False) -> dict:
    cache = ep_path.with_name(ep_path.stem + "_daten.json")
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    print("Lade Kursdaten (Yahoo Finance) …")
    data = fetch(ep)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data
