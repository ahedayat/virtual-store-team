from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Category, Order, OrderItem, OrderStatus, Product
from stores.models import Store
from tenants.models import Tenant

PRESTIA_TENANT_SLUG = "prestia"
PRESTIA_STORE_SLUG = "main"

PRESTIA_CATEGORIES = [
    {
        "slug": "handbags",
        "name": "Handbags",
        "description": "Structured handbags for everyday and formal occasions.",
    },
    {
        "slug": "shoulder-bags",
        "name": "Shoulder Bags",
        "description": "Comfortable shoulder bags with adjustable straps.",
    },
    {
        "slug": "backpacks",
        "name": "Backpacks",
        "description": "Practical backpacks for work, travel, and daily carry.",
    },
    {
        "slug": "wallets",
        "name": "Wallets",
        "description": "Compact wallets and card holders.",
    },
    {
        "slug": "accessories",
        "name": "Accessories",
        "description": "Bag charms, straps, and small leather goods.",
    },
]

PRESTIA_PRODUCTS = [
    {
        "slug": "milano-leather-tote",
        "sku": "PRS-TOTE-001",
        "name": "Milano Leather Tote",
        "category_slug": "handbags",
        "description": (
            "Full-grain leather tote with interior zip pocket and magnetic closure."
        ),
        "price": Decimal("189.00"),
        "image_url": "https://cdn.example.com/prestia/milano-leather-tote.jpg",
        "metadata": {"material": "leather", "color": "cognac"},
    },
    {
        "slug": "aria-mini-crossbody",
        "sku": "PRS-CROSS-002",
        "name": "Aria Mini Crossbody",
        "category_slug": "shoulder-bags",
        "description": "Compact crossbody with adjustable strap and suede lining.",
        "price": Decimal("129.00"),
        "image_url": "https://cdn.example.com/prestia/aria-mini-crossbody.jpg",
        "metadata": {"material": "leather", "color": "black"},
    },
    {
        "slug": "luna-quilted-shoulder",
        "sku": "PRS-SHLD-003",
        "name": "Luna Quilted Shoulder Bag",
        "category_slug": "shoulder-bags",
        "description": "Quilted shoulder bag with chain-accent strap and gold hardware.",
        "price": Decimal("159.00"),
        "image_url": "https://cdn.example.com/prestia/luna-quilted-shoulder.jpg",
        "metadata": {"material": "vegan leather", "color": "ivory"},
    },
    {
        "slug": "urban-commuter-backpack",
        "sku": "PRS-BPK-004",
        "name": "Urban Commuter Backpack",
        "category_slug": "backpacks",
        "description": (
            "Water-resistant backpack with padded laptop sleeve and side pockets."
        ),
        "price": Decimal("149.00"),
        "image_url": "https://cdn.example.com/prestia/urban-commuter-backpack.jpg",
        "metadata": {"material": "nylon", "color": "charcoal"},
    },
    {
        "slug": "weekend-explorer-backpack",
        "sku": "PRS-BPK-005",
        "name": "Weekend Explorer Backpack",
        "category_slug": "backpacks",
        "description": "Lightweight travel backpack with expandable main compartment.",
        "price": Decimal("175.00"),
        "image_url": "https://cdn.example.com/prestia/weekend-explorer-backpack.jpg",
        "metadata": {"material": "canvas", "color": "olive"},
    },
    {
        "slug": "classic-bifold-wallet",
        "sku": "PRS-WLT-006",
        "name": "Classic Bifold Wallet",
        "category_slug": "wallets",
        "description": "Slim bifold wallet with six card slots and bill compartment.",
        "price": Decimal("59.00"),
        "image_url": "https://cdn.example.com/prestia/classic-bifold-wallet.jpg",
        "metadata": {"material": "leather", "color": "brown"},
    },
    {
        "slug": "zip-around-card-holder",
        "sku": "PRS-WLT-007",
        "name": "Zip-Around Card Holder",
        "category_slug": "wallets",
        "description": "Zip-around card holder with RFID lining and coin pocket.",
        "price": Decimal("45.00"),
        "image_url": "https://cdn.example.com/prestia/zip-around-card-holder.jpg",
        "metadata": {"material": "leather", "color": "burgundy"},
    },
    {
        "slug": "signature-tassel-charm",
        "sku": "PRS-ACC-008",
        "name": "Signature Tassel Charm",
        "category_slug": "accessories",
        "description": "Hand-finished leather tassel charm for bags and keyrings.",
        "price": Decimal("29.00"),
        "image_url": "https://cdn.example.com/prestia/signature-tassel-charm.jpg",
        "metadata": {"material": "leather", "color": "tan"},
    },
    {
        "slug": "woven-strap-kit",
        "sku": "PRS-ACC-009",
        "name": "Woven Strap Kit",
        "category_slug": "accessories",
        "description": "Interchangeable woven strap with gold-tone clasps.",
        "price": Decimal("39.00"),
        "image_url": "https://cdn.example.com/prestia/woven-strap-kit.jpg",
        "metadata": {"material": "cotton blend", "color": "multicolor"},
    },
    {
        "slug": "evening-clutch",
        "sku": "PRS-HB-010",
        "name": "Evening Clutch",
        "category_slug": "handbags",
        "description": "Sleek evening clutch with detachable chain strap.",
        "price": Decimal("99.00"),
        "image_url": "https://cdn.example.com/prestia/evening-clutch.jpg",
        "metadata": {"material": "satin", "color": "emerald"},
    },
]


class Command(BaseCommand):
    help = "Seed the Prestia demo tenant, store, categories, and sample bag products."

    def handle(self, *args, **options):
        tenant, tenant_created = Tenant.objects.get_or_create(
            slug=PRESTIA_TENANT_SLUG,
            defaults={
                "name": "Prestia",
                "settings": {"store_display_name": "Prestia"},
            },
        )

        store, store_created = Store.objects.get_or_create(
            tenant=tenant,
            slug=PRESTIA_STORE_SLUG,
            defaults={
                "name": "Prestia Online Store",
                "timezone": "America/New_York",
                "currency": "USD",
            },
        )

        categories_by_slug = {}
        categories_created = 0
        for category_data in PRESTIA_CATEGORIES:
            category, created = Category.objects.get_or_create(
                tenant=tenant,
                store=store,
                slug=category_data["slug"],
                defaults={
                    "name": category_data["name"],
                    "description": category_data["description"],
                    "is_active": True,
                },
            )
            categories_by_slug[category.slug] = category
            if created:
                categories_created += 1

        products_created = 0
        for product_data in PRESTIA_PRODUCTS:
            category = categories_by_slug[product_data["category_slug"]]
            _, created = Product.objects.get_or_create(
                tenant=tenant,
                store=store,
                sku=product_data["sku"],
                defaults={
                    "slug": product_data["slug"],
                    "name": product_data["name"],
                    "category": category,
                    "description": product_data["description"],
                    "price": product_data["price"],
                    "image_url": product_data["image_url"],
                    "metadata": product_data["metadata"],
                    "is_active": True,
                },
            )
            if created:
                products_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Prestia seed complete: "
                f"tenant {'created' if tenant_created else 'exists'}, "
                f"store {'created' if store_created else 'exists'}, "
                f"{categories_created} categories created, "
                f"{products_created} products created."
            )
        )
