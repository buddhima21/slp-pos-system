# SLP Supermarket POS System

Offline, single-terminal desktop Point-of-Sale application for one supermarket
checkout counter. Built per `SLP_POS_System_SRS.pdf` (SRS v1.0).

- **UI:** Tkinter (Python standard library)
- **Database:** SQLite (single local file, WAL mode)
- **Packaging:** PyInstaller single `.exe`
- **No** internet, server, or card payments in v1.0.

## Layers

```
ui/         Tkinter screens (login, checkout, inventory, reports)
services/   Business logic — cart totals, stock rules, change, auth. No SQL, no Tkinter.
data/       Data-access layer — the ONLY place SQL is written.
db/         Connection helper, schema, migration/seed.
hardware/   Barcode scanner (keyboard-emulation) and receipt printer.
```

Rule: SQL lives only in `data/`. UI never touches the database directly.

## Run (development)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m slp_pos.main
```

First run creates `data_store/slp_pos.db` and a default admin account:

| username | password |
|----------|----------|
| `admin`  | `admin123` |

**Change this password before go-live.**

## Load sample products (for testing)

```bash
python -m slp_pos.db.seed
```

## Tests

```bash
pytest
```

## Build status

Following the SRS development plan (Section 8):

- [x] Phase 1 — Environment & skeleton
- [x] Phase 2 — SQLite schema + migration
- [x] Phase 3 — Inventory screen (add / edit / search, low-stock highlight)
- [x] Phase 4 — Checkout screen (typed search, cart, cash + change, atomic sale)
- [ ] Phase 5 — Barcode scanner
- [ ] Phase 6 — Payment & change
- [ ] Phase 7 — Receipt printing
- [ ] Phase 8 — Login/roles, reports, low-stock, backup
- [ ] Phase 9 — PyInstaller packaging
- [ ] Phase 10 — Parallel run
