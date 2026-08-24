# NSE/MCX Premium Terminal — Project Specification (v6)

This repository contains a full-featured deployment structure built natively for **Streamlit** to handle the processing logic defined in the Project Specification (v6) for the **ATM Combined Premium Spike Monitor**.

## 🚀 Key Architectural Implements Covered
- **Strict Baseline Calculation (§3):** Restricts calculation variables to the nearest strike calculated from the *Previous Trading Session Close* ($K = \text{round}(S_{\text{prev}} / \text{strike\_step}) \times \text{strike\_step}$).
- **Day-Locked Watchlist Hold (§4):** Guarantees symbols remain explicitly retained in the alert state for the remaining duration of the trading interval once the threshold triggers ($|\text{Spurt}\%| \ge \text{Threshold}$).
- **Rate-Throttled Loop Handler (§8):** Throttling buffers mapped directly to minimize standard connection exhaustion risks against the Dhan HQ environment.

## 📁 Repository Map Structure
```bash
├── app.py                      # Main Streamlit UI dashboard and logic loop
├── requirements.txt            # Dependency config mapping
├── previous_day_baseline.json  # Persistent baseline state storage register
└── README.md                   # Installation documentation
```

## 🛠️ Step-by-Step Native Installation

1. **Clone the project workspace:**
   ```bash
   git clone https://github.com
   cd dhan-premium-monitor
   ```

2. **Initialize a clean Python virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install exact pinned structural package dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Boot the live stream process frame locally:**
   ```bash
   streamlit run app.py
   ```
