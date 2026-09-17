.PHONY: test smoke api

test:
	python -m pytest -q

# DEP-03: Dockerfiles live in docker/ and the compose file too; the ASGI
# target is dip.api.rest_api:app and the CLI is dip.run.
docker-build-web:
	docker build -f docker/Dockerfile.web -t ind-diplomat:web .

docker-build-worker:
	docker build -f docker/Dockerfile.worker -t ind-diplomat:worker .

docker-build-guardian:
	docker build -f docker/Dockerfile.guardian -t ind-diplomat:guardian .

docker-up:
	docker compose -f docker/docker-compose.yml up --build

smoke:
	python -m dip.run "Assess border escalation risk" --country IND --json

api:
	python -m uvicorn dip.api.rest_api:app --host 127.0.0.1 --port 8000


test-swarm:
	PYTHONPATH=src python -m pytest tests/test_multi_agent_protocol.py
