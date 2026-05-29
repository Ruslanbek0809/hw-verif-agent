---
name: error-debug
description: Common iverilog compilation and simulation error patterns and fixes
---

# Iverilog Error Debugging Guide

## When to Use
Load this skill when the compile or simulate step fails and you need to diagnose the error.

## Common Compilation Errors

### Port Connection Errors
- `Unknown module type: TopModule` → The DUT module name doesn't match. Check module declaration.
- `port connection ... is not an input/output` → Port direction mismatch. Verify DUT interface.
- `Unable to bind wire/reg` → Signal declared but not connected, or used before declaration.

### Syntax Errors
- `syntax error, unexpected ...` → Check for missing semicolons, mismatched begin/end, wrong keywords.
- `error: ... is not a valid l-value` → Trying to assign to a wire inside always block (use reg).
- `Register ... is also used as a wire` → Cannot use `wire` for signals assigned in `always` blocks.

### Type Errors
- `Cannot assign to array` → Arrays need index in assignment.
- `Unable to elaborate` → Usually a parameter/generate issue.

## Common Simulation Issues

### Timeout
- Simulation hits `#1000000 $finish` → infinite loop in stimulus or missing end condition.
- Fix: Ensure `initial` blocks terminate, check for infinite `forever` without break.

### X-propagation
- Outputs show `x` → Signals not initialized. Add reset sequence or initial values.

### Mismatch Patterns
- All outputs wrong → Likely DUT instantiation error or inverted logic.
- First few correct, then wrong → State machine issue, check transitions.
- Only specific cases wrong → Edge case in combinational logic.

## Quick Fix Checklist

1. Module name matches exactly (`TopModule` for VerilogEval tasks)
2. All ports connected with correct widths
3. `reg` used for signals assigned in `always`/`initial`; `wire` for continuous assign
4. Clock is toggling if sequential
5. Reset is applied before test vectors
6. Timeout is present to prevent hangs
7. `$finish` is called at end of test
