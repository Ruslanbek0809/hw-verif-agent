---
name: python_checker_xz
summary: How to handle 'x' and 'z' values in the CSV output.
---
**Skill: Python Checker 'x' and 'z' Handling**
When writing a Python checker for SystemVerilog simulations, remember that the CSV output may contain "x" (unknown) or "z" (high impedance) instead of integers for uninitialized signals. Your Python script MUST handle these string values appropriately without crashing (e.g., catching ValueError when casting to int, and logging a mismatch).
