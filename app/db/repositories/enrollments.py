"""Enrollment repository — STUB.

The enrollments table has been removed.
Client status is now tracked directly in customer_accounts.client_status.
All functions are kept for import compatibility but return empty/None.
"""


def get_all_enrollments(status=None, broker_slug=None, search=None) -> list:
    return []


def get_customer_active_enrollment(customer_email) -> None:
    return None


def get_customer_active_enrollments(customer_email: str) -> list:
    return []


def get_customer_active_enrollment_for_broker(customer_email: str, broker_id: int) -> None:
    return None


def create_enrollment(*args, **kwargs) -> None:
    return None


def update_enrollment_status(eid, status, reviewed_by=None, review_note=None) -> None:
    pass


def get_enrollment(eid) -> None:
    return None
