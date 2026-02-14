"""
Shopify Store Scraper (EasySell Compatible)
============================================
Fetches product data from Shopify stores that use EasySell COD Form.
- Extracts products from /products/{handle}.json
- Parses EasySell config and shop identifier from page HTML
- Detects EasySell COD form presence
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bot.stealth import StealthClient


# ── Data Models ───────────────────────────────────────────────

@dataclass
class ProductVariant:
    variant_id: int
    title: str
    price: str          # e.g. "599.00"
    price_cents: int    # e.g. 59900
    sku: str
    available: bool
    option1: Optional[str] = None
    option2: Optional[str] = None
    option3: Optional[str] = None


@dataclass
class Product:
    product_id: int
    title: str
    handle: str
    vendor: str
    product_type: str
    price: str
    image_url: str
    variants: List[ProductVariant] = field(default_factory=list)
    available: bool = True


@dataclass
class StoreInfo:
    url: str
    domain: str
    name: str
    shop_domain: str         # e.g. "xjvscz-yt.myshopify.com"
    currency: str = "INR"
    country: str = "IN"
    has_easysell: bool = False
    easysell_fields: Dict[str, str] = field(default_factory=dict)
    products: List[Product] = field(default_factory=list)


# ── Scraper ───────────────────────────────────────────────────

class ShopifyScraper:
    """Scrapes product and store info from Shopify stores with EasySell COD form."""

    def __init__(self, client: StealthClient):
        self.client = client

    def _normalize_url(self, url: str) -> str:
        """Ensure URL has scheme and extract clean base URL."""
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_handle_from_url(self, url: str) -> Optional[str]:
        """Extract product handle from URL like /products/some-product."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        match = re.search(r"/products/([^/?#]+)", path)
        return match.group(1) if match else None

    async def get_store_info_from_page(self, page_url: str) -> StoreInfo:
        """
        Extract full store info by visiting a page and parsing HTML.
        Works for both store homepage and product pages.
        """
        base_url = self._normalize_url(page_url)
        domain = urlparse(base_url).netloc
        name = domain
        shop_domain = ""
        currency = "INR"
        country = "IN"
        has_easysell = False

        try:
            resp = await self.client.get(page_url)
            html = resp.text
        except Exception:
            return StoreInfo(
                url=base_url, domain=domain, name=name,
                shop_domain="", has_easysell=False,
            )

        # Extract Shopify.shop
        shop_match = re.search(r'Shopify\.shop\s*=\s*["\']([^"\']+)["\']', html)
        if shop_match:
            shop_domain = shop_match.group(1)
        else:
            shop_match = re.search(r'([a-z0-9\-]+\.myshopify\.com)', html)
            if shop_match:
                shop_domain = shop_match.group(1)

        # Store name from title
        name_match = re.search(r'<title>([^<]+)</title>', html)
        if name_match:
            raw = name_match.group(1).strip()
            # Clean: "Product Name – Store" or "Product Name | Store"
            for sep in [" – ", " | ", " - "]:
                if sep in raw:
                    name = raw.split(sep)[-1].strip()
                    break
            else:
                name = raw

        # EasySell detection
        if "easysell" in html.lower() or "tyslo.com" in html:
            has_easysell = True

        # Currency
        curr_match = re.search(r'"currency"\s*:\s*"([A-Z]+)"', html)
        if curr_match:
            currency = curr_match.group(1)

        # Country
        ctry_match = re.search(r'"country"\s*:\s*"([A-Z]{2})"', html)
        if ctry_match:
            country = ctry_match.group(1)

        return StoreInfo(
            url=base_url,
            domain=domain,
            name=name,
            shop_domain=shop_domain,
            currency=currency,
            country=country,
            has_easysell=has_easysell,
        )

    # Alias for backward compat
    async def get_store_info(self, store_url: str) -> StoreInfo:
        return await self.get_store_info_from_page(store_url)

    async def get_single_product(self, product_url: str) -> Optional[Product]:
        """Fetch a single product by its URL using /products/{handle}.json."""
        base_url = self._normalize_url(product_url)
        handle = self._extract_handle_from_url(product_url)
        if not handle:
            return None

        try:
            resp = await self.client.get(f"{base_url}/products/{handle}.json")
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None

        p = data.get("product", {})
        if not p:
            return None

        return self._parse_product(p, handle)

    async def get_products(self, store_url: str, limit: int = 30) -> List[Product]:
        """
        Fetch products from the store.
        Tries /products.json first, then crawls /collections/all for handles.
        """
        base_url = self._normalize_url(store_url)
        products = []

        # Method 1: /products.json (works on some stores)
        try:
            resp = await self.client.get(
                f"{base_url}/products.json",
                params={"limit": min(250, limit)},
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("products", [])
                for p in raw[:limit]:
                    product = self._parse_product(p)
                    if product:
                        products.append(product)
                if products:
                    return products
        except Exception:
            pass

        # Method 2: Crawl /collections/all for product handles
        try:
            resp = await self.client.get(f"{base_url}/collections/all")
            if resp.status_code == 200:
                html = resp.text
                handles = re.findall(r'/products/([a-zA-Z0-9\-_]+)', html)
                seen = set()
                unique = []
                for h in handles:
                    if h not in seen and h != "json":
                        seen.add(h)
                        unique.append(h)

                for handle in unique[:limit]:
                    try:
                        r = await self.client.get(f"{base_url}/products/{handle}.json")
                        if r.status_code == 200:
                            p = r.json().get("product", {})
                            if p:
                                prod = self._parse_product(p, handle)
                                if prod:
                                    products.append(prod)
                    except Exception:
                        continue
        except Exception:
            pass

        return products

    def _parse_product(self, p: dict, fallback_handle: str = "") -> Optional[Product]:
        """Parse a product JSON dict into a Product dataclass."""
        if not p:
            return None

        variants = []
        for v in p.get("variants", []):
            price_str = v.get("price", "0.00")
            try:
                price_cents = int(float(price_str) * 100)
            except (ValueError, TypeError):
                price_cents = 0

            variants.append(
                ProductVariant(
                    variant_id=v["id"],
                    title=v.get("title", "Default"),
                    price=price_str,
                    price_cents=price_cents,
                    sku=v.get("sku", ""),
                    available=v.get("available", True),
                    option1=v.get("option1"),
                    option2=v.get("option2"),
                    option3=v.get("option3"),
                )
            )

        images = p.get("images", [])
        image_url = images[0]["src"] if images else ""
        available_variants = [v for v in variants if v.available]

        return Product(
            product_id=p["id"],
            title=p.get("title", "Unknown"),
            handle=p.get("handle", fallback_handle),
            vendor=p.get("vendor", ""),
            product_type=p.get("product_type", ""),
            price=variants[0].price if variants else "0.00",
            image_url=image_url,
            variants=variants,
            available=len(available_variants) > 0,
        )

    async def check_cod_available(self, store_url: str) -> bool:
        """Check if EasySell COD form is available on the store."""
        base_url = self._normalize_url(store_url)
        try:
            resp = await self.client.get(base_url, follow_redirects=True)
            text = resp.text.lower()
            if "easysell" in text or "tyslo.com" in text:
                return True
            if "cash on delivery" in text or "cod" in text:
                return True
        except Exception:
            pass
        return False
