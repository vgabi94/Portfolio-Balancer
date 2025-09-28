# Portfolio-Balancer
Portfolio Balancer is a desktop app for managing investment portfolios in Python with a modern PySide6 GUI.  
This app was **vibe coded** with Perplexity, powered by **Grok 4**.  
Key features:
- Add, edit, and remove holdings with live prices via yfinance.
- Set and track target allocations, see deviations, and sort your data.
- Get investment, rebalancing, and reallocation suggestions.
- Save/load portfolios (JSON), with undo/redo.
- Dark theme, interactive/resizable tables, and status bar alerts.
- Ideal for investors seeking intuitive, actionable portfolio management.

## Installation

1. **Clone the repository**
```
git clone https://github.com/your-username/portfolio-balancer.git
cd portfolio-balancer
```

2. **Install the requirements**
```
pip install -r requirements.txt
```

3. **Start the application**
```
python portfolio_balancer.pyw
```
Or double-click `portfolio_balancer.pyw` to start it.

## Notes
- **Python 3.8+ is required.**
- Internet connection is needed for fetching live prices.
- All data is stored locally; no external data is sent or stored.
