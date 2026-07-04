# AI Browser Tester

This is an AI helper that tests websites by itself. You do not need to write testing scripts. The AI decides what to click and type, looks for errors, and writes a report for you.

---

## How It Works

1. **You enter a website link** in the app.
2. **The AI looks at the page** to understand what the website is for.
3. **The AI makes a plan** to test the site.
4. **The AI uses the browser** to click buttons, fill out forms, and explore the pages.
5. **The AI writes a PDF report** showing what it did and any bugs it found.

---

## How to Setup and Run

### 1. Install Python packages
Open your terminal inside this folder and run:
```bash
./.venv/bin/pip install fastapi uvicorn websockets playwright
```

### 2. Start the App
Run this command to start the web app:
```bash
./.venv/bin/python main.py --ui
```

### 3. Open the Dashboard
Open your web browser and go to:
**http://localhost:8000**

---

## How to Test a Website

1. **Enter the website address** (for example: `https://example.com` or a local file path like `file:///Users/vighneshwarkuru/ai-tester/html/homepage.html`).
2. **Turn on "Show browser window while testing"** if you want to watch the browser work live on your screen.
3. **Click "Analyze & Test Website"**.
4. **Wait for the test to finish**.
5. **Click "View PDF Report"** to see the results and bugs in a clean PDF file.
