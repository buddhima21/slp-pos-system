"""Hardware interfaces: barcode scanner and receipt printer.

The USB barcode scanner needs no code here — it emulates a keyboard, typing
the barcode followed by Enter into whichever field has focus (SRS FR-3.1).
The checkout screen handles that in Phase 5. Receipt printing lands in Phase 7.
"""
