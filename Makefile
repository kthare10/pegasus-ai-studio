# Pegasus AI Workbench — Build & Run targets
# Build context is the parent tool/ directory so the Dockerfile
# can COPY pegasus-ai/ and claude-plugin-marketplace/.

IMAGE     := pegasus-ai-workbench
BUILD_CTX := ..
FULL_DF   := pegasus-ai-workbench/Dockerfile
LITE_DF   := pegasus-ai-workbench/Dockerfile.lite

.PHONY: build build-lite build-access run run-lite test push clean

## Build the full image (latest variant)
build:
	docker build -f $(FULL_DF) -t $(IMAGE):latest $(BUILD_CTX)

## Build the lite image (no CLI agents)
build-lite:
	docker build -f $(LITE_DF) -t $(IMAGE):lite $(BUILD_CTX)

## Build the ACCESS variant
build-access:
	docker build -f $(FULL_DF) --build-arg VARIANT=access -t $(IMAGE):access $(BUILD_CTX)

## Run the full image
run:
	docker run --rm -it \
		-p 8888:8888 \
		--env-file .env \
		-v $$(pwd)/work:/home/jovyan/work \
		$(IMAGE):latest

## Run the lite image
run-lite:
	docker run --rm -it \
		-p 8888:8888 \
		--env-file .env \
		-v $$(pwd)/work:/home/jovyan/work \
		$(IMAGE):lite

## Smoke tests — verify all tools are installed
test:
	@echo "=== Smoke testing $(IMAGE):latest ==="
	docker run --rm $(IMAGE):latest bash -c ' \
		set -e; \
		echo "-- Python import pegasus --"; \
		python -c "import Pegasus; print(Pegasus.__file__)"; \
		echo "-- claude --version --"; \
		claude --version; \
		echo "-- opencode --"; \
		which opencode; \
		echo "-- jupyter lab --version --"; \
		jupyter lab --version; \
		echo "-- pegasus-version --"; \
		pegasus-version; \
		echo "=== All smoke tests passed ===" \
	'

## Push images to Docker Hub (kthare10 registry)
push:
	docker tag $(IMAGE):latest kthare10/$(IMAGE):latest
	docker tag $(IMAGE):lite kthare10/$(IMAGE):lite
	docker push kthare10/$(IMAGE):latest
	docker push kthare10/$(IMAGE):lite

## Remove built images
clean:
	docker rmi $(IMAGE):latest $(IMAGE):lite $(IMAGE):access 2>/dev/null || true
