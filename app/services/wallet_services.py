from datetime import datetime
from bson import ObjectId
from app.db.mongodb import get_database
from app.services.payment_gateway import initiate_collection_payment
from app.services.payment_gateway import initiate_payout, verify_account


GATEWAY_METHODS = {"jazzcash", "easypaisa"}


def normalize_method(method: str) -> str:
    m = method.strip().lower()
    if "jazz" in m:
        return "jazzcash"
    if "easy" in m:
        return "easypaisa"
    return m


def _serialize_transaction(tx: dict) -> dict:
    return {
        "id": str(tx.get("_id")),
        "transaction_type": tx.get("transaction_type"),
        "amount": float(tx.get("amount", 0)),
        "payment_method": tx.get("payment_method", ""),
        "gateway_provider": tx.get("gateway_provider"),
        "gateway_reference": tx.get("gateway_reference"),
        "phone": tx.get("phone"),
        "balance_before": float(tx.get("balance_before", 0)),
        "balance_after": float(tx.get("balance_after", 0)),
        "status": tx.get("status", "success"),
        "payment_url": tx.get("payment_url"),
        "created_at": tx.get("created_at") or datetime.utcnow(),
    }


async def get_or_create_wallet(user_id: str) -> dict:
    db = get_database()
    obj_user_id = ObjectId(user_id)
    wallet = await db.wallets.find_one({"user_id": obj_user_id})

    if wallet:
        return wallet

    now = datetime.utcnow()
    wallet = {
        "user_id": obj_user_id,
        "balance": 0.0,
        "currency": "PKR",
        "created_at": now,
        "updated_at": now,
    }
    result = await db.wallets.insert_one(wallet)
    wallet["_id"] = result.inserted_id
    return wallet


async def get_wallet_summary(user_id: str, limit: int = 20) -> dict:
    db = get_database()
    wallet = await get_or_create_wallet(user_id)
    obj_user_id = ObjectId(user_id)

    tx_docs = (
        await db.wallet_transactions
        .find({"user_id": obj_user_id})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )

    transactions = [_serialize_transaction(tx) for tx in tx_docs]

    return {
        "user_id": user_id,
        "balance": float(wallet.get("balance", 0)),
        "currency": wallet.get("currency", "PKR"),
        "updated_at": wallet.get("updated_at") or datetime.utcnow(),
        "transactions": transactions,
    }


async def apply_wallet_transaction(
    user_id: str,
    transaction_type: str,
    amount: float,
    payment_method: str,
    phone: str | None = None,
) -> tuple[dict, dict]:
    db = get_database()
    wallet = await get_or_create_wallet(user_id)

    current_balance = float(wallet.get("balance", 0))
    if transaction_type == "withdraw" and amount > current_balance:
        raise ValueError("Insufficient balance for withdrawal")

    method_normalized = normalize_method(payment_method)

    # For JazzCash/EasyPaisa, verify account first and create pending tx for gateway settlement.
    if method_normalized in GATEWAY_METHODS:
        verification = await verify_account(provider=method_normalized, phone=phone)
        if not verification.get("is_valid"):
            raise ValueError(verification.get("message") or "Account verification failed")

        pending_doc = {
            "user_id": wallet["user_id"],
            "wallet_id": wallet["_id"],
            "transaction_type": transaction_type,
            "amount": float(amount),
            "payment_method": payment_method,
            "gateway_provider": method_normalized,
            "phone": phone,
            "balance_before": current_balance,
            "balance_after": current_balance,
            "status": "pending",
            "account_verified": True,
            "account_verification": verification.get("raw"),
            "created_at": datetime.utcnow(),
        }

        insert_result = await db.wallet_transactions.insert_one(pending_doc)
        pending_doc["_id"] = insert_result.inserted_id

        if transaction_type == "add":
            gateway_data = await initiate_collection_payment(
                provider=method_normalized,
                amount=float(amount),
                phone=phone,
                internal_tx_id=str(insert_result.inserted_id),
            )
        else:
            gateway_data = await initiate_payout(
                provider=method_normalized,
                amount=float(amount),
                phone=phone,
                internal_tx_id=str(insert_result.inserted_id),
            )

        await db.wallet_transactions.update_one(
            {"_id": insert_result.inserted_id},
            {
                "$set": {
                    "payment_url": gateway_data.get("payment_url"),
                    "gateway_reference": gateway_data.get("gateway_reference"),
                    "gateway_payload": gateway_data.get("raw"),
                }
            },
        )
        pending_doc.update(
            {
                "payment_url": gateway_data.get("payment_url"),
                "gateway_reference": gateway_data.get("gateway_reference"),
                "gateway_payload": gateway_data.get("raw"),
            }
        )
        return wallet, _serialize_transaction(pending_doc)

    next_balance = current_balance + amount if transaction_type == "add" else current_balance - amount
    now = datetime.utcnow()

    tx_doc = {
        "user_id": wallet["user_id"],
        "wallet_id": wallet["_id"],
        "transaction_type": transaction_type,
        "amount": float(amount),
        "payment_method": payment_method,
        "phone": phone,
        "balance_before": current_balance,
        "balance_after": next_balance,
        "status": "success",
        "created_at": now,
    }

    tx_insert = await db.wallet_transactions.insert_one(tx_doc)
    tx_doc["_id"] = tx_insert.inserted_id

    await db.wallets.update_one(
        {"_id": wallet["_id"]},
        {"$set": {"balance": next_balance, "updated_at": now}},
    )

    wallet["balance"] = next_balance
    wallet["updated_at"] = now

    return wallet, _serialize_transaction(tx_doc)


async def confirm_wallet_transaction(user_id: str, transaction_id: str) -> tuple[dict, dict]:
    db = get_database()
    wallet = await get_or_create_wallet(user_id)
    obj_user_id = ObjectId(user_id)

    try:
        tx_obj_id = ObjectId(transaction_id)
    except Exception:
        raise ValueError("Invalid transaction id")

    tx = await db.wallet_transactions.find_one({"_id": tx_obj_id, "user_id": obj_user_id})
    if not tx:
        raise ValueError("Transaction not found")

    if tx.get("status") == "success":
        return wallet, _serialize_transaction(tx)

    if tx.get("status") != "pending":
        raise ValueError("Only pending transactions can be confirmed")

    current_balance = float(wallet.get("balance", 0))
    amount = float(tx.get("amount", 0))
    tx_type = tx.get("transaction_type")
    if tx_type == "add":
        next_balance = current_balance + amount
    elif tx_type == "withdraw":
        if amount > current_balance:
            raise ValueError("Insufficient balance at confirmation time")
        next_balance = current_balance - amount
    else:
        raise ValueError("Unsupported transaction type")
    now = datetime.utcnow()

    await db.wallet_transactions.update_one(
        {"_id": tx_obj_id},
        {
            "$set": {
                "status": "success",
                "balance_before": current_balance,
                "balance_after": next_balance,
                "confirmed_at": now,
            }
        },
    )
    await db.wallets.update_one(
        {"_id": wallet["_id"]},
        {"$set": {"balance": next_balance, "updated_at": now}},
    )

    wallet["balance"] = next_balance
    wallet["updated_at"] = now

    updated_tx = await db.wallet_transactions.find_one({"_id": tx_obj_id})
    return wallet, _serialize_transaction(updated_tx or tx)
