import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from catalog.models import (
    Customer,
    Message,
    MessageDirection,
    MessageThread,
    Platform,
    SenderType,
    ThreadStatus,
)
from stores.models import Store
from tenants.models import Tenant

PRESTIA_TENANT_SLUG = "prestia"
PRESTIA_STORE_SLUG = "main"


class Command(BaseCommand):
    help = (
        "Import support customers, threads, and messages from a JSON file. "
        "Uses Prestia tenant/store when --tenant/--store are omitted."
    )

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to the JSON import file.")
        parser.add_argument(
            "--tenant",
            type=str,
            default=PRESTIA_TENANT_SLUG,
            help="Tenant slug (default: prestia).",
        )
        parser.add_argument(
            "--store",
            type=str,
            default=PRESTIA_STORE_SLUG,
            help="Store slug within the tenant (default: main).",
        )

    def handle(self, *args, **options):
        json_path = Path(options["json_file"])
        if not json_path.exists():
            raise CommandError(f"JSON file not found: {json_path}")

        with json_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        try:
            tenant = Tenant.objects.get(slug=options["tenant"])
            store = Store.objects.get(tenant=tenant, slug=options["store"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant not found: {options['tenant']}") from exc
        except Store.DoesNotExist as exc:
            raise CommandError(
                f"Store not found: {options['store']} for tenant {options['tenant']}"
            ) from exc

        customers_created = self._import_customers(tenant, store, payload.get("customers", []))
        threads_created = self._import_threads(
            tenant,
            store,
            payload.get("threads", []),
        )
        messages_created = self._import_messages(
            tenant,
            store,
            payload.get("messages", []),
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Message import complete: "
                f"{customers_created} customers created, "
                f"{threads_created} threads created, "
                f"{messages_created} messages created."
            )
        )

    def _import_customers(self, tenant, store, customers_data):
        created_count = 0
        for item in customers_data:
            platform_user_id = item.get("platform_user_id", "")
            if not platform_user_id:
                raise CommandError("Each customer requires platform_user_id for idempotent import.")

            _, created = Customer.objects.get_or_create(
                tenant=tenant,
                store=store,
                platform=item.get("platform", Platform.MANUAL),
                platform_user_id=platform_user_id,
                defaults={
                    "display_name": item.get("display_name", ""),
                    "email": item.get("email", ""),
                    "phone": item.get("phone", ""),
                    "metadata": item.get("metadata", {}),
                },
            )
            if created:
                created_count += 1
        return created_count

    def _import_threads(self, tenant, store, threads_data):
        created_count = 0
        for item in threads_data:
            external_thread_id = item.get("external_thread_id", "")
            if not external_thread_id:
                raise CommandError("Each thread requires external_thread_id for idempotent import.")

            customer_platform_user_id = item.get("customer_platform_user_id")
            if not customer_platform_user_id:
                raise CommandError(
                    f"Thread {external_thread_id} requires customer_platform_user_id."
                )

            try:
                customer = Customer.objects.get(
                    tenant=tenant,
                    store=store,
                    platform_user_id=customer_platform_user_id,
                )
            except Customer.DoesNotExist as exc:
                raise CommandError(
                    f"Customer not found for platform_user_id={customer_platform_user_id}"
                ) from exc

            _, created = MessageThread.objects.get_or_create(
                tenant=tenant,
                store=store,
                external_thread_id=external_thread_id,
                defaults={
                    "customer": customer,
                    "platform": item.get("platform", Platform.MANUAL),
                    "subject": item.get("subject", ""),
                    "status": item.get("status", ThreadStatus.OPEN),
                    "last_message_at": self._parse_sent_at(item.get("last_message_at")),
                    "metadata": item.get("metadata", {}),
                },
            )
            if created:
                created_count += 1
        return created_count

    def _import_messages(self, tenant, store, messages_data):
        created_count = 0
        for item in messages_data:
            external_thread_id = item.get("external_thread_id")
            external_message_id = item.get("external_message_id", "")
            if not external_thread_id or not external_message_id:
                raise CommandError(
                    "Each message requires external_thread_id and external_message_id."
                )

            try:
                thread = MessageThread.objects.get(
                    tenant=tenant,
                    store=store,
                    external_thread_id=external_thread_id,
                )
            except MessageThread.DoesNotExist as exc:
                raise CommandError(
                    f"Thread not found for external_thread_id={external_thread_id}"
                ) from exc

            _, created = Message.objects.get_or_create(
                thread=thread,
                external_message_id=external_message_id,
                defaults={
                    "tenant": tenant,
                    "store": store,
                    "direction": item.get("direction", MessageDirection.INBOUND),
                    "sender_type": item.get("sender_type", SenderType.CUSTOMER),
                    "body": item.get("body", ""),
                    "sent_at": self._parse_sent_at(item.get("sent_at")),
                    "metadata": item.get("metadata", {}),
                },
            )
            if created:
                created_count += 1
        return created_count

    @staticmethod
    def _parse_sent_at(value):
        if not value:
            from django.utils import timezone

            return timezone.now()
        parsed = parse_datetime(value)
        if parsed is None:
            raise CommandError(f"Invalid datetime value: {value}")
        return parsed
