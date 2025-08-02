# Accumulator Strategy Decision Engine

## Overview

The Accumulator Strategy Decision Engine is a sophisticated automated trading system designed to maximize long-term profitability through systematic market analysis and parameter optimization. The engine monitors trading performance and automatically switches between different market indices when drawdowns are detected.

## Key Features

### 🧠 Intelligent Decision Making
- **Loss Streak Monitoring**: Automatically tracks consecutive losses
- **Market Analysis**: Real-time volatility and return calculations
- **Index Selection**: Ranks all available indices by risk-return scores
- **Parameter Scaling**: Dynamic adjustment based on market volatility

### ⚡ Real-Time Operations
- **Protocol A**: Standard trading with loss streak tracking
- **Protocol B**: Automated drawdown response and index switching
- **Emergency Halts**: Single-trade loss protection
- **Confirmation System**: Admin approval for parameter changes

### 📊 Advanced Analytics
- **Volatility Reference**: Stable baseline for scaling calculations
- **Meta-Learning**: Historical performance data collection
- **Market Metrics**: Mean return, volatility, risk-return scores
- **Live Monitoring**: JSON status updates every 3 seconds

## System Architecture

### Core Components

1. **AccumulatorDecisionEngine**: Main engine class
2. **DecisionEngineState**: State management and persistence
3. **MarketMetrics**: Market analysis data structures
4. **ProtocolState**: Current operational state tracking

### Integration Points

- **TradingState**: Integrated with existing trading system
- **DerivAPI**: Market data fetching and analysis
- **Telegram Bot**: Admin notifications and confirmations
- **Persistent Storage**: JSON-based state and data storage

## Configuration Parameters

### Core Strategy Parameters

```python
BASE_GROWTH_RATE = 1.0      # Foundational growth rate (%)
BASE_TAKE_PROFIT = 1.5      # Foundational take-profit level (%)
LOSS_THRESHOLD = 10         # Consecutive losses trigger threshold
N_PERIODS = 1800           # Market data lookback period
LIQUIDITY_MIN_VOLUME = 1000 # Minimum volume requirement
```

### Volatility Scaling Parameters

```python
G_EXPONENT = 0.5    # Growth rate scaling exponent
P_EXPONENT = 0.5    # Take profit scaling exponent
G_MIN = 0.1         # Minimum growth scaling factor
G_MAX = 5.0         # Maximum growth scaling factor
P_MIN = 0.1         # Minimum profit scaling factor
P_MAX = 5.0         # Maximum profit scaling factor
```

### Safety Parameters

```python
CONFIRM_TIMEOUT = 15    # Admin confirmation timeout (seconds)
DRAW_LIMIT = 10.0      # Single trade loss limit multiplier
SANITY_FACTOR = 5      # Emergency threshold increase
```

## Operational Protocols

### Protocol A: Standard Trading

1. **Trade Execution**: Place trade with current parameters
2. **Outcome Tracking**: Monitor win/loss results
3. **Loss Streak Update**: 
   - Win: Reset streak to 0
   - Loss: Increment streak by 1
4. **Threshold Check**: If streak >= LOSS_THRESHOLD, trigger Protocol B

### Protocol B: Drawdown Response

#### Analysis Phase
1. **Universe Analysis**: Fetch market data for all indices
2. **Metric Calculation**: Compute volatility, mean return, risk-return scores
3. **Filtering**: Remove indices below liquidity/quality thresholds
4. **Ranking**: Sort by risk-return score (descending)

#### Selection Phase
1. **Best Index**: Select top-ranked index
2. **Contingency**: If no qualified indices, increase threshold temporarily

#### Parameter Scaling Phase
1. **Volatility Ratio**: Calculate σ_reference / σ_new
2. **Scaling Factors**: 
   - α_growth = (vol_ratio)^G_EXPONENT
   - α_profit = (vol_ratio)^P_EXPONENT
3. **Clamping**: Apply min/max boundaries
4. **New Parameters**:
   - growth_rate = BASE_GROWTH_RATE × α_growth
   - take_profit = BASE_TAKE_PROFIT × α_profit

#### Confirmation & Execution Phase
1. **Admin Alert**: Send detailed proposal via Telegram
2. **Response Handling**:
   - "yes": Execute switch
   - "no": Reject and reset
   - timeout: Auto-execute
3. **State Update**: Apply new parameters and reset loss streak
4. **Audit Logging**: Record switch for meta-learning

## Emergency Systems

### Single Trade Guardrail
- **Trigger**: Loss > DRAW_LIMIT × take_profit × stake
- **Action**: Immediate halt, high-priority admin alert
- **Recovery**: Manual intervention required

