---
name: bug_detection
summary: Instructions on how to decide if a genuine DUT bug is detected.
---
**Skill: Genuine DUT Bug Detection**
The DUT might contain bugs. If the python checker reports a mismatch, carefully review your Python logic against the DUT Description. If you are highly confident your Python checker and system verilog testbench perfectly match the specification, DO NOT change them just to force a pass. Instead, output a final summary reporting that a genuine DUT bug was found, and DO NOT call any more tools.