from decimal import Decimal
from datetime import timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Category, InventoryLevel, Order, OrderItem, OrderStatus, Product
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


PRESTIA_INVENTORY = [
  # Below threshold: available 3 < threshold 10
    {
        "sku": "PRS-TOTE-001",
        "quantity_on_hand": 5,
        "reserved_quantity": 2,
        "low_stock_threshold": 10,
        "reorder_target": 25,
        "location_name": "Main Floor",
    },
    # Exactly at threshold: available 10 == threshold 10 (not low stock)
    {
        "sku": "PRS-CROSS-002",
        "quantity_on_hand": 10,
        "reserved_quantity": 0,
        "low_stock_threshold": 10,
        "reorder_target": 30,
        "location_name": "Main Floor",
    },
    # Above threshold: available 45 > threshold 10
    {
        "sku": "PRS-SHLD-003",
        "quantity_on_hand": 50,
        "reserved_quantity": 5,
        "low_stock_threshold": 10,
        "reorder_target": 40,
        "location_name": "Main Floor",
    },
    # Out of stock: available 0 < threshold 5
    {
        "sku": "PRS-BPK-004",
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "low_stock_threshold": 5,
        "reorder_target": 20,
        "location_name": "Backroom",
    },
    {
        "sku": "PRS-BPK-005",
        "quantity_on_hand": 18,
        "reserved_quantity": 3,
        "low_stock_threshold": 8,
        "reorder_target": 25,
        "location_name": "Main Floor",
    },
    {
        "sku": "PRS-WLT-006",
        "quantity_on_hand": 22,
        "reserved_quantity": 0,
        "low_stock_threshold": 12,
        "reorder_target": 35,
        "location_name": "Main Floor",
    },
    {
        "sku": "PRS-WLT-007",
        "quantity_on_hand": 4,
        "reserved_quantity": 1,
        "low_stock_threshold": 8,
        "reorder_target": 20,
        "location_name": "Main Floor",
    },
    {
        "sku": "PRS-ACC-008",
        "quantity_on_hand": 30,
        "reserved_quantity": 2,
        "low_stock_threshold": 15,
        "reorder_target": 50,
        "location_name": "Accessories Wall",
    },
    {
        "sku": "PRS-ACC-009",
        "quantity_on_hand": 2,
        "reserved_quantity": 0,
        "low_stock_threshold": 6,
        "reorder_target": 18,
        "location_name": "Accessories Wall",
    },
    {
        "sku": "PRS-HB-010",
        "quantity_on_hand": 7,
        "reserved_quantity": 2,
        "low_stock_threshold": 10,
        "reorder_target": 20,
        "location_name": "Main Floor",
    },
]


PRESTIA_ORDERS = [
    {
        "order_number": "PRS-ORD-001",
        "status": OrderStatus.PAID,
        "days_ago": 0,
        "hour": 10,
        "external_customer_ref": "demo-cust-001",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-TOTE-001", "quantity": 1},
            {"sku": "PRS-ACC-008", "quantity": 2},
        ],
    },
    {
        "order_number": "PRS-ORD-002",
        "status": OrderStatus.COMPLETED,
        "days_ago": 0,
        "hour": 14,
        "external_customer_ref": "demo-cust-002",
        "discount_amount": Decimal("10.00"),
        "items": [
            {"sku": "PRS-CROSS-002", "quantity": 1},
            {"sku": "PRS-WLT-006", "quantity": 1},
        ],
    },
    {
        "order_number": "PRS-ORD-003",
        "status": OrderStatus.FULFILLED,
        "days_ago": 1,
        "hour": 11,
        "external_customer_ref": "demo-cust-003",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-BPK-004", "quantity": 1},
            {"sku": "PRS-ACC-009", "quantity": 1},
        ],
    },
    {
        "order_number": "PRS-ORD-004",
        "status": OrderStatus.PAID,
        "days_ago": 3,
        "hour": 16,
        "external_customer_ref": "demo-cust-004",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-SHLD-003", "quantity": 1},
            {"sku": "PRS-HB-010", "quantity": 1},
        ],
    },
    {
        "order_number": "PRS-ORD-005",
        "status": OrderStatus.COMPLETED,
        "days_ago": 5,
        "hour": 9,
        "external_customer_ref": "demo-cust-005",
        "discount_amount": Decimal("5.00"),
        "items": [
            {"sku": "PRS-BPK-005", "quantity": 1},
            {"sku": "PRS-WLT-007", "quantity": 2},
        ],
    },
    {
        "order_number": "PRS-ORD-006",
        "status": OrderStatus.PAID,
        "days_ago": 6,
        "hour": 13,
        "external_customer_ref": "demo-cust-006",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-TOTE-001", "quantity": 2},
        ],
    },
    {
        "order_number": "PRS-ORD-CANCELLED",
        "status": OrderStatus.CANCELLED,
        "days_ago": 2,
        "hour": 12,
        "external_customer_ref": "demo-cust-007",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-CROSS-002", "quantity": 1},
        ],
    },
    {
        "order_number": "PRS-ORD-DRAFT",
        "status": OrderStatus.DRAFT,
        "days_ago": 0,
        "hour": 8,
        "external_customer_ref": "demo-cust-008",
        "discount_amount": Decimal("0.00"),
        "items": [
            {"sku": "PRS-ACC-008", "quantity": 3},
        ],
    },
]


