from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Locator


@dataclass
class ResponseLike:
    status: Optional[int] = None
    url: str = ""
    body: str = ""


def is_inside_ion_searchbar(locator: Locator) -> bool:
    """Return True if the element is inside an ion-searchbar container.

    Uses DOM closest() to detect Ionic searchbar wrappers to avoid false matches.
    """
    try:
        return bool(locator.evaluate("el => !!el.closest('ion-searchbar')"))
    except Exception:
        return False


def fill_force(locator: Locator, value: str, timeout: int = 30_000) -> None:
    """Robustly fill a field, falling back to JS assignment if needed.

    - Waits for visibility
    - Clicks to focus, clears, then fill()
    - On failure, uses evaluate() to set value and dispatch input/change events
    """
    locator.wait_for(state="visible", timeout=timeout)
    try:
        locator.click()
        locator.fill("")
        locator.fill(str(value), timeout=timeout)
    except Exception:
        try:
            locator.evaluate(
                """
                (el, v) => {
                  try { el.focus(); } catch(e) {}
                  el.value = '';
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.value = String(v);
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                """,
                str(value),
            )
        except Exception:
            # Last resort: try a simple type (may be flaky on some masked inputs)
            try:
                locator.type(str(value), timeout=timeout)
            except Exception:
                pass

