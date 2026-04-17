"""Wallet business logic — credit, debit, withdrawal processing."""
import structlog

from app.db.connection import get_conn
from app.db.repositories.wallet import (
    create_transaction,
    create_withdrawal_request,
    get_or_create_wallet,
    get_wallet_by_id,
    get_withdrawal_request,
    update_wallet_balance,
    update_withdrawal_status,
)

logger = structlog.get_logger(__name__)

MIN_WITHDRAWAL = 10.0  # minimum withdrawal amount (USD)


def credit_wallet(
    customer_id: int,
    amount: float,
    tx_type: str,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    description: str = "",
    created_by: str = "system",
) -> dict:
    """Add funds to a customer's wallet. Returns the transaction dict."""
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    wallet = get_or_create_wallet(customer_id)
    new_balance = float(wallet["balance"]) + amount

    update_wallet_balance(wallet["id"], new_balance, float(wallet["pending_balance"]))
    tx_id = create_transaction(
        wallet["id"], tx_type, amount, new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        created_by=created_by,
    )

    logger.info("wallet_credited",
                customer_id=customer_id, amount=amount, tx_type=tx_type,
                new_balance=new_balance, tx_id=tx_id)
    return {"tx_id": tx_id, "amount": amount, "new_balance": new_balance}


def debit_wallet(
    customer_id: int,
    amount: float,
    tx_type: str,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    description: str = "",
    created_by: str = "system",
) -> dict:
    """Deduct funds from a customer's wallet."""
    if amount <= 0:
        raise ValueError("Debit amount must be positive")

    wallet = get_or_create_wallet(customer_id)
    if float(wallet["balance"]) < amount:
        raise ValueError(f"Insufficient balance: {wallet['balance']} < {amount}")

    new_balance = float(wallet["balance"]) - amount
    update_wallet_balance(wallet["id"], new_balance, float(wallet["pending_balance"]))
    tx_id = create_transaction(
        wallet["id"], tx_type, -amount, new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        created_by=created_by,
    )

    logger.info("wallet_debited",
                customer_id=customer_id, amount=amount, tx_type=tx_type,
                new_balance=new_balance, tx_id=tx_id)
    return {"tx_id": tx_id, "amount": amount, "new_balance": new_balance}


def request_withdrawal(
    customer_id: int,
    amount: float,
    method: str = "bank_transfer",
    *,
    wallet_address: str | None = None,
    wallet_network: str | None = None,
    bank_info: str | None = None,
) -> dict:
    """Customer requests a withdrawal — deducts from balance, adds to pending."""
    if amount < MIN_WITHDRAWAL:
        raise ValueError(f"Minimum withdrawal is ${MIN_WITHDRAWAL}")

    wallet = get_or_create_wallet(customer_id)
    balance = float(wallet["balance"])
    if balance < amount:
        raise ValueError(f"Insufficient balance: ${balance:.2f}")

    # Move from balance to pending
    new_balance = balance - amount
    new_pending = float(wallet["pending_balance"]) + amount
    update_wallet_balance(wallet["id"], new_balance, new_pending)

    # Create withdrawal request
    wr_id = create_withdrawal_request(
        wallet["id"], amount, method,
        wallet_address=wallet_address,
        wallet_network=wallet_network,
        bank_info=bank_info,
    )

    # Log transaction
    tx_id = create_transaction(
        wallet["id"], "withdrawal", -amount, new_balance,
        reference_type="withdrawal_request",
        reference_id=wr_id,
        description=f"Withdrawal request #{wr_id} — {method}",
        status="pending",
        created_by="customer",
    )

    logger.info("withdrawal_requested",
                customer_id=customer_id, amount=amount, method=method,
                wr_id=wr_id, tx_id=tx_id)
    return {"wr_id": wr_id, "tx_id": tx_id, "amount": amount, "new_balance": new_balance}


def approve_withdrawal(wr_id: int, reviewed_by: str = "admin",
                       tx_hash: str | None = None) -> dict:
    """Admin approves a withdrawal — status moves to 'approved'.

    All updates happen in a single transaction to prevent inconsistency.
    """
    wr = get_withdrawal_request(wr_id)
    if not wr:
        raise ValueError("Withdrawal request not found")
    if wr["status"] != "pending":
        raise ValueError(f"Cannot approve: current status is '{wr['status']}'")

    with get_conn() as conn:
        # Update withdrawal request status
        conn.execute(
            """UPDATE withdrawal_requests
               SET status='approved', reviewed_by=?, reviewed_at=GETDATE(), tx_hash=?
               WHERE id=?""",
            (reviewed_by, tx_hash, wr_id),
        )

        # Move from pending_balance
        wallet_row = conn.execute(
            "SELECT * FROM customer_wallets WHERE id=?", (wr["wallet_id"],)
        ).fetchone()
        if wallet_row:
            new_pending = max(0, float(wallet_row["pending_balance"]) - float(wr["amount"]))
            conn.execute(
                "UPDATE customer_wallets SET pending_balance=?, updated_at=GETDATE() WHERE id=?",
                (new_pending, wr["wallet_id"]),
            )

    logger.info("withdrawal_approved", wr_id=wr_id, reviewed_by=reviewed_by)
    return {"wr_id": wr_id, "status": "approved"}


