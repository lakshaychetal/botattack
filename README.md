# 🤖 BotAttack — Shopify COD Order Bot

<p align="center">
  <strong>Professional automated bot for placing Cash on Delivery (COD) orders on Shopify stores using the EasySell COD Form API.</strong>
</p>

---

## ⚡ Features

| Feature | Description |
|---------|-------------|
| 🎯 **EasySell Engine** | Reverse-engineered EasySell COD Form API for direct order submission |
| 🔍 **Store Scanner** | Auto-detects products, variants, Shopify domain, and EasySell presence |
| 🛒 **Full COD Flow** | Visit page → Add to cart → Generate hash → Submit via EasySell API |
| 👤 **Identity Generator** | Realistic Indian customer profiles (names, addresses, phones, 8 states) |
| 🛡️ **Anti-Detection** | Random User-Agents, request delays, HTTP/2, browser-like headers |
| 🌐 **Proxy Support** | HTTP/SOCKS5 proxy rotation for IP masking |
| 📊 **Results Export** | CSV export with order IDs, tracking URLs, and status |
| 🎨 **Professional CLI** | Beautiful Rich terminal UI with menus, tables, panels |
| ⚙️ **Configurable** | YAML configuration for all settings |
| 🔄 **Retry Logic** | Automatic retries with fresh identities on failure |
| 📦 **Batch Orders** | Place multiple orders with randomized delays |

---

## 📋 Requirements

- Python 3.9+
- pip (Python package manager)

---

## 🚀 Quick Start

### 1. Setup

```bash
cd botattack

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure (Optional)

Edit `config.yaml` to customize:
- Order quantity and count
- Customer identity pools (8 Indian states pre-configured)
- Proxy settings
- Delay timings
- Output paths

### 3. Run

```bash
python main.py
```

---

## 🎮 Usage Modes

### Mode 1: Target Product 🎯 (Recommended)
Enter a direct product URL → Bot fetches product & store info → Select variant → Orders placed!

```
Select option: 1
Product URL: https://store.com/products/some-product
```

### Mode 2: Quick Attack 🚀
Enter a store URL → Bot scans all products → Select product → Enter order count → Go!

```
Select option: 2
Store URL: https://store.com
```

### Mode 3: Store Scanner 🔍
Scan any Shopify store to view all products, prices, variants, and EasySell status.

```
Select option: 3
Store URL: https://store.com
```

### Mode 4: Settings ⚙️
View current configuration (delays, proxies, identity pools, etc.)

---

## 🔧 How It Works

The bot targets Shopify stores using the **EasySell COD Form** app. The flow:

1. **Fetch Product** — Gets product data via `/products/{handle}.json`
2. **Detect Store** — Extracts `Shopify.shop` domain and EasySell config from page HTML
3. **Add to Cart** — `POST /cart/add.js` with variant ID
4. **Get Cart** — `GET /cart.js` to verify items
5. **Generate Hash** — Replicates EasySell's `generateUniqueId()` (timestamp + UA hash + random)
6. **Submit Order** — `POST https://load.tyslo.com/order/new` with full COD form data
7. **Track Result** — Parses order ID, number, status URL from response

---

## 📁 Project Structure

```
botattack/
├── main.py              # Entry point
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── bot/
│   ├── __init__.py
│   ├── config.py        # YAML config + Pydantic models
│   ├── scraper.py       # Product & store info scraper
│   ├── checkout.py      # EasySell COD checkout engine
│   ├── identity.py      # Indian identity generator
│   ├── stealth.py       # Anti-detection HTTP client
│   ├── manager.py       # Batch order orchestration
│   ├── cli.py           # Rich CLI interface
│   └── logger.py        # Logging setup
├── logs/                # Log files
└── results/             # CSV order results
```

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. The author is not responsible for any misuse. Using this tool against stores without permission may violate terms of service.
