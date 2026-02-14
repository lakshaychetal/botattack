"""
EasySell COD Checkout Engine
=============================
Handles the complete COD order flow through EasySell's API:

1. Visit product page (establish session/cookies)
2. Clear cart → Add variant to cart
3. Fetch cart data (/cart.js)
4. Generate EasySell client hash
5. POST order to https://load.tyslo.com/order/new

This replaces the standard Shopify checkout flow for stores
that use the EasySell COD Form Shopify app.
"""

import asyncio
import json
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from bot.config import BotConfig, CustomerAddress
from bot.scraper import Product, ProductVariant, StoreInfo
from bot.stealth import StealthClient


# ── Constants ─────────────────────────────────────────────────

EASYSELL_ORDER_API = "https://load.tyslo.com/order/new"


# ── Status & Result ───────────────────────────────────────────

class OrderStatus(str, Enum):
    PENDING = "pending"
    CART_ADDED = "cart_added"
    CART_VERIFIED = "cart_verified"
    HASH_GENERATED = "hash_generated"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrderResult:
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    order_name: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    status_url: Optional[str] = None
    error: Optional[str] = None
    customer_name: str = ""
    product_title: str = ""
    variant_title: str = ""
    total_price: str = ""
    tags: List[str] = field(default_factory=list)
    raw_response: Optional[Dict] = None


# ── Hash Generator ────────────────────────────────────────────

def _java_string_hash(s: str) -> int:
    """
    Replicate Java's String.hashCode() used by EasySell.
    hash = s[0]*31^(n-1) + s[1]*31^(n-2) + ... + s[n-1]
    """
    h = 0
    for ch in s:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
        if h > 0x7FFFFFFF:
            h -= 0x100000000
    return h


def generate_easysell_hash(user_agent: str) -> str:
    """
    Replicate EasySell's generateUniqueId() function:
      function w() {
        const e = new Date().getTime();
        const t = Math.floor(Math.random() * 1e9);
        const o = navigator.userAgent;
        let r = 0;
        for (let e = 0; e < o.length; e++) {
          r = (r << 5) - r + o.charCodeAt(e);
          r |= 0;
        }
        r = Math.abs(r);
        return `${e}${r}${t}`;
      }
    """
    timestamp = int(time.time() * 1000)  # Date.now()
    ua_hash = abs(_java_string_hash(user_agent))
    rand_part = random.randint(0, 999999999)
    return f"{timestamp}{ua_hash}{rand_part}"


# ── Checkout Engine ───────────────────────────────────────────

