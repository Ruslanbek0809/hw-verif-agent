# Prompt templates for the verification agent.
    # Follows the pattern of separating system prompt (always present, Layer 1) from skill content injected on-demand (Layer 2) per learn-claude-code s05.

# Build the system prompt for the agent (Layer 1 — always present).
def build_system_prompt(skill_descriptions: str = "") -> str:
    skills_section = ""
    if skill_descriptions:
        skills_section = f"""

Available verification knowledge domains:
{skill_descriptions}
"""

    return f"""You are a hardware verification engineer specialized in Verilog testbench generation.

Your task is to generate SystemVerilog testbenches that verify a given design under test (DUT).
The testbench must:
1. Instantiate the DUT module as "TopModule top_module1" (matching VerilogEval convention)
2. Generate appropriate test stimuli covering edge cases
3. Check outputs against expected behavior
4. Report pass/fail status via $display statements ("PASS" or "FAIL: <reason>")
5. Include a timeout to prevent infinite simulation (e.g., #1000000 $finish)
6. End with $finish after all checks complete

CRITICAL VERILOG RULES (strictly follow):
- Never use 'int' type — use 'integer' instead
- Never declare variables inside initial blocks — declare all variables at module level
- Use 'reg' for all testbench variables driven in initial/always blocks
- Use only Verilog-2001 compatible syntax

Output ONLY the testbench code inside ```verilog fences.
Do not include the DUT code in the testbench — it will be compiled separately.
{skills_section}"""


# Build the initial testbench generation prompt.
def build_generation_prompt(
    dut_description: str,
    dut_code: str,
    skill_context: str = "",
) -> str:
    skill_section = ""
    if skill_context:
        skill_section = f"""
## Verification Guidelines
{skill_context}
"""

    return f"""Generate a SystemVerilog testbench for the following design.

## Design Description
{dut_description}

## DUT Module Code
```verilog
{dut_code}
```
{skill_section}
## Requirements
- Declare a module `tb` (no ports)
- Instantiate the DUT as `TopModule top_module1 (.port(signal), ...)`
- Connect all DUT ports to testbench signals
- Generate comprehensive test stimuli that cover:
  - Normal operation cases
  - Edge cases and boundary conditions
  - For sequential circuits: proper clock and reset sequences
- Verify DUT outputs match expected behavior
- Use $display("PASS") when all checks pass
- Use $display("FAIL: ...") with details when a check fails
- Add a simulation timeout: initial begin #1000000 $display("TIMEOUT"); $finish; end
- Use `timescale 1ns/1ps

Write the complete testbench module inside ```verilog fences."""


# Build a refinement prompt using compiler/simulation errors as feedback.
def build_refinement_prompt(
    dut_description: str,
    dut_code: str,
    current_testbench: str,
    error_message: str,
    error_type: str,
    skill_context: str = "",
) -> str:
    if error_type == "compilation":
        instruction = """The testbench failed to compile with Icarus Verilog.
Fix the syntax/semantic errors shown below. Output the COMPLETE corrected testbench."""
    else:
        instruction = """The testbench compiled but the simulation produced errors or mismatches.
Analyze the simulation output below and fix the testbench logic. Output the COMPLETE corrected testbench."""

    skill_section = ""
    if skill_context:
        skill_section = f"""
## Relevant Debugging Knowledge
{skill_context}
""" 

    return f"""{instruction}

## Design Description
{dut_description}

## DUT Module Code
```verilog
{dut_code}
```

## Current Testbench (with errors)
```verilog
{current_testbench}
```

## {error_type.capitalize()} Error Output
```
{error_message}
```
{skill_section}
Provide the complete corrected testbench inside ```verilog fences.
Do not include the DUT code — only the testbench.
Ensure the DUT is instantiated as `TopModule top_module1`."""
