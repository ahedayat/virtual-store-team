<div dir="rtl" align="right">

# پیکربندی Store Profile

تنظیمات store profile، brand tone، metadata فروشگاه و پیکربندی‌های مشابه **بخشی از contract API Prestia برای Botkonak نیستند**.

## مسئولیت Botkonak

موارد زیر در **UI تنظیمات tenant/store Botkonak** پیکربندی و نگهداری می‌شوند، نه از Prestia fetch می‌شوند:

| Setting | Used by | Notes |
|---------|---------|-------|
| Store display name | Content Agent، Coordinator context | مثلاً `store_display_name` در tenant settings |
| Brand voice / tone | Content Agent | `settings.brand_voice` — tone، audience، style notes، language |
| Content agent limits | Content Agent | مثلاً `content_agent_max_drafts_per_run` |
| Timezone | Sales Agent | مرزهای دوره برای «امروز» و «۷ روز گذشته» |
| Default currency | Content Agent، Sales Agent | context نمایش و aggregation |

agentهای Botkonak این مقادیر را از modelهای محلی Django `Store` و `Tenant.settings` پس از پیکربندی manager در dashboard می‌خوانند.

## مسئولیت Prestia

Prestia **نیازی به expose کردن** موارد زیر ندارد:

- `GET /v1/store`
- `GET /v1/tenant`
- هر API store profile یا brand-settings برای Botkonak

scope OAuth token همچنان **کدام فروشگاه Prestia** متصل است را resolve می‌کند؛ هویت store برای agentها از پیکربندی Botkonak به‌علاوه APIهای catalog/order/customer Prestia می‌آید.

## فایل‌های مرتبط Botkonak

- `backend/stores/models.py` — fieldهای `Store`
- `backend/tenants/models.py` — `Tenant.settings`
- `agents/content/brand_voice.py` — استخراج brand voice از تنظیمات محلی
- `agents/coordinator/nodes.py` — `_content_specialist_payload()` store_context از داده محلی
- `backend/tenants/management/commands/seed_prestia.py` — defaultهای demo tenant/store

## سؤال‌های باز

1. آیا Botkonak باید tenant settings را از metadata OAuth Prestia (فقط نام store) در onboarding پر کند — UX اختیاری، نه نیازمندی API Prestia.
2. timezone پیش‌فرض canonical برای فروشگاه‌های ایرانی (`Asia/Tehran`).

</div>
