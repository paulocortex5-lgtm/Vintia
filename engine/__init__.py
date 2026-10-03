"""Vantia — Universal Opportunity Engine.

Core packages (``engine.*``) implement the build orchestration defined in
the v4.0 master prompt:

* :mod:`engine.state_manager` — authoritative ``state.json`` (§4)
* :mod:`engine.locking`       — run lock (§0.1 STEP B)
* :mod:`engine.idempotency`   — idempotency registry (§16)
* :mod:`engine.hash_chain`    — cross-run SHA-256 chain (§0)
* :mod:`engine.cost_tracker`  — cost ledger (§0.1 STEP F/J)
* :mod:`engine.execute_step`  — task execution bookkeeping (§0.1 STEP G)

Heavy optional extras are imported lazily by the modules that need them
(PDF/DOCX parsing in Phase 9, Stripe in Phase 12), so ``import engine``
stays light and succeeds even with the minimal runtime installed.
"""

__version__ = "0.4.0"

__all__ = ["__version__"]
