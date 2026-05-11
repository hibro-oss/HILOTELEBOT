import os
import json
import base64
import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import anthropic

load_dotenv()

# ============================================================
# CONFIGURATION — modifie le fichier .env
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MY_USER_ID = int(os.getenv("MY_USER_ID", "0"))

def is_authorized(user_id: int) -> bool:
    return user_id == MY_USER_ID
BOT_ALL_CHANNEL_ID  = 1488256072115552266
NIKE_CHANNEL_ID     = 1488256133662507148
CP_CHANNEL_ID       = 1488256358296977480
TRAP_CHANNEL_ID     = 1501991028339773450
STUSSY_CHANNEL_ID   = 1488256329632972842
RALPH_CHANNEL_ID    = 1488256201069301992
JOTT_CHANNEL_ID     = 1488256281470042192
NORTH_CHANNEL_ID    = 1488256216625975387
CARHARTT_CHANNEL_ID = 1488256273182097548
LACOSTE_CHANNEL_ID  = 1488256305033511033
SNEAKERS_CHANNEL_ID = 1488256310213607616
TOMMY_CHANNEL_ID    = 1488256351586222233
STONE_CHANNEL_ID    = 1488256330593468497
CORTEIZ_CHANNEL_ID  = 1488256344686592090
ADIDAS_CHANNEL_ID   = 1488256352697454723
LEVIS_CHANNEL_ID    = 1502645392523923486
ACCESSOIRES_CHANNEL_ID = 1502657767024890016
TIPS_CHANNEL_ID     = 1488998641380102336
HELP_CHANNEL_ID     = 0
VINTED_EMAIL = os.getenv("VINTED_EMAIL", "")
VINTED_PASSWORD = os.getenv("VINTED_PASSWORD", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Marques à surveiller
BRANDS = [
    "Ralph Lauren", "Lacoste", "Tommy Hilfiger", "Nike",
    "Carhartt", "Stussy", "CP Company", "Nike ACG",
    "Arc'teryx", "Patagonia", "Jott", "Columbia",
    "Stone Island", "Levi's", "Trapstar", "The North Face", "Corteiz", "Adidas"
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
    "Trapstar": 40,
    "The North Face": 45,
    "Corteiz": 50,
    "Adidas": 30,
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

# Tâches en cours par salon (pour pouvoir les arrêter)
running_tasks: dict[str, asyncio.Task] = {}

# Limiteur global — 1 seule requête Vinted à la fois
vinted_sem = asyncio.Semaphore(1)


async def monitor_brand(channel: discord.TextChannel, brand: str, max_price: float | None, apply_filter: bool = False):
    """Boucle infinie : récupère et envoie les nouvelles annonces d'une marque toutes les 30s."""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await get_vinted_cookie(session)
                items = await fetch_items(session, brand, max_price)

            new_items = [i for i in items if i.get("id") not in sent_ids]
            if apply_filter:
                new_items = [i for i in new_items if is_interesting(i)]
            new_items.sort(key=get_price)

            for item in new_items:
                if apply_filter:
                    purchase_price = get_price(item)
                    async with aiohttp.ClientSession() as session:
                        market = await fetch_market_price(session, brand, item.get("title", ""))
                    if market and purchase_price >= market * 0.90:
                        sent_ids.add(item.get("id"))
                        continue
                else:
                    async with aiohttp.ClientSession() as session:
                        market = await fetch_market_price(session, brand, item.get("title", ""))

                item_id = item.get("id")
                sent_ids.add(item_id)

                embed = build_embed(item, brand, market)
                buttons = build_buttons(item, brand)

                try:
                    await channel.send(embed=embed, view=buttons)
                except Exception as e:
                    print(f"[ERREUR] Envoi {brand} {item_id}: {e}")

                await asyncio.sleep(8)

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[ERREUR] monitor_brand {brand}: {e}")

        await asyncio.sleep(60)


async def start_monitor(ctx: commands.Context, key: str, channel: discord.TextChannel, brand: str, max_price: float | None, apply_filter: bool = False):
    if key in running_tasks and not running_tasks[key].done():
        await ctx.send(f"⚠️ La recherche **{brand}** tourne déjà ! Fais `!stop` pour l'arrêter.", delete_after=8)
        return

    task = asyncio.create_task(monitor_brand(channel, brand, max_price, apply_filter))
    running_tasks[key] = task
    await ctx.send(f"✅ Recherche **{brand}** lancée en continu dans {channel.mention} !", delete_after=8)


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
        async with vinted_sem:
            async with session.get(VINTED_BASE, headers=HEADERS) as resp:
                pass
            await asyncio.sleep(1)
    except Exception:
        pass


async def _vinted_get(session: aiohttp.ClientSession, url: str, params: dict, timeout: int = 10) -> dict | None:
    """Requête Vinted avec limiteur global et retry automatique sur 429."""
    for attempt in range(3):
        try:
            async with vinted_sem:
                async with session.get(url, headers=HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 429:
                        wait = 30 * (attempt + 1)
                        print(f"[429] Rate limit Vinted — pause {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                await asyncio.sleep(2)
            return data
        except Exception as e:
            print(f"[ERREUR] _vinted_get: {e}")
            await asyncio.sleep(5)
    return None


async def fetch_items(session: aiohttp.ClientSession, brand: str, max_price: float | None) -> list:
    params = {
        "search_text": brand,
        "catalog_ids": "2050,4",
        "order": "newest_first",
        "per_page": 20,
        "page": 1,
        "price_to": max_price if max_price else 25,
    }
    data = await _vinted_get(session, f"{VINTED_API}/catalog/items", params)
    return data.get("items", []) if data else []


async def fetch_market_price(session: aiohttp.ClientSession, brand: str, title: str) -> float | None:
    keywords = " ".join(title.split()[:3])
    params = {
        "search_text": f"{brand} {keywords}",
        "catalog_ids": "2050,4",
        "order": "relevance",
        "per_page": 20,
        "page": 1,
    }
    data = await _vinted_get(session, f"{VINTED_API}/catalog/items", params, timeout=8)
    if not data:
        return None
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
        return None
    prices.sort()
    cut = max(1, len(prices) // 5)
    prices = prices[cut:-cut] if len(prices) > 2 else prices
    return prices[len(prices) // 2]


SNEAKER_BRANDS = [
    "Nike", "Jordan", "Adidas", "New Balance", "Puma", "Reebok",
    "Asics", "Vans", "Converse", "Salomon", "On Running", "Saucony",
    "Air Max", "Yeezy", "Dunk", "Air Force"
]

MAX_SNEAKER_PRICE = 80

async def fetch_sneakers(session: aiohttp.ClientSession, search: str) -> list:
    params = {
        "search_text": search,
        "catalog_ids": "305,16",
        "order": "newest_first",
        "per_page": 20,
        "page": 1,
        "price_to": MAX_SNEAKER_PRICE,
    }
    data = await _vinted_get(session, f"{VINTED_API}/catalog/items", params)
    return data.get("items", []) if data else []


async def monitor_sneakers(channel: discord.TextChannel):
    """Boucle infinie : tourne sur toutes les marques de sneakers."""
    while True:
        try:
            for brand in SNEAKER_BRANDS:
                async with aiohttp.ClientSession() as session:
                    await get_vinted_cookie(session)
                    items = await fetch_sneakers(session, brand)

                new_items = [i for i in items if i.get("id") not in sent_ids]
                new_items.sort(key=get_price)

                for item in new_items:
                    item_id = item.get("id")
                    sent_ids.add(item_id)

                    async with aiohttp.ClientSession() as session:
                        market = await fetch_market_price(session, brand, item.get("title", ""))

                    embed = build_embed(item, brand, market)
                    buttons = build_buttons(item, brand)

                    try:
                        await channel.send(embed=embed, view=buttons)
                    except Exception as e:
                        print(f"[ERREUR] Envoi sneakers {item_id}: {e}")

                    await asyncio.sleep(8)

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[ERREUR] monitor_sneakers: {e}")

        await asyncio.sleep(60)


TIPS_SEARCHES = [
    "pochette Louis Vuitton",
    "pochette Gucci",
    "pochette Prada",
    "pochette Burberry",
    "ceinture Louis Vuitton",
    "ceinture Gucci",
    "ceinture Hermès",
    "ceinture Lacoste",
    "ceinture Ralph Lauren",
    "maroquinerie Louis Vuitton",
    "sac bandoulière Stone Island",
    "banane Supreme",
    "casquette New Era",
    "casquette Stussy",
    "bonnet Carhartt",
    "lunettes Ray-Ban",
    "lunettes Oakley",
    "montre G-Shock",
    "écharpe Burberry",
    "écharpe Stone Island",
]

MAX_TIPS_PRICE = 80

async def fetch_tips(session: aiohttp.ClientSession, search: str) -> list:
    params = {
        "search_text": search,
        "catalog_ids": "1904,2",
        "order": "newest_first",
        "per_page": 20,
        "page": 1,
        "price_to": MAX_TIPS_PRICE,
    }
    data = await _vinted_get(session, f"{VINTED_API}/catalog/items", params)
    return data.get("items", []) if data else []


async def monitor_tips(channel: discord.TextChannel):
    """Boucle infinie : envoie les accessoires de marque trouvés sur Vinted."""
    while True:
        try:
            for search in TIPS_SEARCHES:
                async with aiohttp.ClientSession() as session:
                    await get_vinted_cookie(session)
                    items = await fetch_tips(session, search)

                new_items = [i for i in items if i.get("id") not in sent_ids]
                new_items.sort(key=get_price)

                for item in new_items:
                    item_id = item.get("id")
                    sent_ids.add(item_id)

                    title = item.get("title", "Article sans titre")
                    raw_price = item.get("price", "?")
                    if isinstance(raw_price, dict):
                        raw_price = raw_price.get("amount", "?")
                    item_url = f"{VINTED_BASE}/items/{item_id}"

                    embed = discord.Embed(
                        title=title,
                        url=item_url,
                        color=0xFFD700,
                    )
                    embed.add_field(name="💰 Prix", value=f"{raw_price} €", inline=True)
                    embed.add_field(name="📐 Taille", value=item.get("size_title", "Unique"), inline=True)
                    embed.add_field(name="💎 État", value=(item.get("status") or "?").replace("_", " ").title(), inline=True)

                    photos = item.get("photos", [])
                    if photos:
                        embed.set_image(url=photos[0].get("full_size_url") or photos[0].get("url", ""))
                    embed.set_footer(text="🏷️ Vinted Lab | Tips Accessoires")

                    view = discord.ui.View(timeout=86400)
                    view.add_item(discord.ui.Button(label="📄 Voir", style=discord.ButtonStyle.secondary, url=item_url))
                    view.add_item(discord.ui.Button(label="🛒 Acheter", style=discord.ButtonStyle.primary, url=item_url))

                    try:
                        await channel.send(embed=embed, view=view)
                    except Exception as e:
                        print(f"[ERREUR] Envoi tips {item_id}: {e}")

                    await asyncio.sleep(8)

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[ERREUR] monitor_tips: {e}")

        await asyncio.sleep(60)


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
def build_embed(item: dict, brand: str, market_price: float | None = None) -> discord.Embed:
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

    if market_price is not None:
        try:
            purchase = float(raw_price)
            marge = market_price - purchase
            suggested = market_price * 1.10
            embed.add_field(name="📊 Prix marché", value=f"{market_price:.0f} €", inline=True)
            embed.add_field(name="💸 Marge", value=f"+{marge:.0f} € ({marge / market_price * 100:.0f}%)", inline=True)
            embed.add_field(name="🏷 Prix suggéré", value=f"{suggested:.0f} €", inline=True)
        except (ValueError, TypeError):
            embed.add_field(name="📊 Prix marché", value=f"{market_price:.0f} €", inline=True)

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
# COMMANDES DE RECHERCHE CONTINUE
# ============================================================
BRANDS_SALON_DEDIE = {"Nike", "CP Company", "Trapstar", "Stussy", "Ralph Lauren", "Jott", "The North Face", "Carhartt", "Lacoste", "Tommy Hilfiger", "Stone Island", "Corteiz", "Adidas", "Levi's"}

@bot.command(name="hiloteall")
async def hiloteall(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    channel = bot.get_channel(BOT_ALL_CHANNEL_ID) or ctx.channel
    for brand in [b for b in BRANDS if b not in BRANDS_SALON_DEDIE]:
        key = f"hiloteall_{brand}"
        if key not in running_tasks or running_tasks[key].done():
            task = asyncio.create_task(monitor_brand(channel, brand, MAX_PRICE.get(brand), apply_filter=True))
            running_tasks[key] = task
    await ctx.send(f"✅ Recherche **toutes marques** lancée en continu dans {channel.mention} !", delete_after=8)


@bot.command(name="nike")
async def nike(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != NIKE_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Nike !", delete_after=5)
        return
    await start_monitor(ctx, "nike", ctx.channel, "Nike", MAX_PRICE.get("Nike"))


@bot.command(name="cp")
async def cp(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != CP_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon CP Company !", delete_after=5)
        return
    await start_monitor(ctx, "cp", ctx.channel, "CP Company", MAX_PRICE.get("CP Company"))


@bot.command(name="trap")
async def trap(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != TRAP_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Trapstar !", delete_after=5)
        return
    await start_monitor(ctx, "trap", ctx.channel, "Trapstar", MAX_PRICE.get("Trapstar"))


@bot.command(name="stussy")
async def stussy(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != STUSSY_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Stussy !", delete_after=5)
        return
    await start_monitor(ctx, "stussy", ctx.channel, "Stussy", MAX_PRICE.get("Stussy"))


@bot.command(name="ralph")
async def ralph(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != RALPH_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Ralph Lauren !", delete_after=5)
        return
    await start_monitor(ctx, "ralph", ctx.channel, "Ralph Lauren", MAX_PRICE.get("Ralph Lauren"))


@bot.command(name="jott")
async def jott(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != JOTT_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Jott !", delete_after=5)
        return
    await start_monitor(ctx, "jott", ctx.channel, "Jott", MAX_PRICE.get("Jott"))


@bot.command(name="tips")
async def tips(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != TIPS_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Tips !", delete_after=5)
        return
    if "tips" in running_tasks and not running_tasks["tips"].done():
        await ctx.send("⚠️ La recherche Tips tourne déjà ! Fais `!stop` pour l'arrêter.", delete_after=8)
        return
    task = asyncio.create_task(monitor_tips(ctx.channel))
    running_tasks["tips"] = task
    await ctx.send(f"✅ Recherche **Tips Accessoires** lancée en continu dans {ctx.channel.mention} !", delete_after=8)


@bot.command(name="levis")
async def levis(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != LEVIS_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Levi's !", delete_after=5)
        return
    await start_monitor(ctx, "levis", ctx.channel, "Levi's", MAX_PRICE.get("Levi's"))


@bot.command(name="adidas")
async def adidas(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != ADIDAS_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Adidas !", delete_after=5)
        return
    await start_monitor(ctx, "adidas", ctx.channel, "Adidas", MAX_PRICE.get("Adidas"))


@bot.command(name="corteiz")
async def corteiz(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != CORTEIZ_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Corteiz !", delete_after=5)
        return
    await start_monitor(ctx, "corteiz", ctx.channel, "Corteiz", MAX_PRICE.get("Corteiz"))


@bot.command(name="stone")
async def stone(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != STONE_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Stone Island !", delete_after=5)
        return
    await start_monitor(ctx, "stone", ctx.channel, "Stone Island", MAX_PRICE.get("Stone Island"))


@bot.command(name="tommy")
async def tommy(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != TOMMY_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Tommy Hilfiger !", delete_after=5)
        return
    await start_monitor(ctx, "tommy", ctx.channel, "Tommy Hilfiger", MAX_PRICE.get("Tommy Hilfiger"))


@bot.command(name="sneakers")
async def sneakers(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != SNEAKERS_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Sneakers !", delete_after=5)
        return
    if "sneakers" in running_tasks and not running_tasks["sneakers"].done():
        await ctx.send("⚠️ La recherche Sneakers tourne déjà ! Fais `!stop` pour l'arrêter.", delete_after=8)
        return
    task = asyncio.create_task(monitor_sneakers(ctx.channel))
    running_tasks["sneakers"] = task
    await ctx.send(f"✅ Recherche **Sneakers** lancée en continu dans {ctx.channel.mention} !", delete_after=8)


@bot.command(name="lacoste")
async def lacoste(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != LACOSTE_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Lacoste !", delete_after=5)
        return
    await start_monitor(ctx, "lacoste", ctx.channel, "Lacoste", MAX_PRICE.get("Lacoste"))


@bot.command(name="carhartt")
async def carhartt(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != CARHARTT_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon Carhartt !", delete_after=5)
        return
    await start_monitor(ctx, "carhartt", ctx.channel, "Carhartt", MAX_PRICE.get("Carhartt"))


@bot.command(name="north")
async def north(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    if ctx.channel.id != NORTH_CHANNEL_ID:
        await ctx.send("❌ Cette commande ne fonctionne que dans le salon The North Face !", delete_after=5)
        return
    await start_monitor(ctx, "north", ctx.channel, "The North Face", MAX_PRICE.get("The North Face"))


# ============================================================
# COMMANDE !startall
# ============================================================
@bot.command(name="startall")
async def startall(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    await ctx.send("🚀 Lancement de toutes les recherches en continu...", delete_after=5)
    await ctx.invoke(bot.get_command("hiloteall"))
    await ctx.invoke(bot.get_command("nike"))
    await ctx.invoke(bot.get_command("cp"))
    await ctx.invoke(bot.get_command("trap"))
    await ctx.invoke(bot.get_command("stussy"))
    await ctx.invoke(bot.get_command("ralph"))
    await ctx.invoke(bot.get_command("jott"))
    await ctx.invoke(bot.get_command("north"))
    await ctx.invoke(bot.get_command("carhartt"))
    await ctx.invoke(bot.get_command("lacoste"))
    await ctx.invoke(bot.get_command("sneakers"))
    await ctx.invoke(bot.get_command("tommy"))
    await ctx.invoke(bot.get_command("stone"))
    await ctx.invoke(bot.get_command("corteiz"))
    await ctx.invoke(bot.get_command("adidas"))
    await ctx.invoke(bot.get_command("levis"))
    await ctx.invoke(bot.get_command("tips"))
    await ctx.send("✅ Toutes les recherches tournent en continu !", delete_after=8)


# ============================================================
# COMMANDE /close — Arrêter la recherche du salon actuel
# ============================================================
@bot.tree.command(name="close", description="Arrête la recherche en cours dans ce salon")
async def close(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Accès refusé.", ephemeral=True)
        return

    CHANNEL_TO_KEY = {
        NIKE_CHANNEL_ID: ["nike"],
        CP_CHANNEL_ID: ["cp"],
        TRAP_CHANNEL_ID: ["trap"],
        STUSSY_CHANNEL_ID: ["stussy"],
        RALPH_CHANNEL_ID: ["ralph"],
        JOTT_CHANNEL_ID: ["jott"],
        NORTH_CHANNEL_ID: ["north"],
        CARHARTT_CHANNEL_ID: ["carhartt"],
        LACOSTE_CHANNEL_ID: ["lacoste"],
        TOMMY_CHANNEL_ID: ["tommy"],
        STONE_CHANNEL_ID: ["stone"],
        CORTEIZ_CHANNEL_ID: ["corteiz"],
        ADIDAS_CHANNEL_ID: ["adidas"],
        LEVIS_CHANNEL_ID: ["levis"],
        SNEAKERS_CHANNEL_ID: ["sneakers"],
        TIPS_CHANNEL_ID: ["tips"],
        BOT_ALL_CHANNEL_ID: [k for k in running_tasks if k.startswith("hiloteall_")],
    }

    channel_id = interaction.channel_id
    keys = CHANNEL_TO_KEY.get(channel_id)

    if not keys:
        await interaction.response.send_message("❌ Aucune recherche associée à ce salon.", ephemeral=True)
        return

    stopped = 0
    for key in list(keys) if isinstance(keys, list) else [keys]:
        task = running_tasks.get(key)
        if task and not task.done():
            task.cancel()
            del running_tasks[key]
            stopped += 1

    if stopped:
        await interaction.response.send_message(f"🛑 Recherche arrêtée dans {interaction.channel.mention} !", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Aucune recherche en cours dans ce salon.", ephemeral=True)


# ============================================================
# COMMANDE !stop
# ============================================================
@bot.command(name="stop")
async def stop(ctx: commands.Context):
    if not is_authorized(ctx.author.id):
        await ctx.message.delete()
        return
    count = 0
    for key, task in running_tasks.items():
        if not task.done():
            task.cancel()
            count += 1
    running_tasks.clear()
    await ctx.send(f"🛑 {count} recherche(s) arrêtée(s).", delete_after=8)


# ============================================================
# COMMANDE /help
# ============================================================
@bot.tree.command(name="help", description="Afficher toutes les commandes du bot")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="📖 Commandes du bot",
        description="Toutes les commandes disponibles sur **Vinted Lab | hilote**",
        color=0x1a73e8,
    )
    embed.add_field(
        name="🚀 !startall",
        value="Lance toutes les recherches en continu dans leurs salons respectifs.",
        inline=False,
    )
    embed.add_field(
        name="🛑 !stop",
        value="Arrête toutes les recherches en cours.",
        inline=False,
    )
    embed.add_field(
        name="🔍 !hiloteall",
        value="Lance la recherche de toutes les marques et envoie les meilleures annonces dans le salon principal.",
        inline=False,
    )
    embed.add_field(
        name="👟 !nike",
        value="Lance la recherche Nike et envoie les annonces dans le salon Nike.",
        inline=False,
    )
    embed.add_field(
        name="🧥 !cp",
        value="Lance la recherche CP Company et envoie les annonces dans le salon CP Company.",
        inline=False,
    )
    embed.add_field(
        name="🔫 !trap",
        value="Lance la recherche Trapstar et envoie les annonces dans le salon Trapstar.",
        inline=False,
    )
    embed.add_field(
        name="🌊 !stussy",
        value="Lance la recherche Stussy et envoie les annonces dans le salon Stussy.",
        inline=False,
    )
    embed.add_field(
        name="🐎 !ralph",
        value="Lance la recherche Ralph Lauren et envoie les annonces dans le salon Ralph Lauren.",
        inline=False,
    )
    embed.add_field(
        name="🧥 !jott",
        value="Lance la recherche Jott et envoie les annonces dans le salon Jott.",
        inline=False,
    )
    embed.add_field(
        name="🏔️ !north",
        value="Lance la recherche The North Face et envoie les annonces dans le salon The North Face.",
        inline=False,
    )
    embed.add_field(
        name="🔨 !carhartt",
        value="Lance la recherche Carhartt et envoie les annonces dans le salon Carhartt.",
        inline=False,
    )
    embed.add_field(
        name="🐊 !lacoste",
        value="Lance la recherche Lacoste et envoie les annonces dans le salon Lacoste.",
        inline=False,
    )
    embed.add_field(
        name="👟 !sneakers",
        value="Lance la recherche de toutes les sneakers (Nike, Jordan, Adidas...) dans le salon Sneakers.",
        inline=False,
    )
    embed.add_field(
        name="🏳️ !tommy",
        value="Lance la recherche Tommy Hilfiger et envoie les annonces dans le salon Tommy Hilfiger.",
        inline=False,
    )
    embed.add_field(
        name="🧱 !stone",
        value="Lance la recherche Stone Island et envoie les annonces dans le salon Stone Island.",
        inline=False,
    )
    embed.add_field(
        name="👑 !corteiz",
        value="Lance la recherche Corteiz et envoie les annonces dans le salon Corteiz.",
        inline=False,
    )
    embed.add_field(
        name="🦓 !adidas",
        value="Lance la recherche Adidas et envoie les annonces dans le salon Adidas.",
        inline=False,
    )
    embed.add_field(
        name="👖 !levis",
        value="Lance la recherche Levi's et envoie les annonces dans le salon Levi's.",
        inline=False,
    )
    embed.add_field(
        name="⭐ /favoris",
        value="Envoie tes articles favoris en message privé.",
        inline=False,
    )
    embed.add_field(
        name="⚡ /tuto",
        value="Affiche le tutoriel complet pour utiliser l'Autobuy.",
        inline=False,
    )
    embed.add_field(
        name="📖 /help",
        value="Affiche cette liste de commandes dans le salon help.",
        inline=False,
    )
    embed.set_footer(text="🏷️ Vinted Lab | hilote")

    help_channel = bot.get_channel(HELP_CHANNEL_ID)
    if help_channel:
        await help_channel.send(embed=embed)
        await interaction.followup.send("✅ Commandes envoyées dans le salon help !", ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================
# COMMANDE !favoris
# ============================================================
@bot.tree.command(name="favoris", description="Voir tes favoris en MP")
async def favoris(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_favs = get_user_favorites(interaction.user.id)
    if not user_favs:
        await interaction.followup.send("Aucun favori enregistré.", ephemeral=True)
        return

    try:
        dm = await interaction.user.create_dm()
        await dm.send(f"⭐ **{len(user_favs)} favori(s) :**")

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

            await dm.send(embed=embed, view=view)
            await asyncio.sleep(0.3)

        await interaction.followup.send("📬 Tes favoris t'ont été envoyés en MP !", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Je ne peux pas t'envoyer de MP. Active les messages privés dans tes paramètres Discord.",
            ephemeral=True
        )


# ============================================================
# COMMANDE /accessoires
# ============================================================
@bot.tree.command(name="accessoires", description="Envoie le guide des meilleurs accessoires achat/revente")
async def accessoires(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Accès refusé.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    channel = bot.get_channel(ACCESSOIRES_CHANNEL_ID) or interaction.channel

    embed1 = discord.Embed(title="👜 Accessoires — Top catégories Achat/Revente", description="Voici les meilleures catégories d'accessoires à acheter et revendre sur Vinted et ailleurs.", color=0xFFD700)
    embed1.set_footer(text="🏷️ Vinted Lab | Guide Accessoires")
    await channel.send(embed=embed1)
    await asyncio.sleep(0.5)

    embed2 = discord.Embed(title="👟 1. Ceintures de marque", color=0x1a73e8)
    embed2.add_field(name="Marques visées", value="Louis Vuitton, Gucci, Hermès, Burberry, Lacoste, Ralph Lauren", inline=False)
    embed2.add_field(name="Prix achat cible", value="5 € — 25 €", inline=True)
    embed2.add_field(name="Prix revente moyen", value="30 € — 120 €", inline=True)
    embed2.add_field(name="Marge moyenne", value="+80 à +200 %", inline=True)
    embed2.add_field(name="💡 Astuce", value="Les ceintures Louis Vuitton et Gucci partent très vite. Cherche les lots ou les pièces sous-côtées. Vérifie toujours l'authenticité avant d'acheter.", inline=False)
    await channel.send(embed=embed2)
    await asyncio.sleep(0.5)

    embed3 = discord.Embed(title="🧢 2. Casquettes & bonnets", color=0x00C851)
    embed3.add_field(name="Marques visées", value="New Era, Supreme, Palace, Stussy, Carhartt, Nike, Stone Island", inline=False)
    embed3.add_field(name="Prix achat cible", value="3 € — 15 €", inline=True)
    embed3.add_field(name="Prix revente moyen", value="20 € — 80 €", inline=True)
    embed3.add_field(name="Marge moyenne", value="+100 à +400 %", inline=True)
    embed3.add_field(name="💡 Astuce", value="Les New Era 59FIFTY en bon état sont très demandées. Les bonnets Carhartt font +150% facilement en hiver. Achète en été quand personne n'en veut.", inline=False)
    await channel.send(embed=embed3)
    await asyncio.sleep(0.5)

    embed4 = discord.Embed(title="🎒 3. Sacs à dos & bananes", color=0xFF9800)
    embed4.add_field(name="Marques visées", value="Supreme, Nike, The North Face, Carhartt, Eastpak, Arc'teryx", inline=False)
    embed4.add_field(name="Prix achat cible", value="5 € — 30 €", inline=True)
    embed4.add_field(name="Prix revente moyen", value="30 € — 150 €", inline=True)
    embed4.add_field(name="Marge moyenne", value="+80 à +300 %", inline=True)
    embed4.add_field(name="💡 Astuce", value="Les bananes Supreme et les sacs Arc'teryx sont des pépites. Cherche les coloris rares ou les collabs limitées.", inline=False)
    await channel.send(embed=embed4)
    await asyncio.sleep(0.5)

    embed5 = discord.Embed(title="⌚ 4. Montres & bijoux", color=0x9C27B0)
    embed5.add_field(name="Marques visées", value="Casio G-Shock, Swatch, Seiko, Fossil, Tommy Hilfiger", inline=False)
    embed5.add_field(name="Prix achat cible", value="5 € — 40 €", inline=True)
    embed5.add_field(name="Prix revente moyen", value="30 € — 200 €", inline=True)
    embed5.add_field(name="Marge moyenne", value="+100 à +300 %", inline=True)
    embed5.add_field(name="💡 Astuce", value="Les G-Shock rétro (années 90-2000) explosent en ce moment. Une G-Shock DW-5600 achetée 15€ se revend 60-80€. Cherche les modèles japonais.", inline=False)
    await channel.send(embed=embed5)
    await asyncio.sleep(0.5)

    embed6 = discord.Embed(title="🕶️ 5. Lunettes de soleil", color=0xF44336)
    embed6.add_field(name="Marques visées", value="Ray-Ban, Oakley, Carrera, Lacoste, Ralph Lauren, Prada", inline=False)
    embed6.add_field(name="Prix achat cible", value="5 € — 25 €", inline=True)
    embed6.add_field(name="Prix revente moyen", value="40 € — 180 €", inline=True)
    embed6.add_field(name="Marge moyenne", value="+150 à +500 %", inline=True)
    embed6.add_field(name="💡 Astuce", value="Les Ray-Ban Wayfarer et Clubmaster sont indémodables. Achète hors saison (automne/hiver) à -70% et revends au printemps.", inline=False)
    await channel.send(embed=embed6)
    await asyncio.sleep(0.5)

    embed7 = discord.Embed(title="🧣 6. Écharpes & bonnets de luxe", color=0x607D8B)
    embed7.add_field(name="Marques visées", value="Burberry, Acne Studios, Stone Island, CP Company", inline=False)
    embed7.add_field(name="Prix achat cible", value="10 € — 40 €", inline=True)
    embed7.add_field(name="Prix revente moyen", value="60 € — 250 €", inline=True)
    embed7.add_field(name="Marge moyenne", value="+100 à +400 %", inline=True)
    embed7.add_field(name="💡 Astuce", value="L'écharpe Burberry à carreaux est une valeur sûre. Achetée 20€ en été elle se revend 100€+ en hiver. Vérifie le label et les coutures.", inline=False)
    await channel.send(embed=embed7)
    await asyncio.sleep(0.5)

    embed8 = discord.Embed(title="📊 Récap — Classement par rentabilité", color=0xFFD700)
    embed8.add_field(name="🥇 Meilleure marge", value="Lunettes de soleil (+500% max)\nCeintures de marque (+200% max)", inline=False)
    embed8.add_field(name="🥈 Meilleur volume", value="Casquettes & bonnets (partent très vite)\nSacs à dos (forte demande)", inline=False)
    embed8.add_field(name="🥉 Meilleur rapport risque/gain", value="Montres G-Shock (faciles à authentifier)\nÉcharpes Burberry (valeur sûre)", inline=False)
    embed8.add_field(name="⚠️ Conseil important", value="Toujours vérifier l'authenticité avant d'acheter. Une pièce fake revendue = compte Vinted banni.", inline=False)
    embed8.set_footer(text="🏷️ Vinted Lab | Guide Accessoires")
    await channel.send(embed=embed8)

    await interaction.followup.send(f"✅ Guide envoyé dans {channel.mention} !", ephemeral=True)


# ============================================================
# COMMANDE !tuto — Tutoriel Autobuy
# ============================================================
@bot.tree.command(name="tuto", description="Affiche le tutoriel pour utiliser l'Autobuy")
async def tuto(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    embed1 = discord.Embed(
        title="⚡ Tutoriel — Comment utiliser l'Autobuy",
        description=(
            "L'Autobuy te permet d'**acheter automatiquement** un article Vinted "
            "directement depuis Discord, en un seul clic.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=0x1a73e8,
    )
    embed1.add_field(
        name="📋 Avant de commencer — Ce qu'il te faut",
        value=(
            "✅ Un compte Vinted actif\n"
            "✅ Une **carte bancaire enregistrée** sur Vinted\n"
            "✅ Ton email et mot de passe Vinted dans le fichier `.env`\n\n"
            "> ⚠️ Sans carte bancaire sur Vinted, l'achat échouera !"
        ),
        inline=False,
    )
    embed1.set_footer(text="🏷️ Vinted Lab | Tutoriel Autobuy • Étape 1/3")

    embed2 = discord.Embed(
        title="🖱️ Étape 1 — Trouver un article",
        description=(
            "Lance une recherche avec une commande comme `!nike`, `!ralph`, `!stussy`...\n\n"
            "Le bot va envoyer des annonces comme celle-ci :"
        ),
        color=0x00C851,
    )
    embed2.add_field(
        name="Une annonce ressemble à ça :",
        value=(
            "```\n"
            "Nike Air Force 1\n"
            "⏱ Publié : Aujourd'hui à 14:32\n"
            "🏷 Marque : Nike\n"
            "📐 Taille : 42\n"
            "💎 État : Très bon état\n"
            "💰 Prix achat : 18 €\n"
            "📊 Prix marché : 45 €\n"
            "💸 Marge : +27 € (60%)\n"
            "```"
        ),
        inline=False,
    )
    embed2.add_field(
        name="Les boutons disponibles :",
        value=(
            "📄 **Détails** → Ouvre l'annonce sur Vinted\n"
            "🛒 **Acheter** → Ouvre la page d'achat Vinted\n"
            "💬 **Négocier** → Envoie un message au vendeur\n"
            "⭐ **Favoriser** → Sauvegarde l'article\n"
            "⚡ **Autobuy** → Achète automatiquement !"
        ),
        inline=False,
    )
    embed2.set_footer(text="🏷️ Vinted Lab | Tutoriel Autobuy • Étape 2/3")

    embed3 = discord.Embed(
        title="⚡ Étape 2 — Utiliser l'Autobuy",
        description="Quand tu vois une bonne affaire, voilà comment acheter en quelques secondes :",
        color=0xFF9800,
    )
    embed3.add_field(
        name="1️⃣  Clique sur ⚡ Autobuy",
        value="Un message de confirmation apparaît **rien que pour toi** (personne d'autre ne le voit).",
        inline=False,
    )
    embed3.add_field(
        name="2️⃣  Vérifie le titre et le prix",
        value="Le bot t'affiche le nom de l'article et son prix avant de confirmer.",
        inline=False,
    )
    embed3.add_field(
        name="3️⃣  Clique sur ✅ Confirmer l'achat",
        value=(
            "Le bot se connecte automatiquement à ton compte Vinted et finalise l'achat.\n"
            "> ⏳ Ça prend environ **15 à 30 secondes**."
        ),
        inline=False,
    )
    embed3.add_field(
        name="4️⃣  Résultat",
        value=(
            "✅ **Achat effectué avec succès !** → L'article est acheté, vérifie tes commandes sur Vinted.\n"
            "❌ **Erreur** → Le bot t'explique pourquoi (article déjà vendu, problème de paiement, etc.)"
        ),
        inline=False,
    )
    embed3.set_footer(text="🏷️ Vinted Lab | Tutoriel Autobuy • Étape 3/3")

    embed4 = discord.Embed(
        title="⚠️ Points importants à savoir",
        color=0xFF4444,
    )
    embed4.add_field(
        name="🔒 Sécurité",
        value="Seul toi vois le bouton de confirmation. L'achat ne se fait **jamais sans ta validation**.",
        inline=False,
    )
    embed4.add_field(
        name="💳 Paiement",
        value="Le bot utilise la carte bancaire **déjà enregistrée** sur ton compte Vinted.",
        inline=False,
    )
    embed4.add_field(
        name="⏰ Rapidité",
        value="L'Autobuy est fait pour les **bonnes affaires qui partent vite**. Plus tu cliques vite, mieux c'est !",
        inline=False,
    )
    embed4.add_field(
        name="❌ Si ça ne marche pas",
        value=(
            "• Vérifie que ton email/mot de passe Vinted est correct dans `.env`\n"
            "• Vérifie qu'une carte bancaire est bien enregistrée sur Vinted\n"
            "• L'article a peut-être déjà été vendu à quelqu'un d'autre"
        ),
        inline=False,
    )
    embed4.set_footer(text="🏷️ Vinted Lab | hilote")

    channel = bot.get_channel(HELP_CHANNEL_ID) or interaction.channel
    await channel.send(embed=embed1)
    await asyncio.sleep(0.5)
    await channel.send(embed=embed2)
    await asyncio.sleep(0.5)
    await channel.send(embed=embed3)
    await asyncio.sleep(0.5)
    await channel.send(embed=embed4)

    await interaction.followup.send(f"✅ Tutoriel envoyé dans {channel.mention} !", ephemeral=True)


# ============================================================
# COMMANDE /lc — Légit Check (authentique ou faux ?)
# ============================================================
@bot.tree.command(name="lc", description="Vérifie si un article est authentique ou fake — envoie une photo !")
@discord.app_commands.describe(image="La photo de l'article à vérifier")
async def lc(interaction: discord.Interaction, image: discord.Attachment):
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message(
            "❌ Envoie une **image** (jpg, png, etc.), pas un autre type de fichier.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    if not ANTHROPIC_API_KEY:
        await interaction.followup.send("❌ Clé API Anthropic manquante dans le fichier `.env` (`ANTHROPIC_API_KEY`).")
        return

    # Télécharger l'image
    async with aiohttp.ClientSession() as session:
        async with session.get(image.url) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Impossible de télécharger l'image, réessaie.")
                return
            image_bytes = await resp.read()

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = image.content_type.split(";")[0]

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Tu es un expert en authentification de vêtements et sneakers de marque. "
                            "Analyse cette image et dis-moi si l'article semble AUTHENTIQUE ou FAKE (contrefaçon). "
                            "Réponds en français. Structure ta réponse ainsi :\n\n"
                            "**Verdict : ✅ AUTHENTIQUE** ou **Verdict : ❌ FAKE (contrefaçon)**\n\n"
                            "**Points analysés :**\n"
                            "- (liste les détails que tu as observés : logo, coutures, étiquettes, qualité, etc.)\n\n"
                            "**Niveau de confiance :** (Faible / Moyen / Élevé)\n\n"
                            "**Conseils :** (ce qu'il faudrait vérifier en plus si tu n'es pas sûr)\n\n"
                            "Si l'image n'est pas assez claire ou ne montre pas suffisamment de détails, dis-le clairement."
                        ),
                    },
                ],
            }
        ],
    )

    result_text = message.content[0].text

    embed = discord.Embed(
        title="🔍 Légit Check",
        description=result_text,
        color=0x00C851 if "AUTHENTIQUE" in result_text else 0xFF4444,
    )
    embed.set_thumbnail(url=image.url)
    embed.set_footer(text=f"🏷️ Vinted Lab | Légit Check • Demandé par {interaction.user.display_name}")

    await interaction.followup.send(embed=embed)


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