def _placed_at_for_store(store: Store, *, days_ago: int, hour: int):
    store_tz = ZoneInfo(store.timezone)
    local_now = timezone.now().astimezone(store_tz)
    local_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days_ago
    )
    local_placed_at = local_day.replace(hour=hour)
    return local_placed_at.astimezone(dt_timezone.utc)


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

        products_by_sku = {
            product.sku: product
            for product in Product.objects.filter(tenant=tenant, store=store)
        }

        orders_created = 0
        order_items_created = 0
        for order_data in PRESTIA_ORDERS:
            line_items = []
            subtotal = Decimal("0.00")
            for item_data in order_data["items"]:
                product = products_by_sku[item_data["sku"]]
                quantity = item_data["quantity"]
                unit_price = product.price
                line_total = (unit_price * quantity).quantize(Decimal("0.01"))
                subtotal += line_total
                line_items.append(
                    {
                        "product": product,
                        "product_name_snapshot": product.name,
                        "sku_snapshot": product.sku,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                    }
                )

            discount_amount = order_data["discount_amount"]
            total_amount = (subtotal - discount_amount).quantize(Decimal("0.01"))
            placed_at = _placed_at_for_store(
                store,
                days_ago=order_data["days_ago"],
                hour=order_data["hour"],
            )

            order, created = Order.objects.get_or_create(
                tenant=tenant,
                store=store,
                order_number=order_data["order_number"],
                defaults={
                    "status": order_data["status"],
                    "currency": store.currency,
                    "subtotal_amount": subtotal,
                    "discount_amount": discount_amount,
                    "total_amount": total_amount,
                    "placed_at": placed_at,
                    "external_customer_ref": order_data["external_customer_ref"],
                    "metadata": {"seed": "prestia"},
                },
            )
            if created:
                orders_created += 1

            for line_item in line_items:
                _, item_created = OrderItem.objects.get_or_create(
                    order=order,
                    sku_snapshot=line_item["sku_snapshot"],
                    defaults={
                        "tenant": tenant,
                        "store": store,
                        "product": line_item["product"],
                        "product_name_snapshot": line_item["product_name_snapshot"],
                        "quantity": line_item["quantity"],
                        "unit_price": line_item["unit_price"],
                        "line_total": line_item["line_total"],
                    },
                )
                if item_created:
                    order_items_created += 1

        inventory_created = 0
        for inventory_data in PRESTIA_INVENTORY:
            product = products_by_sku[inventory_data["sku"]]
            _, created = InventoryLevel.objects.get_or_create(
                tenant=tenant,
                store=store,
                product=product,
                defaults={
                    "quantity_on_hand": inventory_data["quantity_on_hand"],
                    "reserved_quantity": inventory_data["reserved_quantity"],
                    "low_stock_threshold": inventory_data["low_stock_threshold"],
                    "reorder_target": inventory_data["reorder_target"],
                    "location_name": inventory_data["location_name"],
                    "is_active": True,
                    "metadata": {"seed": "prestia"},
                },
            )
            if created:
                inventory_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Prestia seed complete: "
                f"tenant {'created' if tenant_created else 'exists'}, "
                f"store {'created' if store_created else 'exists'}, "
                f"{categories_created} categories created, "
                f"{products_created} products created, "
                f"{orders_created} orders created, "
                f"{order_items_created} order items created, "
                f"{inventory_created} inventory levels created."
            )
        )
