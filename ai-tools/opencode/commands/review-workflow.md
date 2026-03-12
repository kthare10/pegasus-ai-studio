---
description: Audit a Pegasus workflow against best practices
---
Audit the Pegasus workflow in the specified directory against best practices.
$ARGUMENTS

## Steps

### Step 1: Read all workflow files

- `workflow_generator.py`
- All files in `bin/` (wrapper scripts)
- `Docker/*` (Dockerfile)
- `README.md` (if exists)

### Step 2: Check each category

For each item, report **PASS**, **ERROR**, **WARNING**, or **SUGGESTION**.

**Category 1 — Transformation Catalog:**
- Every `Transformation(pfn=...)` path exists
- `is_stageable` is correct (True for submit host scripts, False for container-embedded)
- Support files (R, JAR) are NOT here (they go in Replica Catalog)
- Container image string is `docker://user/image:tag`
- Memory/cores set per tool

**Category 2 — Replica Catalog:**
- All support files registered
- All input data files registered (unless API-fetched)
- Paths use `"file://" + os.path.abspath(path)`

**Category 3 — DAG:**
- `infer_dependencies=True` used
- File objects shared between producer/consumer (same Python object)
- `stage_out=True` only on final outputs
- `register_replica=False` on all outputs
- Job `_id` values are unique

**Category 4 — File I/O Matching (CRITICAL):**
- Wrapper argparse matches generator `add_args()`
- Filenames in `--input`/`--output` match `File()` LFNs
- `os.makedirs` for subdirectory output paths
- No `glob()`/`os.listdir()` directory scanning
- No `__file__`-relative paths for support files

**Category 5 — Wrapper Scripts:**
- Exit code propagation (`sys.exit(result.returncode)`)
- Command logging for debugging
- Shell wrappers: `set -euo pipefail`
- Fan-in: `action="append"` or `nargs="+"` (not directory scanning)

**Category 6 — Resources:**
- Memory reasonable per tool
- Cores match tool `--threads` args

**Category 7 — Dockerfile:**
- All tools installed
- `PYTHONUNBUFFERED=1` set
- Versions pinned

**Category 8 — CLI/Usability:**
- `--help` produces useful output
- Standard flags: `-s`, `-e`, `-o`
- Input validation

### Step 3: Generate report

```
## Pegasus Workflow Review: [name]

### Summary
- Errors: N
- Warnings: N
- Suggestions: N

### Errors
1. [ERROR] Category N: description
   File: path:line_number
   Fix: what to change

### Warnings
1. [WARNING] Category N: description
   Fix: recommendation

### Suggestions
1. [SUGGESTION] Category N: description
```

Read `AGENTS.md` for the full reference patterns to compare against.
