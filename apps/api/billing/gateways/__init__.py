"""Payment gateway integrations — one module per provider, a common
interface (base.py's Gateway protocol), credentials resolved per-gym
(FitKhata is not an aggregator: each gym has its own merchant account).
"""

from __future__ import annotations

from billing.gateways.base import Gateway, GatewayNotConfigured
from billing.models import GatewayCredential


def get_gateway(provider: str) -> Gateway:
    if provider == GatewayCredential.Provider.ESEWA:
        from billing.gateways.esewa import EsewaGateway

        return EsewaGateway()
    if provider == GatewayCredential.Provider.KHALTI:
        from billing.gateways.khalti import KhaltiGateway

        return KhaltiGateway()
    if provider == GatewayCredential.Provider.FONEPAY:
        from billing.gateways.fonepay import FonepayGateway

        return FonepayGateway()
    raise GatewayNotConfigured(f"Unknown payment provider: {provider!r}")


__all__ = ["Gateway", "GatewayNotConfigured", "get_gateway"]
