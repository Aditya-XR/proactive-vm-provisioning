"""Save dashboard screenshots for the report, using the installed Chrome.

Needs a running dashboard: streamlit run dashboard/app.py --server.port 8765
Needs: pip install playwright
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

FIGURES = Path(__file__).parent.parent / "figures"
TABS = {
    "Workload patterns": "dash_workload.png",
    "Predictions": "dash_predictions.png",
    "VM provisioning": "dash_provisioning.png",
    "Resource utilization": "dash_utilization.png",
    "Policy comparison": "dash_comparison.png",
}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1400})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8765", wait_until="networkidle")
    page.get_by_role("tab", name="Workload patterns").wait_for(timeout=60000)
    page.wait_for_timeout(3000)
    for name, file in TABS.items():
        page.get_by_role("tab", name=name).click()
        page.wait_for_timeout(3000)
        page.screenshot(path=FIGURES / file, clip={"x": 0, "y": 90, "width": 1500, "height": 1250})
        alerts = page.locator('[data-testid="stException"]').count()
        print(name, "exceptions on page:", alerts)
    print("page errors:", errors)
    browser.close()
