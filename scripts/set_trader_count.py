"""Set the displayed promo trader count.

Usage:
    python -m scripts.set_trader_count            # sets to 789
    python -m scripts.set_trader_count <number>   # sets to <number>

Run from project root so env vars (.env) are picked up.
"""
import sys

from app.db.repositories.portal_settings import save_portal_settings, get_portal_settings


def main() -> None:
    new_val = int(sys.argv[1]) if len(sys.argv) > 1 else 789
    before = get_portal_settings().get("promo_trader_count", "(unset)")
    save_portal_settings({"promo_trader_count": str(new_val)})
    print(f"[OK] promo_trader_count: {before} -> {new_val}")


if __name__ == "__main__":
    main()
