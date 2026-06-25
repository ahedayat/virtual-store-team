from dataclasses import dataclass


@dataclass(frozen=True)
class AIServiceIdentity:
    service_name: str
    tenant_id: str
    store_id: str
    is_authenticated: bool = True
