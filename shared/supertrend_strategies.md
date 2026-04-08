## Supertrend Strategies — 2026-04-04

### Strategy 1: Supertrend + EMA Trend Filter
- **Source:** TradingView (Supertrend indicator by KivancOzbilgic) + QuantConnect Supertrend strategy
- **Core Logic:**
  - Supertrend(period=10, multiplier=3.0) — ATR-based trailing stop line
  - EMA(200) for trend filter
  - Entry long: Supertrend flips bullish AND price > EMA(200)
  - Entry short: Supertrend flips bearish AND price < EMA(200)
  - Exit: Supertrend flips to opposite direction
- **Expected Edge:** Supertrend captures trend direction with ATR-adaptive stops. The EMA(200) filter prevents counter-trend signals in choppy markets.
- **Why H4/Daily:** Supertrend works best on higher timeframes because ATR-based levels are more stable. On M5-M15, Supertrend whipsaws frequently in noise. On H4, each signal represents a genuine regime shift.
- **Python Pseudocode:**
  ```python
  atr = atr(period=10)
  hl2 = (high + low) / 2
  upper_band = hl2 + multiplier * atr
  lower_band = hl2 - multiplier * atr
  # Supertrend tracking logic (stateful)
  supertrend = ...  # standard Supertrend calculation
  trend = 1 if close > supertrend else -1
  ema200 = sma(close, 200)
  long_entry = (trend == 1) & (close > ema200) & (trend.shift(1) == -1)
  short_entry = (trend == -1) & (close < ema200) & (trend.shift(1) == 1)
  ```

### Strategy 2: Double Supertrend (Fast + Slow)
- **Source:** TradingView "Double Supertrend Strategy" by LazyBear variant
- **Core Logic:**
  - Fast Supertrend(period=7, multiplier=2.0)
  - Slow Supertrend(period=14, multiplier=3.0)
  - Entry long: BOTH Supertrends flip bullish simultaneously
  - Entry short: BOTH Supertrends flip bearish simultaneously
  - Exit: Fast Supertrend flips opposite
- **Expected Edge:** The double Supertrend requires BOTH short and long-term ATR trails to agree, filtering out false signals. The slow Supertrend acts as a trend filter while the fast Supertrend provides the actual entry trigger.
- **Why H4/Daily:** The two Supertrends need enough bars between them to diverge meaningfully. On M5, period 7 and 14 are nearly identical. On H4, fast=7 covers 28 hours, slow=14 covers 56 hours — meaningfully different trend horizons.
- **Python Pseudocode:**
  ```python
  st_fast = supertrend(period=7, multiplier=2.0)
  st_slow = supertrend(period=14, multiplier=3.0)
  long_entry = (close > st_fast) & (close > st_slow) & \
               ((close.shift(1) < st_fast.shift(1)) or (close.shift(1) < st_slow.shift(1)))
  short_entry = (close < st_fast) & (close < st_slow) & \
                ((close.shift(1) > st_fast.shift(1)) or (close.shift(1) > st_slow.shift(1)))
  exit = (close < st_fast) if long else (close > st_fast)
  ```

### Strategy 3: Supertrend + Volume Confirmation
- **Source:** TradingView Supertrend + Volume strategy + r/algotrading discussion
- **Core Logic:**
  - Supertrend(period=10, multiplier=3.0)
  - Volume must be > 1.5x SMA(volume, 20) on the entry bar
  - Entry long: Supertrend flips bullish + volume spike
  - Entry short: Supertrend flips bearish + volume spike
  - Exit: Supertrend flips OR trailing stop (2.5x ATR)
- **Expected Edge:** Volume confirmation ensures the Supertrend signal is backed by genuine institutional participation, not a random price spike breaking through ATR bands. Low-volume Supertrend flips are often noise.
- **Why H4/Daily:** Volume on H4/Daily candles represents significant accumulation/distribution. Volume spikes on these timeframes are meaningful. On M5, volume spikes are often meaningless micro-structure noise.
- **Python Pseudocode:**
  ```python
  st = supertrend(period=10, multiplier=3.0)
  vol_ma = sma(volume, 20)
  vol_spike = volume > vol_ma * 1.5
  long_entry = (close > st) & (close.shift(1) < st.shift(1)) & vol_spike
  short_entry = (close < st) & (close.shift(1) > st.shift(1)) & vol_spike
  ```

### Strategy 4: Supertrend + RSI Divergence
- **Core Logic:**
  - Supertrend(period=10, multiplier=3.0)
  - RSI(14) oversold/overbought divergence
  - Entry long: Supertrend is bullish AND RSI was oversold < 30 within last 5 bars
  - Entry short: Supertrend is bearish AND RSI was overbought > 70 within last 5 bars
  - Exit: Supertrend flips OR RSI crosses back through 50
- **Expected Edge:** Combines trend-following (Supertrend) with mean-reversion entry timing (RSI pullback). Enter trends AFTER a pullback, not at the breakout.
- **Why H4/Daily:** RSI divergence on H4/Daily is a significant signal. On lower TF, RSI is too noisy and generates false divergence signals.

### Strategy 5: Supertrend Multi-Timeframe Confluence
- **Core Logic:**
  - Daily Supertrend(period=10, multiplier=3.0) — trend direction
  - H4 Supertrend(period=7, multiplier=2.0) — entry timing
  - Entry long: Daily Supertrend bullish AND H4 Supertrend flips bullish
  - Entry short: Daily Supertrend bearish AND H4 Supertrend flips bearish
  - Exit: H4 Supertrend flips opposite
- **Expected Edge:** The Daily Supertrend filters for the macro trend, while the H4 Supertrend provides timely entries. This avoids entering late in a Daily trend or entering counter-trend on H4.
- **Why H4/Daily:** By definition this IS a multi-timeframe strategy. It requires Daily + H4 data to function.
