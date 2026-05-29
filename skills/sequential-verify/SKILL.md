---
name: sequential-verify
description: Verification SOP for sequential circuits (clocked, stateful, FSMs)
---

# Sequential Circuit Verification

## When to Use
Load this skill when the DUT has a clock input, uses flip-flops or latches, or implements a state machine.

## Testbench Structure

1. **Clock generation**: Free-running clock with defined period
2. **Reset sequence**: Assert reset, hold for N cycles, deassert
3. **DUT instantiation**: With clock, reset, and data signals
4. **Stimulus**: Applied synchronous to clock edges
5. **Checking**: Sample outputs at appropriate clock edges

## Clock Generation

```systemverilog
reg clk = 0;
always #5 clk = ~clk;  // 10ns period = 100MHz
```

## Reset Sequence

```systemverilog
initial begin
    reset = 1;
    @(posedge clk);
    @(posedge clk);
    reset = 0;
end
```

## Stimulus Strategy

1. Reset behavior: verify all outputs go to known state
2. Single-cycle operations: one input change per clock
3. Multi-cycle sequences: state machine transitions
4. Hold inputs stable: check output settles
5. Back-to-back operations: stress pipeline/timing

## Checking Pattern

Sample outputs on the next clock edge after stimulus:
```systemverilog
@(posedge clk);
#1;  // Small delta after edge for output to settle
if (dut_output !== expected) ...
```

## FSM-Specific

- Test all state transitions (cover the state graph)
- Test illegal/unexpected inputs in each state
- Verify reset returns to initial state from any state
- Check output values in each state

## Common Pitfalls

- Checking output on the same edge as the driving input (race condition)
- Forgetting to reset before test starts
- Not waiting enough cycles for pipeline stages
- Clock/reset polarity mismatch (posedge vs negedge, active-high vs active-low)
