---
description: Generate a Pegasus wrapper script
---
Generate a Pegasus WMS wrapper script based on this request:
$ARGUMENTS

## CRITICAL RULES

- **You MUST write the file to disk** — do NOT just display code in chat
- **NEVER create files in `/tmp/`** — use `/home/jovyan/work/` only
- Arguments in the wrapper MUST match what `workflow_generator.py` passes in `add_args()`

## Steps

### Step 1: Create directory

```bash
mkdir -p /home/jovyan/work/<workflow-name>/bin
```

### Step 2: Write the wrapper using this template

```python
#!/usr/bin/env python3
"""[Description of what this step does]."""

import argparse
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="[Step description]")
    # Arguments MUST match workflow_generator.py add_args()
    parser.add_argument("--input", required=True, help="Input file")
    parser.add_argument("--output", required=True, help="Output file")
    args = parser.parse_args()

    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")

    # Create output directory if path contains /
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Run the tool
    cmd = ["tool", "--input", args.input, "--output", args.output]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    # Verify output
    if not os.path.exists(args.output):
        logger.error(f"Output not found: {args.output}")
        sys.exit(1)
    logger.info(f"Output written: {args.output}")


if __name__ == "__main__":
    main()
```

### Step 3: Make executable and verify

```bash
chmod +x bin/<step>.py
ls -la bin/
```

### Step 4: Show integration code

Show the Transformation Catalog entry and Job definition for `workflow_generator.py`:

```python
# Transformation Catalog
tx = Transformation("step_name", site=exec_site_name,
    pfn=os.path.join(self.wf_dir, "bin/step_name.py"),
    is_stageable=True, container=container,
).add_pegasus_profile(memory="2 GB", cores=1)

# Job definition
job = Job("step_name", _id=f"step_name_{item}")
job.add_args("--input", input_file, "--output", output_file)
job.add_inputs(input_file)
job.add_outputs(output_file, stage_out=False, register_replica=False)
wf.add_jobs(job)
```

## Key Rules

- NEVER use `glob()`, `os.listdir()`, or directory scanning
- Find support files with `os.path.join(os.getcwd(), "filename")` — NOT `__file__`
- Always propagate exit codes: `sys.exit(result.returncode)`
- Always log the command being run

Read `AGENTS.md` for wrapper script examples and best practices.
