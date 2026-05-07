import os
import json
import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ============================================================
# CONFIGURATION — modifie le fichier .env
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MY_USER_ID = int(os.getenv("MY_USER_ID", "0"))
BOT_ALL_CHANNEL_ID = int(os.getenv("BOT_ALL_CHANNEL_ID", "0"))
VINTED_EMAIL = os.getenv("VINTED_EMAIL", "")
VINTED_PASSWORD = os.getenv("VINTED_PASSWORD", "")

# Marques à surveiller
BRANDS = [
    "Ralph Lauren", "Lacoste", "Tommy Hilfiger", "Nike",
    "Carhartt", "Stussy", "CP Company", "Nike ACG",
    "Arc'teryx", "Patagonia", "Jott", "Columbia",
    "Stone Island", "Levi's"
]

# Prix max par marque (None = pas de limite)
MAX_PRICE = {
    "Ralph Lauren": 20,
    "Lacoste": 25,
    "Tommy Hilfiger": 20,
    "Nike": 30,
    "Carhartt": 35,
    "Stussy": 25,
    "CP Company": 50,
    "Nike ACG": 40,
    "Arc'teryx": 80,
    "Patagonia": 40,
    "Jott": 30,
    "Columbia": 25,
    "Stone Island": 60,
    "Levi's": 15,
}

PLAIN_COLORS = {"noir", "blanc", "gris", "beige", "crème", "creme", "marron", "nude"}

# ============================================================
# VINTED API
# ============================================================
VINTED_BASE = "https://www.vinted.fr"
VINTED_API = "https://www.vinted.fr/api/v2"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.vinted.fr/",
    "Origin": "https://www.vinted.fr",
}

# ============================================================
# FAVORIS
# ============================================================
FAVORITES_FILE = "favorites.json"

def load_favorites() -> dict:
    try:
        with open(FAVORITES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_favorites(favs: dict) -> None:
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, indent=2, ensure_ascii=False)

def get_user_favorites(user_id: int) -> dict:
    return load_favorites().get(str(user_id), {})

def set_user_favorites(user_id: int, user_favs: dict) -> None:
    favs = load_favorites()
    favs[str(user_id)] = user_favs
    save_favorites(favs)


class FavoriteBtn(discord.ui.Button):
    def __init__(self, item_id: str, item: dict, brand: str):
        super().__init__(
            label="⭐ Favoriser",
            style=discord.ButtonStyle.secondary,
            custom_id=f"fav_{item_id}",
            row=1,
        )
        self.item_id = item_id
        self.item = item
        self.brand = brand

    async def callback(self, interaction: discord.Interaction):
        user_favs = get_user_favorites(interaction.user.id)
        if self.item_id in user_favs:
            del user_favs[self.item_id]
            self.label = "⭐ Favoriser"
            self.style = discord.ButtonStyle.secondary
            msg = "Retiré de tes favoris."
        else:
            price = self.item.get("price", "?")
            if isinstance(price, dict):
                price = price.get("amount", "?")
            photo = ""
            photos = self.item.get("photos", [])
            if photos:
                photo = photos[0].get("full_size_url") or photos[0].get("url", "")
            user_favs[self.item_id] = {
                "title": self.item.get("title", "?"),
                "price": price,
                "brand": self.brand,
                "size": self.item.get("size_title", "?"),
                "url": f"{VINTED_BASE}/items/{self.item_id}",
                "photo": photo,
            }
            self.label = "💛 Favori"
            self.style = discord.ButtonStyle.success
            msg = "Ajouté à tes favoris !"
        set_user_favorites(interaction.user.id, user_favs)
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(msg, ephemeral=True)


class RemoveFavBtn(discord.ui.Button):
    def __init__(self, item_id: str, user_id: int):
        super().__init__(
            label="🗑 Retirer",
            style=discord.ButtonStyle.danger,
            custom_id=f"unfav_{item_id}_{user_id}",
        )
        self.item_id = item_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        user_favs = get_user_favorites(self.user_id)
        if self.item_id in user_favs:
            del user_favs[self.item_id]
            set_user_favorites(self.user_id, user_favs)
        self.disabled = True
        self.label = "Retiré"
        await interaction.response.edit_message(view=self.view)


