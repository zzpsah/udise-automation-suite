"""UDISE+ SDMS automation — Linux/VPS port of the Colab notebook.

Faithful port of UDISE_Automation_v2.8.0_2026-10-03.ipynb.

Safety model preserved from the notebook:
  - read/preview first, writes require explicit enablement
  - a write is successful only after fresh read-back confirms persistence
  - POST is never blindly retried after an ambiguous failure
  - credentials/cookies stay runtime-only, never logged or written to disk
"""

__version__ = "2.8.0"
__notebook_baseline__ = "UDISE_Automation_v2.8.0_2026-10-03.ipynb"
