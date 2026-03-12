---
description: Generate a Dockerfile for a Pegasus workflow
---
Generate a Dockerfile for a Pegasus workflow based on this request:
$ARGUMENTS

## CRITICAL RULES

- **You MUST write the file to disk** — do NOT just display code in chat
- **NEVER create files in `/tmp/`** — use `/home/jovyan/work/` only
- All tools go in ONE container shared across all workflow jobs

## Steps

### Step 1: Create directory

```bash
mkdir -p /home/jovyan/work/<workflow-name>/Docker
```

### Step 2: Write the Dockerfile

Choose the appropriate base image:

**Option A — pip-based (simple):**
```dockerfile
FROM python:3.8-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget curl && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    pandas==2.0.3 numpy==1.24.4 matplotlib==3.7.5 requests==2.31.0
ENV PYTHONUNBUFFERED=1
CMD ["/bin/bash"]
```

**Option B — micromamba (bioinformatics):**
```dockerfile
FROM mambaorg/micromamba:1.5-jammy
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl xvfb libgl1-mesa-glx libfontconfig1 && \
    rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER
RUN micromamba install -y -n base -c conda-forge -c bioconda \
    python=3.8 [tools] && micromamba clean --all --yes
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/local/bin/_entrypoint.sh"]
CMD ["bash"]
```

### Step 3: Verify and show commands

```bash
ls -la Docker/Dockerfile
```

Show the user:
```bash
docker build -t username/image:latest -f Docker/Dockerfile .
docker run --rm -it username/image:latest bash
docker run --rm username/image:latest which tool1 tool2
docker push username/image:latest
```

## Key Rules

- Pin all tool versions for reproducibility
- Always set `ENV PYTHONUNBUFFERED=1` for Pegasus log capture
- Use `--no-cache-dir` (pip) or `clean --all` (micromamba) for smaller images
- If `is_stageable=False`: COPY wrapper scripts and `chmod +x`
- Do NOT use container `mounts=[]` for data — use CondorIO `transfer_input_files`

Read `AGENTS.md` for Dockerfile patterns and examples.
