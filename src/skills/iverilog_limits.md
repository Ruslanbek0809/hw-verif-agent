---
name: icarus_verilog_limitations
summary: Essential constraints for writing SystemVerilog that compiles in Icarus Verilog.
---
**Skill: Icarus Verilog Limitations**
Your testbench (`tb.sv`) will be compiled and simulated using Icarus Verilog (`iverilog`). Icarus Verilog has limited support for advanced SystemVerilog verification features. 

To ensure successful compilation, you MUST strictly adhere to these rules:
*   **No Classes or OOP:** Do not use `class`, `endclass`, inheritance, or mailboxes.
*   **No Constrained Randomization:** Do not use `std::randomize()`, `rand`, or `randc`. Use basic `$urandom` or `$random` for random stimulus generation instead.
*   **No Functional Coverage:** Do not write `covergroup`, `coverpoint`, or `bins`.
*   **No Assertions:** Avoid complex concurrent assertions (`assert property`). 
*   **Keep it Simple:** Rely on structural Verilog, standard `initial` blocks, basic `always` blocks, arrays, and standard `$display`/`$fwrite` system tasks.