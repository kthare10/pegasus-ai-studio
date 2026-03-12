---
description: Create a new Pegasus workflow project
---
Create a new Pegasus WMS workflow project based on this request:
$ARGUMENTS

## CRITICAL RULES — Follow Exactly

- **NEVER create files in `/tmp/`** — they are invisible to JupyterLab
- **ALL files MUST go under `/home/jovyan/work/`**
- **You MUST write every file to disk** using the Write tool — do NOT just display code in chat
- **You MUST create ALL FOUR file types**: (1) workflow_generator.py, (2) bin/*.py wrappers, (3) Docker/Dockerfile, (4) README.md. Do NOT skip any. Do NOT tell the user to "add a Dockerfile later" or "feel free to tweak" — create ALL files NOW.
- If the user did not specify a name, ASK them — do NOT invent one
- **Do NOT finish until all four file types exist on disk.** Verify with `ls -R`.

## Steps

### Step 1: Create directory structure

```bash
mkdir -p /home/jovyan/work/<name>-workflow/{bin,Docker}
```

### Step 2: Write `workflow_generator.py`

Use this structure — customize the marked sections:

```python
#!/usr/bin/env python3
"""Pegasus workflow generator for [NAME]."""

import argparse
import logging
import os
import sys
from pathlib import Path

from Pegasus.api import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TOOL_CONFIGS = {
    "step1": {"memory": "2 GB", "cores": 1},
    # Add one entry per pipeline step
}


class MyWorkflow:
    wf = None; sc = None; tc = None; rc = None; props = None
    wf_name = "my_workflow"

    def __init__(self, dagfile="workflow.yml"):
        self.dagfile = dagfile
        self.wf_dir = str(Path(__file__).parent.resolve())
        self.shared_scratch_dir = os.path.join(self.wf_dir, "scratch")
        self.local_storage_dir = os.path.join(self.wf_dir, "output")

    def write(self):
        if self.sc is not None: self.sc.write()
        self.props.write(); self.rc.write(); self.tc.write()
        self.wf.write(file=self.dagfile)

    def create_pegasus_properties(self):
        self.props = Properties()
        self.props["pegasus.transfer.threads"] = "16"

    def create_sites_catalog(self, exec_site_name="condorpool"):
        self.sc = SiteCatalog()
        local = Site("local").add_directories(
            Directory(Directory.SHARED_SCRATCH, self.shared_scratch_dir)
            .add_file_servers(FileServer("file://" + self.shared_scratch_dir, Operation.ALL)),
            Directory(Directory.LOCAL_STORAGE, self.local_storage_dir)
            .add_file_servers(FileServer("file://" + self.local_storage_dir, Operation.ALL)),
        )
        exec_site = Site(exec_site_name).add_condor_profile(universe="vanilla").add_pegasus_profile(style="condor")
        self.sc.add_sites(local, exec_site)

    def create_transformation_catalog(self, exec_site_name="condorpool"):
        self.tc = TransformationCatalog()
        container = Container("my_container",
            container_type=Container.SINGULARITY,
            image="docker://username/image:latest",
            image_site="docker_hub")
        transformations = []
        for tool_name, config in TOOL_CONFIGS.items():
            tx = Transformation(tool_name, site=exec_site_name,
                pfn=os.path.join(self.wf_dir, f"bin/{tool_name}.py"),
                is_stageable=True, container=container,
            ).add_pegasus_profile(memory=config["memory"], cores=config.get("cores", 1))
            transformations.append(tx)
        self.tc.add_containers(container)
        self.tc.add_transformations(*transformations)

    def create_replica_catalog(self):
        self.rc = ReplicaCatalog()
        # Register input files here

    def create_workflow(self, args):
        self.wf = Workflow(self.wf_name, infer_dependencies=True)
        # Build DAG: create Jobs with add_args, add_inputs, add_outputs
        # Rules: stage_out=True ONLY on final outputs, register_replica=False on ALL outputs
        # Share File objects between producer/consumer jobs


def main():
    parser = argparse.ArgumentParser(description="[NAME] workflow generator")
    parser.add_argument("-s", "--skip-sites-catalog", action="store_true")
    parser.add_argument("-e", "--execution-site-name", default="condorpool")
    parser.add_argument("-o", "--output", default="workflow.yml")
    # Add workflow-specific arguments here
    args = parser.parse_args()

    workflow = MyWorkflow(dagfile=args.output)
    workflow.create_pegasus_properties()
    if not args.skip_sites_catalog:
        workflow.create_sites_catalog(args.execution_site_name)
    workflow.create_transformation_catalog(args.execution_site_name)
    workflow.create_replica_catalog()
    workflow.create_workflow(args)
    workflow.write()
    logger.info(f"Workflow written to {args.output}")


if __name__ == "__main__":
    main()
```

### Step 3: Write `bin/<step>.py` for each pipeline step

```python
#!/usr/bin/env python3
"""[Description of step]."""
import argparse, logging, os, subprocess, sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="[Step] wrapper")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir: os.makedirs(out_dir, exist_ok=True)

    cmd = ["tool", "--input", args.input, "--output", args.output]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    if not os.path.exists(args.output):
        logger.error(f"Output not found: {args.output}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

After writing, run: `chmod +x bin/*.py`

### Step 4: Write `Docker/Dockerfile` (MANDATORY — do NOT skip)

```dockerfile
FROM python:3.8-slim
RUN apt-get update && apt-get install -y --no-install-recommends wget curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pandas numpy matplotlib requests
ENV PYTHONUNBUFFERED=1
CMD ["/bin/bash"]
```

### Step 5: Write `README.md` (MANDATORY — do NOT skip)

Include: pipeline overview, directory structure, prerequisites, usage (CLI options, submit, monitor), outputs.

### Step 6: Verify all files exist

```bash
ls -R /home/jovyan/work/<name>-workflow/
```

Show the listing to the user. Verify ALL FOUR mandatory files exist:
1. `workflow_generator.py` — if missing, STOP and write it
2. `bin/*.py` — if missing, STOP and write them
3. `Docker/Dockerfile` — if missing, STOP and write it
4. `README.md` — if missing, STOP and write it

**Do NOT respond to the user until all four exist on disk.**

Read `AGENTS.md` for detailed Pegasus patterns and examples.
