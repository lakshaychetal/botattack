"""
CLI Interface
=============
Professional command-line interface using Rich library.
Beautiful menus, progress bars, tables, and colored output.
"""

import asyncio
import sys
from typing import List, Optional
from urllib.parse import urlparse

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.theme import Theme

from bot.checkout import OrderStatus
from bot.config import BotConfig, load_config
from bot.logger import setup_logger
from bot.manager import BatchResult, OrderManager
from bot.scraper import Product, ProductVariant, StoreInfo

# ── Theme & Console ───────────────────────────────────────────

custom_theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "warning": "bold yellow",
    "info": "bold cyan",
    "muted": "dim",
    "accent": "bold magenta",
})

console = Console(theme=custom_theme)

# ── Banner ────────────────────────────────────────────────────

BANNER = r"""
[bold magenta]
 ██████╗  ██████╗ ████████╗ █████╗ ████████╗████████╗ █████╗  ██████╗██╗  ██╗
 ██╔══██╗██╔═══██╗╚══██╔══╝██╔══██╗╚══██╔══╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝
 ██████╔╝██║   ██║   ██║   ███████║   ██║      ██║   ███████║██║     █████╔╝
 ██╔══██╗██║   ██║   ██║   ██╔══██║   ██║      ██║   ██╔══██║██║     ██╔═██╗
 ██████╔╝╚██████╔╝   ██║   ██║  ██║   ██║      ██║   ██║  ██║╚██████╗██║  ██╗
 ╚═════╝  ╚═════╝    ╚═╝   ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
[/bold magenta]
[bold white]         ━━━ Shopify COD Order Bot v2.0.0 ━━━[/bold white]
[dim]          EasySell Engine • Professional Edition[/dim]
"""


