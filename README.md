# HW-Verif-Agent

## Overview

A Python-based LLM agent that autonomously generates Verilog testbenches, compiles them with Icarus Verilog, and iteratively refines them using compiler feedback, RAG, and Skills-based context management.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Icarus Verilog
brew install icarus-verilog   # macOS
# sudo apt install iverilog   # Ubuntu

# 3. Configure API keys
cp config/.env.example config/.env
# Edit config/.env with your keys (For now, free option is Google AI Studio)

# 4. Run tool tests
python tests/test_tools.py

# 5. Run on a single task
python main.py --task Prob001_zero
```

**Skills** are loaded on-demand into the LLM context (not all at once in the system prompt). This is the primary context management approach.

