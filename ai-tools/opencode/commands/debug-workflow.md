---
description: Diagnose a Pegasus workflow failure
---
Debug a Pegasus workflow failure based on this information:
$ARGUMENTS

## Steps

### Step 1: Gather diagnostics

```bash
pegasus-analyzer <run-dir>
find <run-dir> -name "*.out" -o -name "*.err" | head -20
cat <run-dir>/<job-id>.out
cat <run-dir>/<job-id>.err
```

### Step 2: Match error against known patterns

**File Staging:**
| Error | Cause | Fix |
|-------|-------|-----|
| `No such file or directory` (input) | Missing Replica Catalog entry | Add `rc.add_replica()` |
| `No such file or directory` (support script) | Script in TC not RC | Move to Replica Catalog + job input |
| `No such file or directory` (output subdir) | Missing `os.makedirs` | Add `os.makedirs(os.path.dirname(out), exist_ok=True)` |
| `FileNotFoundError` for `../bin/script.R` | `__file__`-relative path | Use `os.path.join(os.getcwd(), "script.R")` |
| `glob()`/`os.listdir()` empty | Directory scanning | Pass explicit file paths |

**Container:**
| Error | Cause | Fix |
|-------|-------|-----|
| `Unable to pull container` | Image typo | Check `docker://user/image:tag` |
| `command not found` | Tool missing | Add to Dockerfile |
| `ModuleNotFoundError` | Package missing | Add pip/micromamba install |

**Arguments:**
| Error | Cause | Fix |
|-------|-------|-----|
| `unrecognized arguments` | `add_args()` vs argparse mismatch | Align argument names |
| `arguments are required` | Missing `add_args()` | Add the `--flag` |

**Resources:**
| Error | Cause | Fix |
|-------|-------|-----|
| OOM / MemoryError | Too little memory | Increase `memory="N GB"` |
| Timeout | Too slow | Increase timeout or optimize |

**Dependencies:**
| Error | Cause | Fix |
|-------|-------|-----|
| Job runs too early | Missing File dependency | Share File objects between jobs |
| Circular dependency | File is input+output | Fix the cycle |

**Wrappers:**
| Error | Cause | Fix |
|-------|-------|-----|
| Exit 1, no stderr | Missing stderr capture | Add `print(result.stderr, file=sys.stderr)` |
| Permission denied | Not executable | `chmod +x bin/script.py` |
| Output not created | Path mismatch | Match filename to `File()` LFN |

### Step 3: Read source files

Read the failed wrapper, workflow_generator.py, and Dockerfile.

### Step 4: Propose fix

1. Show exact code change (before/after)
2. Explain root cause
3. Show verification command

### Step 5: Prevention

Suggest running `/review` to catch other issues.

Read `AGENTS.md` for additional error patterns and solutions.
