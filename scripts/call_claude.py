import sys
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

prompt_file = sys.argv[1] if len(sys.argv) > 1 else 'scratch/prompt_claude_advisor.txt'
prompt_text = Path(prompt_file).read_text(encoding='utf-8')

print(f"Calling Claude CLI with prompt from {prompt_file} ({len(prompt_text)} chars) via STDIN...")

proc = subprocess.run(
    "claude -p",
    input=prompt_text,
    text=True,
    encoding='utf-8',
    shell=True,
    capture_output=True,
    errors='replace'
)

print(proc.stdout)
if proc.stderr:
    print("--- STDERR ---", file=sys.stderr)
    print(proc.stderr, file=sys.stderr)

sys.exit(proc.returncode)