class CheckoutEngine:
    """
    EasySell COD Checkout Engine.

    Flow:
      1. GET  product_url          → Visit page (cookies + session)
      2. POST /cart/clear.js       → Clear cart
      3. POST /cart/add.js         → Add variant
      4. GET  /cart.js             → Verify cart & get items
      5. Generate EasySell hash
      6. POST load.tyslo.com/order/new → Submit COD order
    """

    def __init__(
        self,
        store_url: str,
        store_info: StoreInfo,
        client: StealthClient,
        config: BotConfig,
    ):
        self.base_url = store_url.rstrip("/")
        self.store_info = store_info
        self.client = client
        self.config = config

    async def place_order(
        self,
        product: Product,
        variant: ProductVariant,
        customer: CustomerAddress,
        product_url: str,
        quantity: int = 1,
    ) -> OrderResult:
        """
        Execute the full EasySell COD checkout flow.
        """
        result = OrderResult(
            customer_name=f"{customer.first_name} {customer.last_name}",
            product_title=product.title,
            variant_title=variant.title,
        )

        # Create persistent session for cookie continuity
        session = self.client.create_session()
        user_agent = session.headers.get("User-Agent", "")

        try:
            # ── Step 1: Visit product page ────────────────────
            try:
                resp = await session.get(
                    product_url,
                    headers={"User-Agent": user_agent},
                    follow_redirects=True,
                )
            except Exception:
                pass  # Non-critical, just for cookies

            # ── Step 2: Clear cart ────────────────────────────
            try:
                await session.post(
                    f"{self.base_url}/cart/clear.js",
                    headers={
                        "User-Agent": user_agent,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
            except Exception:
                pass

            # Small human-like delay
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # ── Step 3: Add to cart ───────────────────────────
            add_payload = {
                "items": [{"id": variant.variant_id, "quantity": quantity}]
            }

            try:
                add_resp = await session.post(
                    f"{self.base_url}/cart/add.js",
                    headers={
                        "User-Agent": user_agent,
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "Origin": self.base_url,
                        "Referer": product_url,
                    },
                    json=add_payload,
                )
                if add_resp.status_code != 200:
                    result.status = OrderStatus.FAILED
                    result.error = f"Failed to add to cart (HTTP {add_resp.status_code})"
                    return result
            except Exception as e:
                result.status = OrderStatus.FAILED
                result.error = f"Cart add error: {str(e)}"
                return result

            result.status = OrderStatus.CART_ADDED

            await asyncio.sleep(random.uniform(0.2, 0.5))

            # ── Step 4: Get cart data ─────────────────────────
            try:
                cart_resp = await session.get(
                    f"{self.base_url}/cart.js",
                    headers={
                        "User-Agent": user_agent,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                cart_data = cart_resp.json()
                cart_items = cart_data.get("items", [])
                if not cart_items:
                    result.status = OrderStatus.FAILED
                    result.error = "Cart is empty after add"
                    return result
            except Exception as e:
                result.status = OrderStatus.FAILED
                result.error = f"Cart fetch error: {str(e)}"
                return result

            result.status = OrderStatus.CART_VERIFIED
            result.total_price = str(cart_data.get("total_price", 0) / 100)

            # ── Step 5: Generate hash ─────────────────────────
            es_hash = generate_easysell_hash(user_agent)
            result.status = OrderStatus.HASH_GENERATED

            # ── Step 6: Submit COD order via EasySell API ─────
            order_payload = self._build_order_payload(
                es_hash=es_hash,
                customer=customer,
                cart_items=cart_items,
                product_url=product_url,
            )

            try:
                order_resp = await session.post(
                    EASYSELL_ORDER_API,
                    headers={
                        "User-Agent": user_agent,
                        "Content-Type": "text/plain",
                        "Accept": "application/json",
                        "Origin": self.base_url,
                        "Referer": product_url,
                    },
                    content=json.dumps(order_payload),
                )
                result.status = OrderStatus.SUBMITTED
            except Exception as e:
                result.status = OrderStatus.FAILED
                result.error = f"Order submit error: {str(e)}"
                return result

            # ── Parse response ────────────────────────────────
            if order_resp.status_code == 200:
                try:
                    resp_data = order_resp.json()
                except Exception:
                    result.status = OrderStatus.FAILED
                    result.error = f"Invalid JSON response: {order_resp.text[:200]}"
                    return result

                if resp_data.get("success"):
                    order = resp_data.get("order", {})
                    result.status = OrderStatus.COMPLETED
                    result.order_id = str(order.get("id", ""))
                    result.order_number = str(order.get("order_number", order.get("number", "")))
                    result.order_name = order.get("name", "")
                    result.status_url = order.get("order_status_url", "")
                    result.tags = order.get("tags", [])
                    result.raw_response = resp_data

                    # Get total from line items
                    line_items = order.get("line_items", [])
                    if line_items:
                        total_cents = sum(
                            item.get("total_price", 0) for item in line_items
                        )
                        result.total_price = f"{total_cents / 100:.2f}"
                else:
                    result.status = OrderStatus.FAILED
                    # Parse error details
                    errors = resp_data.get("errors", [])
                    if errors and isinstance(errors, list):
                        messages = [
                            e.get("message", str(e)) if isinstance(e, dict) else str(e)
                            for e in errors
                        ]
                        result.error = "; ".join(messages)
                    else:
                        result.error = resp_data.get(
                            "message",
                            resp_data.get("error", "Unknown API error"),
                        )
                    result.raw_response = resp_data
            else:
                result.status = OrderStatus.FAILED
                result.error = f"HTTP {order_resp.status_code}: {order_resp.text[:300]}"

        except Exception as e:
            result.status = OrderStatus.FAILED
            result.error = f"Unexpected error: {str(e)}"
        finally:
            await session.aclose()

        return result

    def _build_order_payload(
        self,
        es_hash: str,
        customer: CustomerAddress,
        cart_items: List[Dict[str, Any]],
        product_url: str,
    ) -> Dict[str, Any]:
        """
        Build the EasySell order payload exactly matching the JS frontend.
        """
        full_name = f"{customer.first_name} {customer.last_name}"

        return {
            "hash": es_hash,
            "shop": self.store_info.shop_domain,
            "currency": {
                "active": self.store_info.currency,
                "rate": "1.0",
            },
            "data": {
                "first_name": {
                    "title": "Full Name",
                    "value": full_name,
                },
                "phone": {
                    "title": "Mobile Number",
                    "value": customer.phone,
                },
                "address": {
                    "title": "Full Address",
                    "value": customer.address1,
                },
                "address2": {
                    "title": "Land Mark",
                    "value": customer.address2,
                },
                "zip": {
                    "title": "PIN code",
                    "value": customer.zip,
                },
                "city": {
                    "title": "City",
                    "value": customer.city,
                },
                "province": {
                    "title": "State",
                    "value": customer.province_code,
                },
            },
            "cart": cart_items,
            "shipping": None,
            "locale": "en",
            "version": "V2",
            "source_url": product_url,
            "offer": None,
            "bumps": [],
            "downsell": {"discount_amount": None},
            "fee": None,
            "recovered": False,
            "is_draft_order": False,
            "utms": {},
            "pixelCookies": {},
            "apps": {},
            "es_token": None,
            "taxesIncluded": False,
            "pixels": [],
            "is_bundle": False,
        }
