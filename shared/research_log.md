# Shared Research Log — Strategy Pipeline

---

## NEW STRATEGIES — Unconventional / Research-Grade — 2026-04-08

### Strategy 6: Classic Cointegration Pairs Trading (WTI/Brent Crude)
- **Status:** 🔬 RESEARCH PHASE
- **Source URL:** https://databento.com/blog/build-a-pairs-trading-strategy-in-python
- **Category:** Statistical Arbitrage / Pairs Trading
- **Core Logic:**
  - Uses Engle-Granger two-step cointegration test to verify stationarity of spread
  - Calculates hedge ratio via OLS linear regression: Y = α + βX + ε
  - Constructs spread: spread = Y - (α + βX) = residuals
  - Normalizes spread using z-score: z = (spread - mean) / std
  - Entry Long: z < -ENTRY_THRESHOLD (buy Y, sell X)
  - Entry Short: z > ENTRY_THRESHOLD (sell Y, buy X)
  - Exit: |z| < EXIT_THRESHOLD (mean reversion)
  - Uses rolling windows: re-estimates cointegration and hedge ratio every LOOKBACK periods
  - Trades 1:1 nominal hedge ratio (can be adjusted using β for different volatilities)
- **Expected Edge:** Pairs trading exploits mean reversion in the spread between cointegrated assets. Unlike simple correlation, cointegration ensures a long-term equilibrium relationship. The strategy profits when the spread deviates from its mean and subsequently reverts. Using rolling windows adapts to changing market conditions and hedge ratios.
- **Python Pseudocode:**
  ```python
  import pandas as pd
  import numpy as np
  from statsmodels.tsa.stattools import coint
  from sklearn.linear_model import LinearRegression
  
  # Parameters (from Databento blog)
  LOOKBACK = 100
  ENTRY_THRESHOLD = 1.5
  EXIT_THRESHOLD = 0.5
  P_THRESHOLD = 0.05
  
  # Initialize columns
  df['cointegrated'] = 0
  df['residual'] = 0.0
  df['zscore'] = 0.0
  df['position_x'] = 0   # Position in asset X (e.g., WTI)
  df['position_y'] = 0   # Position in asset Y (e.g., Brent)
  
  is_cointegrated = False
  lr = LinearRegression()
  
  # Rolling window approach
  for i in range(LOOKBACK, len(df), LOOKBACK):
      # Extract lookback window
      x = df['x'].iloc[i-LOOKBACK:i].values[:, None]  # Asset X prices
      y = df['y'].iloc[i-LOOKBACK:i].values[:, None]  # Asset Y prices
      
      if is_cointegrated:
          # Forward window: compute and normalize signal
          x_new = df['x'].iloc[i:i+LOOKBACK].values[:, None]
          y_new = df['y'].iloc[i:i+LOOKBACK].values[:, None]
          
          # Calculate spread using hedge ratio from lookback period
          spread_back = y - lr.coef_[0] * x - lr.intercept_
          spread_forward = y_new - lr.coef_[0] * x_new - lr.intercept_
          
          # Z-score normalization
          zscore = (spread_forward - np.mean(spread_back)) / np.std(spread_back)
          
          # Store results
          df.iloc[i:i+LOOKBACK, df.columns.get_loc("cointegrated")] = 1
          df.iloc[i:i+LOOKBACK, df.columns.get_loc("residual")] = spread_forward
          df.iloc[i:i+LOOKBACK, df.columns.get_loc("zscore")] = zscore
      
      # Check for cointegration in lookback window
      _, p_value, _ = coint(x.flatten(), y.flatten())
      is_cointegrated = p_value < P_THRESHOLD
      
      # Update hedge ratio if cointegrated
      if is_cointegrated:
          lr.fit(x, y)
  
  # Generate trading signals
  # Long Y, Short X when spread is undervalued (z < -threshold)
  df.loc[df['zscore'] < -ENTRY_THRESHOLD, 'position_y'] = 1
  df.loc[df['zscore'] < -ENTRY_THRESHOLD, 'position_x'] = -1
  
  # Short Y, Long X when spread is overvalued (z > threshold)
  df.loc[df['zscore'] > ENTRY_THRESHOLD, 'position_y'] = -1
  df.loc[df['zscore'] > ENTRY_THRESHOLD, 'position_x'] = 1
  
  # Exit positions when z-score reverts to near zero
  exit_long = (df['zscore'] >= -EXIT_THRESHOLD) & (df['zscore'] <= EXIT_THRESHOLD)
  df.loc[exit_long, ['position_x', 'position_y']] = 0
  
  # Prevent look-ahead bias
### Strategy 8: Kalman Filter Mean Reversion
- **Status:** 🔬 RESEARCH PHASE
- **Source:** QuantifiedStrategies.com — "Kalman Filter Trading Strategy"
- **URL:** https://www.quantifiedstrategies.com/kalman-filter-trading-strategy/
- **Category:** Mean Reversion / Adaptive Filtering
- **Core Logic:**
  - Kalman Filter dynamically estimates asset's "fair value" (latent state) from noisy price observations using state-space model
  - Computes rolling 5-period SMA of closing prices as short-term trend proxy
  - **Entry Long:** 5-day SMA crosses **below** Kalman Filter estimate → price below fair value → buy
  - **Entry Short:** 5-day SMA crosses **above** Kalman Filter estimate → price above fair value → sell short
  - **Exit:** Opposite crossover (5-day SMA crosses back above/below Kalman Filter)
  - Mathematical model: y(t) = β(t)×x(t) + ε(t), where β(t) evolves as random walk
- **Expected Edge:** Kalman filter continuously updates the state estimate without fixed lookback windows, adapting to changing market regimes. Profits from short-term price deviations reverting to dynamically-estimated equilibrium. SPY backtest: CAGR 6.33%, risk-adjusted return 17.80%, only 35.38% time invested — captures mean reversion while sidestepping trending periods.
- **Python Pseudocode:**
  ```python
  from pykalman import KalmanFilter
  import pandas_ta as ta
  
  def kalman_mean_reversion(df):
      close = df['close'].values
      
      # Initialize Kalman Filter (1D state space)
      kf = KalmanFilter(
          transition_matrices=1,
          observation_matrices=1,
          initial_state_mean=close[0],
          initial_state_covariance=1,
          observation_covariance=1,
          transition_covariance=0.01
      )
      
      state_means, _ = kf.filter(close)
      df['kalman'] = state_means.flatten()
      df['sma_5'] = df['close'].rolling(5).mean()
      
      df['signal'] = 0
      long_entry = (df['sma_5'].shift(1) >= df['kalman'].shift(1)) & (df['sma_5'] < df['kalman'])
      long_exit = (df['sma_5'].shift(1) < df['kalman'].shift(1)) & (df['sma_5'] >= df['kalman'])
      df.loc[long_entry, 'signal'] = 1
      df.loc[long_exit, 'signal'] = 0
      
      return df['signal']
  ```
- **Risk Considerations:**
  - Parameter-sensitive (transition/observation covariance); requires walk-forward optimization
  - Poor performance in strong trending markets; consider ADX filter
  - pykalman not in standard library; requires `pip install pykalman`
  - Only long side tested; short side needs validation
  - No explicit stop-loss in base design; recommend ATR-based stops

### Strategy 9: RSI(2) Connors Mean Reversion
- **Status:** 🔬 RESEARCH PHASE
- **Source:** Larry Connors & Cesar Alvarez — "Short Term Trading Strategies That Work" (2008)
- **URL:** https://www.quantifiedstrategies.com/rsi-2-strategy/
- **Category:** Mean Reversion / Short-Term Oscillator
- **Core Logic:**
  - **Trend Filter (daily timeframe):**
    - Long setup: Close > 200-day SMA
    - Short setup: Close < 200-day SMA
  - **Entry Trigger:** RSI(2) < 5 for longs; RSI(2) > 95 for shorts
  - **Exit Rules:**
    - Long exit: RSI(2) > 65 OR Close > 5-day SMA
    - Short exit: RSI(2) < 30 OR Close < 5-day SMA
  - Entry at market close; typical hold 3–7 days
- **Expected Edge:** 2-period RSI is hyper-sensitive, capturing short-term sentiment extremes. 200-day SMA filter aligns trades with dominant trend, avoiding "catching falling knives." Backtests on SPY/QQQ show 70–85% win rate when rules strictly followed. Profits from panic-selling in uptrends and euphoria-buying in downtrends.
- **Python Pseudocode:**
  ```python
  import pandas_ta as ta
  
  def connors_rsi2_strategy(df):
      df['sma_200'] = df['close'].rolling(200).mean()
      trend_bull = df['close'] > df['sma_200']
      trend_bear = df['close'] < df['sma_200']
      
      df['rsi_2'] = ta.rsi(df['close'], length=2)
      df['sma_5'] = df['close'].rolling(5).mean()
      
      df['signal'] = 0
      long_entry = trend_bull & (df['rsi_2'] < 5)
      df.loc[long_entry, 'signal'] = 1
      
      positions = df['signal'].shift(1) == 1
      exit_long = positions & ((df['rsi_2'] > 65) | (df['close'] > df['sma_5']))
      df.loc[exit_long, 'signal'] = 0
      
      return df['signal']
  ```
- **Risk Considerations:**
  - Gap risk — entries at close expose to overnight gaps
  - No stop-loss in original design; consider discretionary volatility stops
  - May underperform in parabolic trends where RSI stays extreme
  - Best on liquid ETFs (SPY, QQQ); avoid low-volume stocks
  - Requires daily bars; intraday not recommended

### Strategy 10: ATR-Scaled Mean Reversion (Triple MA)
- **Status:** 🔬 RESEARCH PHASE
- **Source:** James Ford — "MA+ATR Mean Reversion" (pyhood)
- **URL:** https://jamestford.github.io/pyhood/strategies/ma-atr-mean-reversion/
- **Category:** Mean Reversion / Volatility-Adjusted Bands
- **Core Logic:**
  - **Trend Confirmation:** EMA(10) > EMA(50) > EMA(200) for uptrend (reverse for downtrend)
  - **Entry:** Price pulls back to EMA(10) and dips below lower ATR band → long on next open
    - Lower band = EMA(10) − ATR(14) × 2.0
  - **Exit:** Price reverts to EMA(10) (take profit)
  - Optional minimum 2-bar hold to filter noise
- **Expected Edge:** Triple EMA filter restricts trades to counter-trend within established trends. ATR bands auto-scale to volatility — wider in chop (fewer false breakouts), tighter in calm (more sensitive). Designed for high win rate (>65%) with controlled drawdown; consistent mean reversion capture, not home-run.
- **Python Pseudocode:**
  ```python
  import pandas_ta as ta
  
  def atr_scaled_mean_reversion(df):
      df['ema_fast'] = ta.ema(df['close'], length=10)
      df['ema_med']  = ta.ema(df['close'], length=50)
      df['ema_long'] = ta.ema(df['close'], length=200)
      df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
      
      uptrend = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_long'])
      mult = 2.0
      df['lower_band'] = df['ema_fast'] - (df['atr'] * mult)
      
      df['signal'] = 0
      entry = uptrend.shift(1) & (df['close'].shift(1) >= df['lower_band'].shift(1)) & \
              (df['close'] < df['lower_band'])
      df.loc[entry, 'signal'] = 1
      
      in_position = df['signal'].shift(1) == 1
      exit_sig = in_position & (df['close'] > df['ema_fast'])
      df.loc[exit_sig, 'signal'] = 0
      
      return df['signal']
  ```
- **Risk Considerations:**
  - Multi-indicator risk → potential overfitting; validate out-of-sample
  - ATR multiplier critical; optimize per instrument/timeframe
  - Best on daily or 4H; avoid <1H (too noisy)
  - Triple MA reduces signal frequency; patience required
  - Requires regime-aware optimization (markets shift)

---

