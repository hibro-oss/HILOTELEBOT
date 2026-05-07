import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible pour voir ce qui se passe
        page = await browser.new_page(locale="fr-FR")

        print("Ouverture de la page de login Vinted...")
        await page.goto("https://www.vinted.fr/login", wait_until="networkidle")
        await asyncio.sleep(2)

        print("\n=== INPUTS trouvés ===")
        inputs = await page.locator("input").all()
        for inp in inputs:
            attrs = {}
            for attr in ["id", "name", "type", "placeholder", "data-testid", "autocomplete"]:
                val = await inp.get_attribute(attr)
                if val:
                    attrs[attr] = val
            print(attrs)

        print("\n=== BOUTONS trouvés ===")
        buttons = await page.locator("button").all()
        for btn in buttons:
            attrs = {}
            for attr in ["type", "data-testid", "id"]:
                val = await btn.get_attribute(attr)
                if val:
                    attrs[attr] = val
            text = await btn.inner_text()
            attrs["text"] = text.strip()[:50]
            print(attrs)

        input("\nAppuie sur Entrée pour fermer...")
        await browser.close()

asyncio.run(main())
