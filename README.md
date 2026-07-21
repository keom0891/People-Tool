# Affected People Risk Dashboard

> **Multi-country platform for historical disaster impact analysis and risk assessment**

![version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)

---

# ✨ Description

The **Affected People Risk Dashboard** is an interactive Streamlit application developed to estimate historical and future disaster impacts on affected populations using **DesInventar** and **EM-DAT** databases.

The application:

- Combines DesInventar and EM-DAT into a single annual historical catalogue.
- Estimates annual affected population.
- Builds Annual Exceedance Curves (AEC).
- Generates synthetic disaster catalogues using Monte Carlo simulation.
- Evaluates three impact scenarios:
  - **Affected**
  - **Affected Poor**
  - **Affected Vulnerable**
- Compares results across multiple countries.

---

# 🎯 Objectives

The dashboard allows users to:

- Analyze historical disaster impacts.
- Integrate multiple disaster databases.
- Estimate annual affected population.
- Generate Annual Exceedance Curves.
- Simulate future disaster catalogues.
- Compare country and regional risk metrics.

---

# 📋 Features

## Country Analysis

- Historical annual affected people
- Annual Exceedance Curve
- Synthetic catalogue simulation
- Summary statistics
- Interactive dashboard

## Regional Comparison

- Interactive regional map
- Country ranking
- Regional statistics
- Scenario comparison

---

# 📂 Required Input Files

## DesInventar

- XML export

Required information:

- Event type
- Event date
- Administrative divisions
- Affected population
- Destroyed dwellings
- Damaged dwellings

## EM-DAT

- Excel (.xlsx)

Required fields:

- ISO Country Code
- Start Year
- Number of Affected

---

# ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/keom0891/People-Tool.git
cd People-Tool
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

---

# ☁️ Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Open **Streamlit Community Cloud**.
3. Click **New app**.
4. Select **keom0891/People-Tool**.
5. Set the main file path to:

```text
app.py
```

6. Click **Deploy**.

---

# 📁 Repository Structure

```text
People-Tool/
│
├── app.py
├── affected_poor_script.py
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

---

# 🛠 Technologies

- Python
- Streamlit
- Pandas
- NumPy
- Plotly
- Matplotlib
- lxml
- openpyxl

---

# 👥 Authors

**Disaster Risk Management Team**  
Inter-American Development Bank (IDB)

Tool development:

- Kenneth Otárola, Andrés Abarca, Ginés Suárez

---

# 📄 License

Copyright © Inter-American Development Bank (IDB).

See the `LICENSE` file for additional information.

---

# 🙏 Acknowledgements

This project uses historical disaster information from:

- DesInventar Disaster Information Management System
- EM-DAT – The International Disaster Database

The dashboard was developed to support disaster risk analysis, resilience planning, and evidence-based decision making across Latin America and the Caribbean.
