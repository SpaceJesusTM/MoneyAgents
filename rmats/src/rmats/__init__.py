"""RMATS: Recursive Multi-Agent Trading System (arXiv 2605.25311).

Pipeline at each monthly rebalance date t:

    data -> signals -> 4 agents propose AgentMessages
         -> Manager aggregates (confidence x health weighted), broadcasts,
            agents re-propose, until ||w_bar^{r+1} - w_bar^r||_2 < eps or r = 3
         -> Risk agent circuit breaker may override
         -> constrained MV optimizer projects w_bar onto constraints
         -> backtest applies weights with transaction costs
"""

__version__ = "0.1.0"
