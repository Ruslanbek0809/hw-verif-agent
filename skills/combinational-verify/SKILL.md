---
name: combinational-verify
description: Verification SOP for combinational logic circuits (no clock, no state)
---

# Combinational Circuit Verification

## When to Use
Load this skill when the DUT has no clock input, no sequential elements (flip-flops, latches), and outputs depend only on current inputs.

## Testbench Structure

1. **Module declaration**: `module tb();` with signals matching DUT ports
2. **DUT instantiation**: `TopModule top_module1 (.port(signal), ...);`
3. **Stimulus block**: `initial begin` with test vectors
4. **Checking**: Compare outputs immediately after input change (use small #delay)

## Stimulus Strategy

Apply inputs in this order:
1. All zeros
2. All ones
3. One-hot patterns (one input high at a time)
4. Walking patterns for multi-bit inputs
5. Random patterns for wider coverage
6. Boundary values (max, min, overflow edges)

## Checking Pattern

```systemverilog
task check(input [WIDTH-1:0] expected, input [WIDTH-1:0] actual, string msg);
    if (actual !== expected) begin
        $display("FAIL: %s - expected %h, got %h", msg, expected, actual);
        errors = errors + 1;
    end
endtask
```

## Timing

- No clock needed
- Use `#10` between stimulus changes to allow propagation
- Total sim time: proportional to number of test vectors

## Common Pitfalls

- Forgetting to test with X/Z inputs (if applicable)
- Not covering all input combinations for small designs (<= 4 inputs)
- Missing edge cases in arithmetic circuits (overflow, underflow)