# ============================================================
# BOT SETUP
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs déjà envoyés pour éviter les doublons (reset au redémarrage)
sent_ids: set[int] = set()


# ============================================================
# AUTOBUY — Playwright
# ============================================================
async def _dismiss_overlays(page) -> None:
    await page.evaluate("""
        () => {
            ['onetrust-banner-sdk', 'onetrust-pc-dark-filter', 'onetrust-consent-sdk'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.remove();
            });
            document.querySelectorAll('[class*="modal--overlay"], [class*="overlay--"], [data-testid*="modal"]')
                .forEach(el => el.remove());
            document.body.style.overflow = 'auto';
            document.body.style.pointerEvents = 'auto';
        }
    """)


async def vinted_autobuy(item_url: str) -> tuple[bool, str]:
    if not VINTED_EMAIL or not VINTED_PASSWORD:
        return False, "VINTED_EMAIL / VINTED_PASSWORD manquants dans .env"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                locale="fr-FR",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            page = await ctx.new_page()

            # LOGIN via la vraie page d'auth Vinted
            await page.goto(
                "https://www.vinted.fr/member/signup/select_type",
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(2)
            await _dismiss_overlays(page)
            await asyncio.sleep(0.5)

            # Cliquer sur "Continuer avec e-mail"
            email_btn = page.locator('[data-testid="auth-select-type--register-email"]')
            await email_btn.wait_for(state="visible", timeout=10000)
            await email_btn.click()
            await asyncio.sleep(1)

            email_input = page.locator(
                'input[name="email"], input[type="email"], input[autocomplete="email"]'
            ).first
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.fill(VINTED_EMAIL)

            next_btn = page.locator('button[type="submit"]').first
            if await next_btn.is_visible():
                await next_btn.click()
                await asyncio.sleep(1)

            pwd_input = page.locator('input[name="password"], input[type="password"]').first
            await pwd_input.wait_for(state="visible", timeout=10000)
            await pwd_input.fill(VINTED_PASSWORD)

            submit_btn = page.locator('button[type="submit"]').first
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=20000)

            if "/member/signup" in page.url or "select_type" in page.url:
                await browser.close()
                return False, "Échec du login — vérifie ton e-mail / mot de passe dans .env"

            # ACHAT
            await page.goto(item_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await _dismiss_overlays(page)

            buy_btn = page.locator('[data-testid="item-action-buttons-buy-now"]')
            if not await buy_btn.is_visible(timeout=5000):
                await browser.close()
                return False, "Article indisponible à l'achat"
            await buy_btn.click()
            await page.wait_for_load_state("networkidle", timeout=10000)

            confirm_btn = page.locator('[data-testid="checkout-submit-button"]')
            if not await confirm_btn.is_visible(timeout=5000):
                await browser.close()
                return False, "Page de paiement introuvable — méthode de paiement configurée sur Vinted ?"
            await confirm_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            await browser.close()
            return True, "Achat effectué avec succès !"

    except Exception as e:
        return False, f"Erreur inattendue : {e}"


class ConfirmBuyView(discord.ui.View):
    def __init__(self, item_url: str, item_title: str, price: str):
        super().__init__(timeout=60)
        self.item_url = item_url
        self.item_title = item_title
        self.price = price

    @discord.ui.button(label="✅ Confirmer l'achat", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="⏳ Achat en cours...", view=None)
        success, msg = await vinted_autobuy(self.item_url)
        emoji = "✅" if success else "❌"
        await interaction.edit_original_response(content=f"{emoji} {msg}")

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Achat annulé.", view=None)


class AutobuyBtn(discord.ui.Button):
    def __init__(self, item_id: str, item_url: str, item_title: str, price: str):
        super().__init__(
            label="⚡ Autobuy",
            style=discord.ButtonStyle.success,
            custom_id=f"autobuy_{item_id}",
            row=1,
        )
        self.item_url = item_url
        self.item_title = item_title
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        view = ConfirmBuyView(self.item_url, self.item_title, self.price)
        await interaction.response.send_message(
            f"⚡ **Confirmer l'achat ?**\n> {self.item_title}\n> **{self.price} €**",
            view=view,
            ephemeral=True,
        )


# ============================================================
# VINTED HELPERS
# ============================================================
async def get_vinted_cookie(session: aiohttp.ClientSession) -> None:
    try:
        async with session.get(VINTED_BASE, headers=HEADERS) as resp:
            pass
    except Exception:
        pass


async def fetch_items(session: aiohttp.ClientSession, brand: str, max_price: float | None) -> list:
    params = {
        "search_text": brand,
        "catalog_ids": "2050,4",
        "order": "newest_first",
        "per_page": 20,
        "page": 1,
    }
    params["price_to"] = min(max_price, 25) if max_price else 25

    try:
        async with session.get(
            f"{VINTED_API}/catalog/items",
            headers=HEADERS,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                print(f"[ERREUR] fetch_items {brand}: HTTP {resp.status}")
                return []
            data = await resp.json()
            return data.get("items", [])
    except Exception as e:
        print(f"[ERREUR] fetch_items {brand}: {e}")
        return []


async def fetch_resale_price(session: aiohttp.ClientSession, brand: str, title: str, purchase_price: float) -> str:
    keywords = " ".join(title.split()[:3])
    params = {
        "search_text": f"{brand} {keywords}",
        "catalog_ids": "2050,4",
        "order": "relevance",
        "per_page": 20,
        "page": 1,
    }
    try:
        async with session.get(
            f"{VINTED_API}/catalog/items",
            headers=HEADERS,
            params=params,
            timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            if resp.status != 200:
                return f"{purchase_price + 3:.0f} €"
            data = await resp.json()
            items = data.get("items", [])
            prices = []
            for item in items:
                p = item.get("price")
                if isinstance(p, dict):
                    p = p.get("amount")
                try:
                    prices.append(float(p))
                except (ValueError, TypeError):
                    pass
            if not prices:
                return f"{purchase_price + 3:.0f} €"
            # Exclure les valeurs aberrantes (top et bottom 20%)
            prices.sort()
            cut = max(1, len(prices) // 5)
            prices = prices[cut:-cut] if len(prices) > 2 else prices
            market_price = prices[len(prices) // 2]
            resale = max(market_price + 3, purchase_price + 3)
            return f"{resale:.0f} €"
    except Exception:
        return f"{purchase_price + 3:.0f} €"


def is_interesting(item: dict) -> bool:
    if item.get("favourite_count", 0) < 2:
        return False
    color = (item.get("color1") or "").lower().strip()
    if color and color in PLAIN_COLORS:
        return False
    return True


def get_price(item: dict) -> float:
    p = item.get("price", 9999)
    if isinstance(p, dict):
        p = p.get("amount", 9999)
    try:
        return float(p)
    except (ValueError, TypeError):
        return 9999


# ============================================================
# EMBED + BOUTONS
# ============================================================
def build_embed(item: dict, brand: str, resale_price: str = "N/A") -> discord.Embed:
    title = item.get("title", "Article sans titre")
    raw_price = item.get("price", "?")
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount", "?")
    condition = item.get("status", "?")
    size = item.get("size_title", "?")
    item_url = f"{VINTED_BASE}/items/{item.get('id')}"
    created_at = item.get("created_at_ts", "")

    if created_at:
        try:
            dt = datetime.fromtimestamp(int(created_at))
            time_str = f"Aujourd'hui à {dt.strftime('%H:%M')}"
        except Exception:
            time_str = "Récemment"
    else:
        time_str = "Récemment"

    embed = discord.Embed(title=title, url=item_url, color=0x1a73e8)
    embed.add_field(name="⏱ Publié", value=time_str, inline=False)
    embed.add_field(name="🏷 Marque", value=brand, inline=True)
    embed.add_field(name="📐 Taille", value=size, inline=True)
    embed.add_field(name="💎 État", value=condition.replace("_", " ").title(), inline=True)
    embed.add_field(name="💰 Prix achat", value=f"{raw_price} €", inline=True)
    embed.add_field(name="📈 Prix revente", value=resale_price, inline=True)
    embed.set_footer(text="🏷️ Vinted Lab | hilote")

    photos = item.get("photos", [])
    if photos:
        embed.set_image(url=photos[0].get("full_size_url") or photos[0].get("url", ""))

    return embed


def build_buttons(item: dict, brand: str) -> discord.ui.View:
    item_id = str(item.get("id"))
    item_url = f"{VINTED_BASE}/items/{item_id}"
    raw_price = item.get("price", "?")
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount", "?")

    view = discord.ui.View(timeout=86400)  # 24h
    view.add_item(discord.ui.Button(label="📄 Détails", style=discord.ButtonStyle.secondary, url=item_url, row=0))
    view.add_item(discord.ui.Button(label="🛒 Acheter", style=discord.ButtonStyle.primary, url=item_url, row=0))
    view.add_item(discord.ui.Button(label="💬 Négocier", style=discord.ButtonStyle.secondary, url=f"{VINTED_BASE}/items/{item_id}/want_it/new", row=0))
    view.add_item(FavoriteBtn(item_id=item_id, item=item, brand=brand))
    view.add_item(AutobuyBtn(item_id=item_id, item_url=item_url, item_title=item.get("title", "?"), price=str(raw_price)))
    return view


# ============================================================
# COMMANDE !botall
# ============================================================
@bot.command(name="botall")
async def botall(ctx: commands.Context):
    if ctx.author.id != MY_USER_ID:
        await ctx.message.delete()
        return

    channel = bot.get_channel(BOT_ALL_CHANNEL_ID) or ctx.channel
    await ctx.send("🔍 Recherche des meilleures annonces Vinted en cours...", delete_after=5)

    async with aiohttp.ClientSession() as session:
        await get_vinted_cookie(session)

        total_sent = 0
        for brand in BRANDS:
            max_p = MAX_PRICE.get(brand)
            items = await fetch_items(session, brand, max_p)

            new_items = [i for i in items if i.get("id") not in sent_ids and is_interesting(i)]
            new_items.sort(key=get_price)

            for item in new_items[:3]:
                item_id = item.get("id")
                sent_ids.add(item_id)

                resale = await fetch_resale_price(session, brand, item.get("title", ""), get_price(item))
                embed = build_embed(item, brand, resale)
                buttons = build_buttons(item, brand)

                try:
                    await channel.send(embed=embed, view=buttons)
                    total_sent += 1
                    await asyncio.sleep(20)
                except Exception as e:
                    print(f"[ERREUR] Envoi annonce {item_id}: {e}")

    await ctx.send(f"✅ {total_sent} annonces envoyées !", delete_after=10)


# ============================================================
# COMMANDE !favoris
# ============================================================
@bot.tree.command(name="favoris", description="Voir tes favoris")
async def favoris(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_favs = get_user_favorites(interaction.user.id)
    if not user_favs:
        await interaction.followup.send("Aucun favori enregistré.", ephemeral=True)
        return

    await interaction.followup.send(f"⭐ **{len(user_favs)} favori(s) :**", ephemeral=True)

    for item_id, data in list(user_favs.items()):
        embed = discord.Embed(
            title=data.get("title", "?"),
            url=data.get("url", ""),
            color=0xFFD700
        )
        embed.add_field(name="🏷 Marque", value=data.get("brand", "?"), inline=True)
        embed.add_field(name="📐 Taille", value=data.get("size", "?"), inline=True)
        embed.add_field(name="💰 Prix", value=f"{data.get('price', '?')} €", inline=True)
        embed.set_footer(text="🏷️ Vinted Lab | favoris")
        if data.get("photo"):
            embed.set_image(url=data["photo"])

        view = discord.ui.View(timeout=300)
        view.add_item(discord.ui.Button(label="🔗 Voir sur Vinted", style=discord.ButtonStyle.secondary, url=data.get("url", "")))
        view.add_item(RemoveFavBtn(item_id=item_id, user_id=interaction.user.id))

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await asyncio.sleep(0.3)


# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")
    print(f"   Salon : #bot-all ({BOT_ALL_CHANNEL_ID})")
    print(f"   Marques : {', '.join(BRANDS)}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="les meilleures deals Vinted 🔥"
        )
    )


# ============================================================
# LANCEMENT
# ============================================================
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