def complete_withdrawal(wr_id: int, reviewed_by: str = "admin",
                        tx_hash: str | None = None) -> dict:
    """Admin marks withdrawal as completed (funds sent).

    All updates happen in a single transaction to prevent inconsistency.
    """
    wr = get_withdrawal_request(wr_id)
    if not wr:
        raise ValueError("Withdrawal request not found")
    if wr["status"] not in ("approved", "pending"):
        raise ValueError(f"Cannot complete: current status is '{wr['status']}'")

    with get_conn() as conn:
        # If still pending, remove from pending_balance
        if wr["status"] == "pending":
            wallet_row = conn.execute(
                "SELECT * FROM customer_wallets WHERE id=?", (wr["wallet_id"],)
            ).fetchone()
            if wallet_row:
                new_pending = max(0, float(wallet_row["pending_balance"]) - float(wr["amount"]))
                conn.execute(
                    "UPDATE customer_wallets SET pending_balance=?, updated_at=GETDATE() WHERE id=?",
                    (new_pending, wr["wallet_id"]),
                )

        # Update withdrawal request status
        conn.execute(
            """UPDATE withdrawal_requests
               SET status='completed', reviewed_by=?, reviewed_at=GETDATE(), tx_hash=?
               WHERE id=?""",
            (reviewed_by, tx_hash, wr_id),
        )

        # Update the transaction status
        conn.execute(
            """UPDATE wallet_transactions SET status='completed'
               WHERE reference_type='withdrawal_request' AND reference_id=?""",
            (wr_id,),
        )

    logger.info("withdrawal_completed", wr_id=wr_id, tx_hash=tx_hash)
    return {"wr_id": wr_id, "status": "completed"}


def reject_withdrawal(wr_id: int, reviewed_by: str = "admin",
                      admin_note: str = "") -> dict:
    """Admin rejects a withdrawal — refund balance.

    All updates happen in a single transaction to prevent inconsistency.
    """
    wr = get_withdrawal_request(wr_id)
    if not wr:
        raise ValueError("Withdrawal request not found")
    if wr["status"] not in ("pending", "approved"):
        raise ValueError(f"Cannot reject: current status is '{wr['status']}'")

    amount = float(wr["amount"])

    with get_conn() as conn:
        # Read current wallet state inside the transaction
        wallet_row = conn.execute(
            "SELECT * FROM customer_wallets WHERE id=?", (wr["wallet_id"],)
        ).fetchone()
        if not wallet_row:
            raise ValueError("Wallet not found")

        # Refund: move from pending back to balance
        new_balance = float(wallet_row["balance"]) + amount
        new_pending = max(0, float(wallet_row["pending_balance"]) - amount)
        conn.execute(
            "UPDATE customer_wallets SET balance=?, pending_balance=?, updated_at=GETDATE() WHERE id=?",
            (new_balance, new_pending, wr["wallet_id"]),
        )

        # Update withdrawal request status
        conn.execute(
            """UPDATE withdrawal_requests
               SET status='rejected', admin_note=?, reviewed_by=?, reviewed_at=GETDATE()
               WHERE id=?""",
            (admin_note, reviewed_by, wr_id),
        )

        # Mark original transaction as cancelled
        conn.execute(
            """UPDATE wallet_transactions SET status='cancelled'
               WHERE reference_type='withdrawal_request' AND reference_id=?""",
            (wr_id,),
        )

        # Create refund transaction entry
        conn.execute(
            """INSERT INTO wallet_transactions
               (wallet_id, tx_type, amount, balance_after,
                reference_type, reference_id, description, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (wr["wallet_id"], "adjustment", amount, new_balance,
             "withdrawal_request", wr_id,
             f"Refund for rejected withdrawal #{wr_id}",
             "completed", reviewed_by),
        )

    logger.info("withdrawal_rejected", wr_id=wr_id, reviewed_by=reviewed_by)
    return {"wr_id": wr_id, "status": "rejected", "new_balance": new_balance}


def cancel_withdrawal(customer_id: int, wr_id: int) -> dict:
    """Customer cancels their own pending withdrawal.

    All updates happen in a single transaction to prevent inconsistency.
    """
    wr = get_withdrawal_request(wr_id)
    if not wr:
        raise ValueError("Withdrawal request not found")
    if wr["customer_id"] != customer_id:
        raise ValueError("Not your withdrawal request")
    if wr["status"] != "pending":
        raise ValueError(f"Cannot cancel: status is '{wr['status']}'")

    amount = float(wr["amount"])

    with get_conn() as conn:
        wallet_row = conn.execute(
            "SELECT * FROM customer_wallets WHERE id=?", (wr["wallet_id"],)
        ).fetchone()
        if not wallet_row:
            raise ValueError("Wallet not found")

        new_balance = float(wallet_row["balance"]) + amount
        new_pending = max(0, float(wallet_row["pending_balance"]) - amount)

        conn.execute(
            "UPDATE customer_wallets SET balance=?, pending_balance=?, updated_at=GETDATE() WHERE id=?",
            (new_balance, new_pending, wr["wallet_id"]),
        )
        conn.execute(
            """UPDATE withdrawal_requests
               SET status='cancelled', admin_note='Cancelled by customer', reviewed_at=GETDATE()
               WHERE id=?""",
            (wr_id,),
        )
        conn.execute(
            """UPDATE wallet_transactions SET status='cancelled'
               WHERE reference_type='withdrawal_request' AND reference_id=?""",
            (wr_id,),
        )
        conn.execute(
            """INSERT INTO wallet_transactions
               (wallet_id, tx_type, amount, balance_after,
                reference_type, reference_id, description, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (wr["wallet_id"], "adjustment", amount, new_balance,
             "withdrawal_request", wr_id,
             f"Cancelled withdrawal #{wr_id}",
             "completed", "customer"),
        )

    logger.info("withdrawal_cancelled", customer_id=customer_id, wr_id=wr_id)
    return {"wr_id": wr_id, "status": "cancelled", "new_balance": new_balance}
