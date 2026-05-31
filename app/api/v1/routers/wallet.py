from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.routers.auth import get_current_user
from app.schemas.wallet import (
    WalletSummaryResponse,
    WalletTransactionRequest,
    WalletTransactionResponse,
)
from app.services.wallet_services import apply_wallet_transaction, fail_wallet_transaction, get_wallet_summary
from app.services.wallet_services import confirm_wallet_transaction
from app.services.notification_service import create_notification


router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/summary", response_model=WalletSummaryResponse)
async def wallet_summary(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))
    return await get_wallet_summary(user_id=user_id, limit=limit)


@router.post("/transactions", response_model=WalletTransactionResponse)
async def create_wallet_transaction(
    payload: WalletTransactionRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))

    try:
        wallet, tx = await apply_wallet_transaction(
            user_id=user_id,
            transaction_type=payload.transaction_type,
            amount=payload.amount,
            payment_method=payload.payment_method,
            phone=payload.phone,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    summary = await get_wallet_summary(user_id=user_id, limit=20)

    is_pending = tx.get("status") == "pending"
    pending_message = "Complete provider payment to finalize wallet top-up"
    if is_pending and tx.get("transaction_type") == "withdraw":
        pending_message = "Complete provider verification to finalize withdrawal"

    # Fire in-app notification for the wallet event
    tx_type = tx.get("transaction_type", "")
    amount = tx.get("amount", 0)
    method = tx.get("payment_method", "")
    if is_pending:
        notif_title = "Wallet Transaction Pending"
        notif_msg = (
            f"Your {'withdrawal' if tx_type == 'withdraw' else 'top-up'} of Rs. {amount:,.0f}"
            f" via {method} is pending. Complete the provider step to finish."
        )
        notif_type = "wallet_pending"
    else:
        notif_title = "Wallet Transaction Successful"
        notif_msg = (
            f"Rs. {amount:,.0f} {'withdrawn' if tx_type == 'withdraw' else 'added to your wallet'}"
            f" via {method}."
        )
        notif_type = "wallet_confirmed"
    try:
        await create_notification(
            user_id=user_id,
            type=notif_type,
            title=notif_title,
            message=notif_msg,
            data={"transaction_id": str(tx.get("_id", tx.get("id", ""))), "amount": amount},
        )
    except Exception:
        pass  # notification failure must never break the transaction response

    return WalletTransactionResponse(
        status="pending" if is_pending else "success",
        message=pending_message if is_pending else "Transaction completed successfully",
        wallet=summary,
        transaction=tx,
        next_action_url=tx.get("payment_url"),
    )


@router.post("/transactions/{transaction_id}/confirm", response_model=WalletTransactionResponse)
async def confirm_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))

    try:
        wallet, tx = await confirm_wallet_transaction(user_id=user_id, transaction_id=transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    summary = await get_wallet_summary(user_id=user_id, limit=20)

    # Notify user that the transaction was confirmed
    tx_type = tx.get("transaction_type", "")
    amount = tx.get("amount", 0)
    method = tx.get("payment_method", "")
    try:
        await create_notification(
            user_id=user_id,
            type="wallet_confirmed",
            title="Payment Confirmed",
            message=(
                f"Rs. {amount:,.0f} {'withdrawal' if tx_type == 'withdraw' else 'wallet top-up'}"
                f" via {method} has been confirmed."
            ),
            data={"transaction_id": transaction_id, "amount": amount},
        )
    except Exception:
        pass

    return WalletTransactionResponse(
        status="success",
        message="Transaction confirmed",
        wallet=summary,
        transaction=tx,
    )


@router.post("/transactions/{transaction_id}/fail", response_model=WalletTransactionResponse)
async def fail_transaction(
    transaction_id: str,
    payload: dict | None = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))
    reason = None if payload is None else payload.get("reason")

    try:
        wallet, tx = await fail_wallet_transaction(user_id=user_id, transaction_id=transaction_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    summary = await get_wallet_summary(user_id=user_id, limit=20)

    # Notify user that the transaction failed
    tx_type = tx.get("transaction_type", "")
    amount = tx.get("amount", 0)
    try:
        await create_notification(
            user_id=user_id,
            type="wallet_failed",
            title="Transaction Failed",
            message=(
                f"Your {'withdrawal' if tx_type == 'withdraw' else 'top-up'} of Rs. {amount:,.0f}"
                f" could not be completed. {reason or 'Please try again.'}"
            ),
            data={"transaction_id": transaction_id, "amount": amount, "reason": reason or ""},
        )
    except Exception:
        pass

    return WalletTransactionResponse(
        status="failed",
        message=reason or "Transaction failed",
        wallet=summary,
        transaction=tx,
    )


@router.post("/gateway/callback/{provider}")
async def gateway_callback(provider: str, payload: dict):
    # Provider should call this URL after payment completion.
    # Expected payload includes merchant_tx_id (our transaction id) and status.
    tx_id = payload.get("merchant_tx_id") or payload.get("transaction_id")
    tx_status = str(payload.get("status", "")).lower()

    if not tx_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing transaction id in callback")

    if tx_status not in {"success", "paid", "completed", "ok"}:
        return {"status": "ignored", "provider": provider, "message": "Callback received but not successful status"}

    # We don't have user_id in callback payload; resolve from tx document.
    from bson import ObjectId
    from app.db.mongodb import get_database

    db = get_database()
    try:
        tx = await db.wallet_transactions.find_one({"_id": ObjectId(tx_id)})
    except Exception:
        tx = None

    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    await confirm_wallet_transaction(user_id=str(tx.get("user_id")), transaction_id=tx_id)
    return {"status": "success", "provider": provider, "transaction_id": tx_id}
