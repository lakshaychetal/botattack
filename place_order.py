"""Place a real order with specific name: Lakshay Chetal"""
import asyncio
from bot.config import load_config, CustomerAddress
from bot.stealth import StealthClient
from bot.scraper import ShopifyScraper
from bot.checkout import CheckoutEngine
from bot.identity import IdentityGenerator

PRODUCT_URL = "https://duragadgets.in/products/backshield-back-pain-relief-patches"


async def place_order():
    config = load_config()
    client = StealthClient(config)
    scraper = ShopifyScraper(client)
    id_gen = IdentityGenerator(config)

    print("🎯 Fetching product...")
    product = await scraper.get_single_product(PRODUCT_URL)
    if not product:
        print("❌ Product not found")
        return

    print(f"✅ {product.title}")

    print("🏪 Getting store info...")
    store_info = await scraper.get_store_info_from_page(PRODUCT_URL)
    print(f"✅ Shop: {store_info.shop_domain}")

    # Generate identity but override name
    customer = id_gen.generate()
    customer.first_name = "Lakshay"
    customer.last_name = "Chetal"
    
    print(f"\n📦 Order Details:")
    print(f"   Name: {customer.first_name} {customer.last_name}")
    print(f"   Phone: {customer.phone}")
    print(f"   Address: {customer.address1}")
    print(f"   Area: {customer.address2}")
    print(f"   City: {customer.city}")
    print(f"   State: {customer.province} ({customer.province_code})")
    print(f"   PIN: {customer.zip}")
    print(f"   Email: {customer.email}")

    # Select first variant
    variant = product.variants[0]
    print(f"\n💰 Product: {variant.title} — ₹{variant.price}")

    print("\n🚀 Placing COD order...")
    engine = CheckoutEngine(
        store_url=store_info.url,
        store_info=store_info,
        client=client,
        config=config,
    )

    result = await engine.place_order(
        product=product,
        variant=variant,
        customer=customer,
        product_url=PRODUCT_URL,
        quantity=1,
    )

    print(f"\n{'='*60}")
    if result.status.value == "completed":
        print(f"✅ ORDER PLACED SUCCESSFULLY!")
        print(f"   Order Name: {result.order_name}")
        print(f"   Order Number: #{result.order_number}")
        print(f"   Order ID: {result.order_id}")
        print(f"   Total: ₹{result.total_price}")
        if result.status_url:
            print(f"   Tracking: {result.status_url}")
        if result.tags:
            print(f"   Tags: {', '.join(result.tags)}")
    else:
        print(f"❌ ORDER FAILED")
        print(f"   Status: {result.status.value}")
        print(f"   Error: {result.error}")
    print("="*60)


asyncio.run(place_order())
