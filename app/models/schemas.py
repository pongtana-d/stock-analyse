from __future__ import annotations

from pydantic import BaseModel


# --- Indicator sub-models ---


class EMAData(BaseModel):
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None


class MACDData(BaseModel):
    macd: float | None = None
    signal: float | None = None
    histogram: float | None = None
    crossover: str | None = None  # "bullish" | "bearish" | None


class RSIPoint(BaseModel):
    date: str
    value: float


class RSIData(BaseModel):
    value: float | None = None
    series: list[RSIPoint] = []  # last ~30 bars for divergence detection


class BollingerData(BaseModel):
    upper: float | None = None
    middle: float | None = None
    lower: float | None = None
    bandwidth: float | None = None


class VolumeData(BaseModel):
    obv: float | None = None
    obvTrend: str | None = None  # "rising" | "falling" | "flat"
    recentVsAvg: float | None = None


class PivotData(BaseModel):
    pp: float | None = None
    r1: float | None = None
    r2: float | None = None
    s1: float | None = None
    s2: float | None = None


class CandlestickPattern(BaseModel):
    name: str       # "Engulfing", "Hammer", etc.
    date: str       # date string (formatted same as OHLCV bars)
    direction: str  # "bullish" | "bearish"
    barsAgo: int    # 0 = last bar, 1 = 2 bars ago, ...


class CandlestickData(BaseModel):
    patterns: list[CandlestickPattern] = []


class SwingPoint(BaseModel):
    date: str
    price: float
    type: str  # "high" | "low"


class SwingData(BaseModel):
    points: list[SwingPoint] = []  # oldest → newest; read sequence for HH/HL/LH/LL


class FibonacciData(BaseModel):
    trend: str | None = None  # "bullish" | "bearish" — direction of the swing used for retracement
    level_382: float | None = None
    level_50: float | None = None
    level_618: float | None = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        return {
            "trend": data.pop("trend"),
            "38.2": data.pop("level_382"),
            "50": data.pop("level_50"),
            "61.8": data.pop("level_618"),
        }


class TimeframeIndicators(BaseModel):
    ema: EMAData = EMAData()
    macd: MACDData = MACDData()
    rsi: RSIData = RSIData()
    bollingerBands: BollingerData = BollingerData()
    volume: VolumeData = VolumeData()
    pivotPoints: PivotData = PivotData()
    fibonacci: FibonacciData = FibonacciData()
    candlestick: CandlestickData = CandlestickData()
    swingPoints: SwingData = SwingData()


# --- OHLCV ---


class OHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# --- Top-level response ---


class StockResponse(BaseModel):
    ticker: str
    timestamp: str
    dataDelay: str = "15min"
    indicators: dict[str, TimeframeIndicators]
    ohlc: dict[str, list[OHLCVBar]]


# --- Portfolio ---


class PortfolioItem(BaseModel):
    ticker: str


class PortfolioList(BaseModel):
    tickers: list[str] = []


# --- Analysis ---


class AnalysisRecord(BaseModel):
    id: int
    ticker: str
    ai_model: str
    system_prompt: str | None = None
    indicator_data: dict | None = None
    ai_response: str
    signal: str | None = None
    confidence: str | None = None
    analysis_date: str
    created_at: str


class AnalysisRunSummary(BaseModel):
    ticker: str
    signal: str | None = None
    confidence: str | None = None
    analysis_date: str
    error: str | None = None


class AnalysisRunResponse(BaseModel):
    triggered_at: str
    market_open: bool
    results: list[AnalysisRunSummary] = []


# --- Config ---


class ConfigItem(BaseModel):
    key: str
    value: str


class ConfigUpdate(BaseModel):
    value: str


# --- Health ---


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    yfinance: str  # "ok" | "error"
