# Integration tests for iverilog tool wrappers.

# Run with: python -m pytest tests/test_tools.py -v
# Or standalone: python tests/test_tools.py

import sys
from pathlib import Path
import shutil
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.iverilog import iverilog_compile, vvp_simulate

# Skip the whole module if Icarus Verilog is not available in PATH.
if shutil.which("iverilog") is None or shutil.which("vvp") is None:
  pytest.skip("Icarus Verilog (iverilog/vvp) not installed; skipping integration tests.", allow_module_level=True)


# A trivially correct testbench should compile.
def test_compile_simple_pass():
    dut = """
module TopModule (output zero);
  assign zero = 1'b0;
endmodule
"""
    testbench = """
`timescale 1ns/1ps
module tb();
  wire zero;
  TopModule top_module1 (.zero(zero));

  initial begin
    #10;
    if (zero !== 1'b0) begin
      $display("FAIL: zero should be 0, got %b", zero);
    end else begin
      $display("PASS");
    end
    #10 $finish;
  end
endmodule
"""
    result = iverilog_compile(testbench, dut)
    print(f"Compile result: success={result.success}, output={result.output}")
    assert result.success, f"Expected compilation to pass: {result.output}"
    assert result.binary_path is not None


# A testbench with syntax errors should fail gracefully.
def test_compile_syntax_error():
    dut = """
module TopModule (output zero);
  assign zero = 1'b0;
endmodule
"""
    testbench = """
module tb()  // missing semicollon
  wire zero;
  TopModule top_module1 (.zero(zero));
  initial begin #10 $finish; end
endmodule
"""
    result = iverilog_compile(testbench, dut)
    print(f"Compile result: success={result.success}, output={result.output}")
    assert not result.success
    assert result.binary_path is None


# A correct testbench should simulate without mismatches.
def test_simulate_pass():
    dut = """
module TopModule (output zero);
  assign zero = 1'b0;
endmodule
"""
    testbench = """
`timescale 1ns/1ps
module tb();
  wire zero;
  TopModule top_module1 (.zero(zero));

  initial begin
    #10;
    if (zero !== 1'b0)
      $display("FAIL");
    else
      $display("PASS");
    $finish;
  end
endmodule
"""
    compile_result = iverilog_compile(testbench, dut)
    assert compile_result.success, f"Compile failed: {compile_result.output}"

    sim_result = vvp_simulate(compile_result.binary_path)
    print(f"Sim result: success={sim_result.success}, output={sim_result.output}")
    assert sim_result.success
    assert "PASS" in sim_result.output


if __name__ == "__main__":
    print("=" * 50)
    print("Testing iverilog tools...")
    print("=" * 50)

    print("\n1. test_compile_simple_pass")
    test_compile_simple_pass()
    print("   OK")

    print("\n2. test_compile_syntax_error")
    test_compile_syntax_error()
    print("   OK")

    print("\n3. test_simulate_pass")
    test_simulate_pass()
    print("   OK")

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