class CLI:
    """Professional CLI interface for the bot."""

    def __init__(self):
        self.config: Optional[BotConfig] = None
        self.manager: Optional[OrderManager] = None
        self.logger = None

    def display_banner(self):
        console.print(BANNER)
        console.print()

    def load_configuration(self):
        console.print("[info]⚙  Loading configuration...[/info]")
        self.config = load_config()
        self.logger = setup_logger(
            self.config.output.log_file,
            self.config.output.verbose,
        )
        self.manager = OrderManager(self.config)
        self.manager.on_log(lambda msg: console.print(f"  {msg}"))
        console.print("[success]✓  Configuration loaded[/success]")
        console.print()

    def display_main_menu(self) -> str:
        table = Table(
            title="[bold]Main Menu[/bold]",
            box=box.ROUNDED,
            border_style="cyan",
            title_style="bold white",
            show_header=False,
            pad_edge=True,
        )
        table.add_column("Option", style="bold cyan", width=6)
        table.add_column("Description", style="white")

        table.add_row("1", "🎯  Target Product — Direct product URL (recommended)")
        table.add_row("2", "🚀  Quick Attack — Enter store URL, scan & order")
        table.add_row("3", "🔍  Scan Store — View all products")
        table.add_row("4", "⚙️   Settings — View current config")
        table.add_row("5", "❌  Exit")

        console.print(table)
        console.print()

        return Prompt.ask(
            "[bold cyan]Select option[/bold cyan]",
            choices=["1", "2", "3", "4", "5"],
            default="1",
        )

    # ── Mode 1: Target Product (Primary) ──────────────────────

    async def target_product_mode(self):
        """Target a specific product URL — the primary attack mode."""
        console.print(Panel(
            "[bold]🎯 Target Product Mode[/bold]\n"
            "[dim]Enter a product URL from any Shopify store with EasySell COD form.[/dim]\n"
            "[dim]Example: https://store.com/products/some-product[/dim]",
            border_style="yellow",
        ))

        product_url = Prompt.ask("[bold cyan]🔗 Product URL[/bold cyan]")
        if not product_url:
            return

        product_url = product_url.strip()
        if not product_url.startswith("http"):
            product_url = "https://" + product_url

        # Extract store URL
        parsed = urlparse(product_url)
        store_url = f"{parsed.scheme}://{parsed.netloc}"

        # Step 1: Fetch product
        product = None
        store_info = None

        with console.status("[bold cyan]Fetching product & store info...[/bold cyan]", spinner="dots"):
            try:
                product = await self.manager.scraper.get_single_product(product_url)
                store_info = await self.manager.scraper.get_store_info_from_page(product_url)
            except Exception as e:
                console.print(f"[error]❌ Error: {e}[/error]")
                return

        if not product:
            console.print("[error]❌ Could not find product at that URL.[/error]")
            console.print("[dim]Make sure the URL is a valid /products/... page.[/dim]")
            return

        if not store_info or not store_info.shop_domain:
            console.print("[error]❌ Could not detect Shopify shop domain.[/error]")
            console.print("[dim]This might not be a Shopify store or the page structure is different.[/dim]")
            return

        # Display product info
        self._display_product_info(product, store_info)

        if not product.available:
            console.print("[error]❌ Product is not available / sold out.[/error]")
            return

        # Check EasySell
        if store_info.has_easysell:
            console.print("[success]✅ EasySell COD Form detected[/success]")
        else:
            console.print("[warning]⚠️  EasySell not detected. Will attempt anyway.[/warning]")

        # Select variant
        variant = self._select_variant(product)
        if not variant:
            return

        # How many orders?
        count = IntPrompt.ask(
            "[bold cyan]📦 How many orders?[/bold cyan]",
            default=self.config.order.max_orders,
        )

        # Confirm
        self._display_order_summary(store_info, product, variant, count)
        if not Confirm.ask("[bold yellow]⚡ Launch attack?[/bold yellow]", default=True):
            console.print("[warning]Aborted.[/warning]")
            return

        # Execute
        await self._execute_orders(store_info, product, variant, product_url, count)

    # ── Mode 2: Quick Attack ──────────────────────────────────

    async def quick_attack(self):
        """Scan store, pick product, attack."""
        console.print(Panel(
            "[bold]🚀 Quick Attack Mode[/bold]\n"
            "[dim]Enter a store URL — bot will scan products and place COD orders.[/dim]",
            border_style="magenta",
        ))

        store_url = Prompt.ask("[bold cyan]🔗 Store URL[/bold cyan]")
        if not store_url:
            return

        store_url = store_url.strip()
        if not store_url.startswith("http"):
            store_url = "https://" + store_url

        with console.status("[bold cyan]Scanning store...[/bold cyan]", spinner="dots"):
            try:
                scan_data = await self.manager.scan_store(store_url)
            except Exception as e:
                console.print(f"[error]❌ Failed to scan: {e}[/error]")
                return

        store_info = scan_data["store"]
        products = scan_data["available_products"]

        if not products:
            console.print("[error]❌ No available products found.[/error]")
            console.print(
                "[dim]Tip: If the store has products, try Mode 1 (Target Product) "
                "with a direct product URL instead.[/dim]"
            )
            return

        self._display_products(products)

        product_idx = IntPrompt.ask(
            "[bold cyan]Select product #[/bold cyan]", default=1,
        )
        if product_idx < 1 or product_idx > len(products):
            console.print("[error]Invalid selection.[/error]")
            return

        product = products[product_idx - 1]
        variant = self._select_variant(product)
        if not variant:
            return

        count = IntPrompt.ask(
            "[bold cyan]📦 How many orders?[/bold cyan]",
            default=self.config.order.max_orders,
        )

        product_url = f"{store_info.url}/products/{product.handle}"

        self._display_order_summary(store_info, product, variant, count)
        if not Confirm.ask("[bold yellow]⚡ Launch attack?[/bold yellow]", default=True):
            return

        await self._execute_orders(store_info, product, variant, product_url, count)

    # ── Mode 3: Scan Store ────────────────────────────────────

    async def scan_store_mode(self):
        """Scan a store and display all products."""
        console.print(Panel(
            "[bold]🔍 Store Scanner[/bold]\n"
            "[dim]Scan a Shopify store to view all products.[/dim]",
            border_style="cyan",
        ))

        store_url = Prompt.ask("[bold cyan]🔗 Store URL[/bold cyan]")
        if not store_url:
            return

        store_url = store_url.strip()
        if not store_url.startswith("http"):
            store_url = "https://" + store_url

        with console.status("[bold cyan]Scanning...[/bold cyan]", spinner="dots"):
            try:
                scan_data = await self.manager.scan_store(store_url)
            except Exception as e:
                console.print(f"[error]❌ Failed: {e}[/error]")
                return

        store_info = scan_data["store"]
        products = scan_data["available_products"]

        # Store info panel
        console.print(Panel(
            f"[bold]{store_info.name}[/bold]\n"
            f"[dim]Domain:[/dim]   {store_info.domain}\n"
            f"[dim]Shopify:[/dim]  {store_info.shop_domain or 'N/A'}\n"
            f"[dim]Currency:[/dim] {store_info.currency}\n"
            f"[dim]EasySell:[/dim] {'✅ Detected' if store_info.has_easysell else '❌ Not found'}\n"
            f"[dim]Products:[/dim] {len(products)} available",
            title="Store Info",
            border_style="green",
        ))

        if products:
            self._display_products(products, detailed=True)

            if Confirm.ask("[bold cyan]Place orders?[/bold cyan]", default=True):
                product_idx = IntPrompt.ask("[bold cyan]Select product #[/bold cyan]", default=1)
                if 1 <= product_idx <= len(products):
                    product = products[product_idx - 1]
                    variant = self._select_variant(product)
                    if variant:
                        count = IntPrompt.ask("[bold cyan]How many orders?[/bold cyan]", default=1)
                        product_url = f"{store_info.url}/products/{product.handle}"
                        await self._execute_orders(store_info, product, variant, product_url, count)
        else:
            console.print("[warning]No products found. Try Target Product mode with a direct URL.[/warning]")

    # ── Mode 4: Settings ──────────────────────────────────────

    def display_settings(self):
        table = Table(
            title="[bold]Current Configuration[/bold]",
            box=box.ROUNDED,
            border_style="cyan",
        )
        table.add_column("Setting", style="bold cyan")
        table.add_column("Value", style="white")

        c = self.config
        table.add_row("Order Quantity", str(c.order.quantity))
        table.add_row("Max Orders", str(c.order.max_orders))
        table.add_row("Delay Range", f"{c.order.delay_between_orders.min}s - {c.order.delay_between_orders.max}s")
        table.add_row("Retry Attempts", str(c.order.retry_attempts))
        table.add_row("Customer Pool", str(len(c.customers)) + " entries")
        table.add_row("Auto-Gen Provinces", str(len(c.auto_generate.provinces)))
        table.add_row("Proxy Enabled", "✅" if c.proxy.enabled else "❌")
        table.add_row("Proxies Loaded", str(len(c.proxy.list)))
        table.add_row("Random UA", "✅" if c.stealth.random_user_agent else "❌")
        table.add_row("Random Delays", "✅" if c.stealth.random_delays else "❌")
        table.add_row("Log File", c.output.log_file)
        table.add_row("Results CSV", c.output.results_file)

        console.print(table)
        console.print()

    # ── UI Helpers ────────────────────────────────────────────

    def _display_product_info(self, product: Product, store_info: StoreInfo):
        """Display a single product's info."""
        variant_lines = ""
        for v in product.variants:
            status = "[green]●[/green]" if v.available else "[red]●[/red]"
            variant_lines += f"\n    {status} {v.title} — ₹{v.price}"

        console.print(Panel(
            f"[bold]{product.title}[/bold]\n"
            f"[dim]Store:[/dim]    {store_info.name}\n"
            f"[dim]Shopify:[/dim]  {store_info.shop_domain}\n"
            f"[dim]Price:[/dim]    ₹{product.price}\n"
            f"[dim]Vendor:[/dim]   {product.vendor}\n"
            f"[dim]Available:[/dim] {'✅' if product.available else '❌'}\n"
            f"[dim]Variants:[/dim] {len(product.variants)}"
            f"{variant_lines}",
            border_style="green",
            title="📦 Product Found",
        ))

    def _display_products(self, products: List[Product], detailed: bool = False):
        table = Table(
            title=f"[bold]Available Products ({len(products)})[/bold]",
            box=box.ROUNDED,
            border_style="green",
        )
        table.add_column("#", style="bold cyan", width=4)
        table.add_column("Product", style="white", max_width=40)
        table.add_column("Price", style="bold green", width=12)
        table.add_column("Variants", style="yellow", width=10)
        table.add_column("Status", width=10)

        if detailed:
            table.add_column("Type", style="dim", width=15)
            table.add_column("Vendor", style="dim", width=15)

        for i, p in enumerate(products, 1):
            avail = sum(1 for v in p.variants if v.available)
            status = "[green]✅ In Stock[/green]" if p.available else "[red]❌ Out[/red]"

            row = [str(i), p.title[:40], f"₹{p.price}", f"{avail}/{len(p.variants)}", status]
            if detailed:
                row.extend([p.product_type or "—", p.vendor or "—"])
            table.add_row(*row)

        console.print(table)
        console.print()

    def _select_variant(self, product: Product) -> Optional[ProductVariant]:
        available = [v for v in product.variants if v.available]

        if not available:
            console.print("[error]No available variants.[/error]")
            return None

        if len(available) == 1:
            v = available[0]
            console.print(f"[info]Auto-selected: {v.title} — ₹{v.price}[/info]")
            return v

        table = Table(
            title="[bold]Select Variant[/bold]",
            box=box.SIMPLE,
            border_style="yellow",
        )
        table.add_column("#", style="bold cyan", width=4)
        table.add_column("Variant", style="white")
        table.add_column("Price", style="bold green")

        for i, v in enumerate(available, 1):
            table.add_row(str(i), v.title, f"₹{v.price}")

        console.print(table)

        idx = IntPrompt.ask("[bold cyan]Select variant #[/bold cyan]", default=1)
        if idx < 1 or idx > len(available):
            console.print("[error]Invalid selection.[/error]")
            return None

        return available[idx - 1]

    def _display_order_summary(
        self, store: StoreInfo, product: Product, variant: ProductVariant, count: int,
    ):
        console.print(Panel(
            f"[bold white]Order Summary[/bold white]\n\n"
            f"  [cyan]Store:[/cyan]    {store.name} ({store.domain})\n"
            f"  [cyan]Shopify:[/cyan]  {store.shop_domain}\n"
            f"  [cyan]Product:[/cyan]  {product.title}\n"
            f"  [cyan]Variant:[/cyan]  {variant.title}\n"
            f"  [cyan]Price:[/cyan]    ₹{variant.price}\n"
            f"  [cyan]Qty/Order:[/cyan] {self.config.order.quantity}\n"
            f"  [cyan]Orders:[/cyan]   {count}\n"
            f"  [cyan]Payment:[/cyan]  Cash on Delivery (COD)\n"
            f"  [cyan]Engine:[/cyan]   EasySell API\n",
            border_style="yellow",
            title="⚡ Attack Plan",
        ))

    async def _execute_orders(
        self,
        store_info: StoreInfo,
        product: Product,
        variant: ProductVariant,
        product_url: str,
        count: int,
    ):
        """Execute batch orders with live display."""
        console.print()
        console.print("[bold magenta]🚀 LAUNCHING ATTACK...[/bold magenta]")
        console.print()

        results_table = Table(
            title="[bold]Order Results[/bold]",
            box=box.ROUNDED,
            border_style="cyan",
        )
        results_table.add_column("#", style="bold", width=4)
        results_table.add_column("Customer", style="white", width=25)
        results_table.add_column("Order", style="bold green", width=14)
        results_table.add_column("Status", width=12)
        results_table.add_column("Total", style="green", width=12)
        results_table.add_column("Error", style="red", max_width=30)

        batch = await self.manager.place_batch_orders(
            store_info=store_info,
            product=product,
            variant=variant,
            product_url=product_url,
            count=count,
        )

        for i, order in enumerate(batch.orders, 1):
            if order.status == OrderStatus.COMPLETED:
                status = "[bold green]✅ SUCCESS[/bold green]"
                order_col = order.order_name or f"#{order.order_number}"
            else:
                status = "[bold red]❌ FAILED[/bold red]"
                order_col = "—"

            results_table.add_row(
                str(i),
                order.customer_name,
                order_col,
                status,
                f"₹{order.total_price}" if order.total_price else "—",
                (order.error or "—")[:30],
            )

        console.print()
        console.print(results_table)

        self._display_batch_summary(batch)

        try:
            self.manager.export_results(batch)
        except Exception:
            pass

    def _display_batch_summary(self, batch: BatchResult):
        success_style = "green" if batch.total_success > 0 else "red"

        console.print(Panel(
            f"[bold white]Attack Summary[/bold white]\n\n"
            f"  [cyan]Total Attempted:[/cyan]  {batch.total_attempted}\n"
            f"  [{success_style}]Successful:[/{success_style}]       {batch.total_success}\n"
            f"  [red]Failed:[/red]            {batch.total_failed}\n"
            f"  [cyan]Success Rate:[/cyan]     {batch.success_rate:.1f}%\n"
            f"  [cyan]Duration:[/cyan]         {batch.duration:.1f}s\n",
            border_style="magenta",
            title="📊 Results",
        ))


async def main():
    cli = CLI()

    try:
        cli.display_banner()
        cli.load_configuration()

        while True:
            choice = cli.display_main_menu()

            if choice == "1":
                await cli.target_product_mode()
            elif choice == "2":
                await cli.quick_attack()
            elif choice == "3":
                await cli.scan_store_mode()
            elif choice == "4":
                cli.display_settings()
            elif choice == "5":
                console.print("[bold]👋 Goodbye![/bold]")
                break

            console.print()

    except KeyboardInterrupt:
        console.print("\n[warning]Interrupted. Exiting...[/warning]")
    except Exception as e:
        console.print(f"[error]Fatal error: {e}[/error]")
        raise


def run():
    asyncio.run(main())
