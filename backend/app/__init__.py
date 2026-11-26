"""Backend application package for Autonomous AI Sales Voice Agent."""

import os

# Prevent OpenBLAS/OMP multi-thread buffer over-allocation on Windows during uvicorn --reload
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
