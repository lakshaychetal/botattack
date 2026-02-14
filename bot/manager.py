"""
Order Manager
=============
Orchestrates COD orders through EasySell API with:
- Store scanning and product fetching
- Single and batch order placement
- Retry logic with fresh identities
- CSV result export
- Progress callbacks for UI
"""

import asyncio
import csv
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from bot.checkout import CheckoutEngine, OrderResult, OrderStatus
from bot.config import BotConfig, CustomerAddress
from bot.identity import IdentityGenerator
from bot.scraper import Product, ProductVariant, ShopifyScraper, StoreInfo
from bot.stealth import StealthClient


@dataclass
class BatchResult:
    """Results from a batch order run."""
    total_attempted: int = 0
    total_success: int = 0
    total_failed: int = 0
    orders: List[OrderResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_attempted == 0:
            return 0.0
        return (self.total_success / self.total_attempted) * 100

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


# Callback types
ProgressCallback = Callable[[int, int, OrderResult], None]
LogCallback = Callable[[str], None]


class OrderManager:
    """
    Manages COD order placement via EasySell API.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.stealth_client = StealthClient(config)
        self.scraper = ShopifyScraper(self.stealth_client)
        self.identity_gen = IdentityGenerator(config)
        self._on_progress: Optional[ProgressCallback] = None
        self._on_log: Optional[LogCallback] = None

    def on_progress(self, callback: ProgressCallback):
        self._on_progress = callback

    def on_log(self, callback: LogCallback):
        self._on_log = callback

    def _log(self, msg: str):
        if self._on_log:
            self._on_log(msg)

    async def scan_store(self, store_url: str) -> dict:
        """
        Scan a Shopify store: get info, products, COD availability.
        """
        self._log("🔍 Scanning store...")

        store_info = await self.scraper.get_store_info(store_url)
        self._log(f"📦 Store: {store_info.name} ({store_info.domain})")
        self._log(f"🏪 Shopify domain: {store_info.shop_domain or 'Not found'}")
        self._log(f"💱 Currency: {store_info.currency}")

        self._log("🔍 Checking for EasySell COD form...")
        if store_info.has_easysell:
            self._log("✅ EasySell COD Form detected!")
        else:
            self._log("⚠️  EasySell not detected (will attempt standard COD)")

        self._log("🔍 Fetching products...")
        products = await self.scraper.get_products(store_url, limit=50)
        available = [p for p in products if p.available]
        self._log(f"📋 Found {len(products)} products ({len(available)} available)")

        return {
            "store": store_info,
            "products": products,
            "available_products": available,
        }

    async def place_single_order(
        self,
        store_info: StoreInfo,
        product: Product,
        variant: ProductVariant,
        product_url: str,
        customer: Optional[CustomerAddress] = None,
    ) -> OrderResult:
        """Place a single COD order with retry logic."""
        if customer is None:
            customer = self.identity_gen.generate()

        engine = CheckoutEngine(
            store_url=store_info.url,
            store_info=store_info,
            client=self.stealth_client,
            config=self.config,
        )

        last_result = None
        for attempt in range(1, self.config.order.retry_attempts + 1):
            self._log(f"  ⏳ Attempt {attempt}/{self.config.order.retry_attempts}...")

            result = await engine.place_order(
                product=product,
                variant=variant,
                customer=customer,
                product_url=product_url,
                quantity=self.config.order.quantity,
            )

            if result.status == OrderStatus.COMPLETED:
                return result

            last_result = result

            if attempt < self.config.order.retry_attempts:
                wait = self.config.order.retry_delay * attempt
                self._log(f"  ⚠️  Failed: {result.error}. Retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
                # New identity for retry
                customer = self.identity_gen.generate()

        return last_result or OrderResult(
            status=OrderStatus.FAILED, error="All retries exhausted"
        )

    async def place_batch_orders(
        self,
        store_info: StoreInfo,
        product: Product,
        variant: ProductVariant,
        product_url: str,
        count: int,
    ) -> BatchResult:
        """
        Place multiple COD orders with delays between them.
        """
        batch = BatchResult()
        batch.start_time = datetime.now()
        batch.total_attempted = count

        for i in range(count):
            order_num = i + 1
            customer = self.identity_gen.generate()

            self._log(
                f"\n{'─' * 50}\n"
                f"📦 Order {order_num}/{count}\n"
                f"👤 {customer.first_name} {customer.last_name}\n"
                f"📍 {customer.city}, {customer.province} ({customer.province_code})\n"
                f"📱 {customer.phone}"
            )

            result = await self.place_single_order(
                store_info=store_info,
                product=product,
                variant=variant,
                product_url=product_url,
                customer=customer,
            )

            batch.orders.append(result)

            if result.status == OrderStatus.COMPLETED:
                batch.total_success += 1
                self._log(
                    f"  ✅ Order {result.order_name or '#' + str(result.order_number)} placed!"
                    f" Total: ₹{result.total_price}"
                )
            else:
                batch.total_failed += 1
                self._log(f"  ❌ Failed: {result.error}")

            if self._on_progress:
                self._on_progress(order_num, count, result)

            # Delay between orders
            if order_num < count:
                delay = random.uniform(
                    self.config.order.delay_between_orders.min,
                    self.config.order.delay_between_orders.max,
                )
                self._log(f"  ⏰ Waiting {delay:.1f}s before next order...")
                await asyncio.sleep(delay)

        batch.end_time = datetime.now()
        return batch

    def export_results(self, batch: BatchResult, filepath: Optional[str] = None):
        """Export batch results to CSV."""
        filepath = filepath or self.config.output.results_file
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = path.exists()

        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    "Timestamp", "Order #", "Order Name", "Status",
                    "Customer", "Product", "Variant", "Total",
                    "Status URL", "Error",
                ])

            for order in batch.orders:
                writer.writerow([
                    datetime.now().isoformat(),
                    order.order_number or "N/A",
                    order.order_name or "N/A",
                    order.status.value,
                    order.customer_name,
                    order.product_title,
                    order.variant_title,
                    order.total_price or "N/A",
                    order.status_url or "",
                    order.error or "",
                ])

        self._log(f"📊 Results exported to {filepath}")
