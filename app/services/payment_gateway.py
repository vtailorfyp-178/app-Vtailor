from datetime import datetime
from typing import Any
import re

import httpx

from app.core.config import get_settings


def _provider_config(provider: str) -> tuple[str | None, str | None, str | None]:
    settings = get_settings()
    p = provider.lower()
    if p == "jazzcash":
        return settings.JAZZCASH_MERCHANT_ID, settings.JAZZCASH_API_KEY, settings.JAZZCASH_API_URL
    if p == "easypaisa":
        return settings.EASYPAISA_MERCHANT_ID, settings.EASYPAISA_API_KEY, settings.EASYPAISA_API_URL
    return None, None, None


def _verify_url_for(provider: str) -> str | None:
    settings = get_settings()
    p = provider.lower()
    if p == "jazzcash":
        return settings.JAZZCASH_VERIFY_API_URL
    if p == "easypaisa":
        return settings.EASYPAISA_VERIFY_API_URL
    return None


def _payout_url_for(provider: str) -> str | None:
    settings = get_settings()
    p = provider.lower()
    if p == "jazzcash":
        return settings.JAZZCASH_PAYOUT_API_URL
    if p == "easypaisa":
        return settings.EASYPAISA_PAYOUT_API_URL
    return None


def _is_valid_pk_mobile(phone: str | None) -> bool:
    if not phone:
        return False
    raw = re.sub(r"\s+", "", phone)
    # Accept 03XXXXXXXXX or +923XXXXXXXXX
    return bool(re.match(r"^(03\d{9}|\+923\d{9})$", raw))


async def verify_account(provider: str, phone: str | None) -> dict[str, Any]:
    settings = get_settings()
    merchant_id, api_key, _ = _provider_config(provider)
    verify_api_url = _verify_url_for(provider)

    if not _is_valid_pk_mobile(phone):
        return {
            "is_valid": False,
            "message": "Invalid account number format. Use 03XXXXXXXXX or +923XXXXXXXXX",
            "raw": None,
        }

    if not merchant_id or not api_key or not verify_api_url:
        if settings.WALLET_GATEWAY_SIMULATION:
            # In simulation, valid number format is treated as valid account.
            return {
                "is_valid": True,
                "message": "Account verified (simulation)",
                "raw": {"mode": "simulation", "provider": provider, "phone": phone},
            }
        raise ValueError(
            f"{provider} account verification is not configured. Set verify URL and merchant credentials in backend .env"
        )

    payload = {
        "merchant_id": merchant_id,
        "account": phone,
        "timestamp": datetime.utcnow().isoformat(),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(verify_api_url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise ValueError(f"{provider} account verification failed with status {response.status_code}")

    data = response.json() if response.text else {}
    is_valid = bool(data.get("is_valid") or data.get("valid") or data.get("account_valid"))
    return {
        "is_valid": is_valid,
        "message": data.get("message") or ("Account verified" if is_valid else "Account verification failed"),
        "raw": data,
    }


async def initiate_payout(
    provider: str,
    amount: float,
    phone: str | None,
    internal_tx_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    merchant_id, api_key, _ = _provider_config(provider)
    payout_api_url = _payout_url_for(provider)

    if not merchant_id or not api_key or not payout_api_url:
        if settings.WALLET_GATEWAY_SIMULATION:
            return {
                "payment_url": None,
                "gateway_reference": f"sim-payout-{provider}-{internal_tx_id}",
                "raw": {
                    "mode": "simulation",
                    "provider": provider,
                    "amount": amount,
                    "phone": phone,
                    "instruction": "No external payout page in simulation. Tap Verify Payment in app.",
                },
            }
        raise ValueError(
            f"{provider} payout is not configured. Set payout URL and merchant credentials in backend .env"
        )

    callback_url = f"{settings.WALLET_CALLBACK_BASE_URL}/app/api/v1/wallet/gateway/callback/{provider}"
    payload = {
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": "PKR",
        "beneficiary_account": phone,
        "merchant_tx_id": internal_tx_id,
        "callback_url": callback_url,
        "timestamp": datetime.utcnow().isoformat(),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(payout_api_url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise ValueError(f"{provider} payout initiation failed with status {response.status_code}")

    data = response.json() if response.text else {}
    gateway_ref = data.get("transaction_id") or data.get("reference") or data.get("id")
    return {
        "payment_url": data.get("payment_url") or data.get("redirect_url") or None,
        "gateway_reference": gateway_ref,
        "raw": data,
    }


async def initiate_collection_payment(
    provider: str,
    amount: float,
    phone: str | None,
    internal_tx_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    merchant_id, api_key, api_url = _provider_config(provider)

    if not merchant_id or not api_key or not api_url:
        if settings.WALLET_GATEWAY_SIMULATION:
            return {
                "payment_url": None,
                "gateway_reference": f"sim-{provider}-{internal_tx_id}",
                "raw": {
                    "mode": "simulation",
                    "provider": provider,
                    "amount": amount,
                    "phone": phone,
                    "instruction": "No external payment page in simulation. Tap Verify Payment in app.",
                },
            }
        raise ValueError(
            f"{provider} gateway is not configured. Set merchant credentials and API URL in backend .env"
        )

    callback_url = f"{settings.WALLET_CALLBACK_BASE_URL}/app/api/v1/wallet/gateway/callback/{provider}"

    payload = {
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": "PKR",
        "phone": phone,
        "merchant_tx_id": internal_tx_id,
        "callback_url": callback_url,
        "timestamp": datetime.utcnow().isoformat(),
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(api_url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise ValueError(f"{provider} initiation failed with status {response.status_code}")

    data = response.json() if response.text else {}
    payment_url = data.get("payment_url") or data.get("checkout_url") or data.get("redirect_url")
    gateway_ref = data.get("transaction_id") or data.get("reference") or data.get("id")

    return {
        "payment_url": payment_url,
        "gateway_reference": gateway_ref,
        "raw": data,
    }