### Contingency Actions
- **Trigger**: No qualified indices in universe analysis
- **Action**: Temporarily increase LOSS_THRESHOLD by SANITY_FACTOR
- **Effect**: Continue with current parameters, extended tolerance

## Command Interface

### Core Commands

```
start trading          # Begin trading with decision engine
stop trading          # Stop trading and reset
engine status         # Detailed engine status
bot thinking          # JSON monitoring display
resume halt           # Resume from emergency halt
```

### Confirmation Commands

```
yes                   # Confirm proposed parameter switch
no                    # Reject proposed parameter switch
```

## Data Storage

### Engine State File
```json
{
  "active_index": "1HZ100V",
  "active_growth_rate": 1.2,
  "active_take_profit": 1.8,
  "loss_streak": 3,
  "protocol_state": "standard_trading",
  "sigma_reference": 0.00012,
  "total_switches": 5
}
```

### Meta-Learning Data
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "triggering_loss_streak": 10,
  "index_old": "R_100",
  "index_new": "1HZ100V",
  "sigma_ref": 0.00012,
  "sigma_new": 0.00015,
  "growth_rate_new": 1.2,
  "take_profit_new": 1.8,
  "pnl_next_100_trades": 15.67
}
```

## Monitoring & Status

### JSON Status Output
```json
{
  "timestamp": "2024-01-15T10:30:21Z",
  "active_index": "1HZ100V",
  "loss_streak": 3,
  "analysis_in_progress": false,
  "market_metrics": {
    "σ_reference": 0.00012,
    "σ_active": 0.00015,
    "μ_active": 0.00001,
    "R_score_active": 0.0667
  },
  "proposed_params": {
    "index": null,
    "growth_rate": null,
    "take_profit": null
  },
  "protocol_state": "standard_trading",
  "total_switches": 5
}
```

## Performance Optimization

### Market Data Caching
- **Cache Duration**: 5 minutes per symbol
- **Efficiency**: Reduces API calls during analysis
- **Freshness**: Automatic cache invalidation

### Concurrent Analysis
- **Parallel Processing**: All indices analyzed simultaneously
- **Timeout Handling**: 30-second API timeouts
- **Error Recovery**: Graceful handling of failed analyses

### Meta-Learning Pipeline
- **Data Collection**: Every switch logged automatically
- **Retrospective Analysis**: 100-trade performance windows
- **Optimization**: Periodic parameter tuning recommendations

## Integration Example

```python
# Initialize the decision engine
decision_engine = AccumulatorDecisionEngine(api, telegram_bot=bot)

# Start monitoring
await decision_engine.start_monitoring()

# Handle trade completion
result = await decision_engine.on_trade_completed(
    profit_loss=-0.5,
    stake=1.0
)

# Check for halts or parameter updates
if result.get("halt"):
    # Handle emergency halt
    pass
else:
    # Update trading parameters if changed
    new_params = decision_engine.get_current_parameters()
```

## Safety Considerations

### Risk Management
- **Position Sizing**: Controlled by existing stake management
- **Loss Limits**: Both per-trade and cumulative protections
- **Market Exposure**: Limited to approved index universe

### Operational Safety
- **State Persistence**: All critical state saved continuously
- **Admin Oversight**: Human confirmation for major changes
- **Emergency Controls**: Multiple halt mechanisms

### Data Integrity
- **Atomic Operations**: State changes are transaction-safe
- **Backup Systems**: Multiple data persistence layers
- **Error Recovery**: Graceful degradation on failures

## Troubleshooting

### Common Issues

1. **"No reference volatility"**: Engine needs time to initialize with first index
2. **"No qualified indices"**: Market conditions may be extreme, contingency mode activated
3. **"Confirmation timeout"**: Admin didn't respond, switch auto-executed
4. **"Emergency halt"**: Single trade exceeded loss limits, manual intervention needed

### Recovery Procedures

1. **State Corruption**: Delete state files, engine will reinitialize
2. **Market Data Issues**: Check API connectivity, wait for cache refresh
3. **Parameter Lockup**: Use "resume halt" command to reset
4. **Performance Issues**: Review meta-learning data for optimization opportunities

## Future Enhancements

### Planned Features
- **Machine Learning**: Advanced parameter optimization
- **Multi-Asset**: Cross-asset correlation analysis
- **Regime Detection**: Market regime classification
- **Portfolio Theory**: Multi-index portfolio allocation

### Optimization Opportunities
- **Neural Networks**: Pattern recognition in market data
- **Genetic Algorithms**: Parameter space exploration
- **Reinforcement Learning**: Adaptive strategy evolution
- **Ensemble Methods**: Multiple strategy combinations

---

*This decision engine represents a significant advancement in automated trading systems, combining rigorous risk management with sophisticated market analysis to deliver consistent, long-term profitability.* 