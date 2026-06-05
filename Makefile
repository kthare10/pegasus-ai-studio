# PegasusAI Studio — Build & Run
#
# Usage:
#   make build       # Build Docker image
#   make run         # Run container on port 8888
#   make dev-api     # Run backend in dev mode (port 8080)
#   make dev-web     # Run frontend in dev mode (port 3000)
#   make test-api    # Run backend tests
#   make clean       # Remove image

IMAGE  := kthare10/pegasus-ai-studio
TAG    := latest

# Pin the platform: the Dockerfile only installs the full HTCondor daemons and
# the Pegasus planner (pegasus-plan) on amd64 via DEB packages. The arm64 path
# falls back to conda/pip client-only tools, which lack condor_master and
# pegasus-plan. Build/run amd64 (under emulation on Apple Silicon) so the full
# stack is present.
PLATFORM := linux/amd64

.PHONY: build run stop test-api dev-api dev-web clean

# ── Docker ──────────────────────────────────────────────

build:
	docker build --platform $(PLATFORM) -t $(IMAGE):$(TAG) .

run:
	docker run -it --rm \
		--platform $(PLATFORM) \
		--privileged \
		-p 8888:80 \
		-v $$(pwd)/work:/home/pegasus/work \
		--env-file .env \
		$(IMAGE):$(TAG)

stop:
	docker stop $$(docker ps -q --filter ancestor=$(IMAGE):$(TAG)) 2>/dev/null || true

push:
	docker push $(IMAGE):$(TAG)

clean:
	docker rmi $(IMAGE):$(TAG) 2>/dev/null || true

# ── Development ─────────────────────────────────────────

dev-api:
	cd studio-api && \
	source .venv/bin/activate && \
	uvicorn main:app --reload --port 8080

dev-web:
	cd studio-web && npm run dev

test-api:
	cd studio-api && \
	source .venv/bin/activate && \
	pytest tests/ -v

test-web:
	cd studio-web && npm test

install-api:
	cd studio-api && \
	python3 -m venv .venv && \
	source .venv/bin/activate && \
	pip install -r requirements.txt && \
	pip install pytest httpx

install-web:
	cd studio-web && npm install
