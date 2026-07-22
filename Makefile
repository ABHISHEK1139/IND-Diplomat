.PHONY: test smoke api

test:
	python -m pytest -q

docker-build-web:
	docker build -f Dockerfile.web -t ind-diplomat:web .

docker-build-worker:
	docker build -f Dockerfile.worker -t ind-diplomat:worker .

docker-build-guardian:
	docker build -f Dockerfile.guardian -t ind-diplomat:guardian .

docker-up:
	docker-compose up --build

smoke:
	python run.py "Assess border escalation risk" --country IND --json

api:
	python -m uvicorn api:app --host 127.0.0.1 --port 8000
