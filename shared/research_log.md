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
  signals_y = df['position_y'].shift(1)
  signals_x = df['position_x'].shift(1)
  ```
- **Risk Considerations:** 
  - Requires transaction cost modeling (slippage, fees) as strategy is sensitive to these
  - Best liquid contracts (lead months) should be used to minimize slippage
  - Hedge ratio may need adjustment for different volatilities/notional values
  - Strategy assumes mean reversion; strong trending regimes can cause losses
  - Lookback period optimization may improve performance