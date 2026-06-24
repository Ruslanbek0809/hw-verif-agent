---
name: sv_csv_logging_safeguards
summary: How to write testbench values to a CSV safely without race conditions or delta-cycle bugs.
---
**Skill: Race-Free CSV Logging**
When logging DUT inputs and outputs to `driver_output.csv`, you must avoid delta-cycle race conditions. If you sample signals exactly on the active clock edge, you might log the old value instead of the updated value.

Follow these rules for your `tb.sv`:
*   **File I/O Setup:** Use an integer file descriptor: `integer fd; fd = $fopen("driver_output.csv", "w");` inside an `initial` block.
*   **Write Headers:** Always write a header row first: `$fwrite(fd, "clk,reset,in_a,out_b\n");`
*   **Sample on the Opposite Edge:** If the DUT updates on the `posedge clk`, log your data on the `negedge clk` to ensure all non-blocking assignments have settled.
    *   *Example:* `always @(negedge clk) $fwrite(fd, "%b,%b,%d,%d\n", clk, reset, in_a, out_b);`
*   **Alternative (Strobe):** If you must log on the `posedge`, use `$strobe` instead of `$fwrite` to delay the write until the end of the current simulation time step.
*   **Close the File:** Always call `$fclose(fd);` before finishing the simulation.