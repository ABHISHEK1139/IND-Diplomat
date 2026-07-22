import json
import random
from locust import HttpUser, task, between

class DiplomatUser(HttpUser):
    # Simulates users waiting between 1 to 5 seconds before making the next request
    wait_time = between(1, 5)
    
    # List of realistic OSINT queries
    queries = [
        {"query": "Assess the risk of a global pandemic originating from Wuhan.", "country_code": "CHN"},
        {"query": "Analyze Russian troop movements near the Ukrainian border.", "country_code": "RUS"},
        {"query": "Evaluate India's semiconductor manufacturing capability.", "country_code": "IND"},
        {"query": "Assess the economic impact of Houthi attacks in the Red Sea.", "country_code": "YEM"},
        {"query": "Evaluate the likelihood of China invading Taiwan by 2027.", "country_code": "CHN"}
    ]

    @task(3)
    def submit_investigation(self):
        """
        Submits an investigation query to the unified pipeline API.
        This tests the load capacity of the FastAPI server, Neo4j, and the LLM inference endpoints.
        """
        payload = random.choice(self.queries)
        headers = {'Content-Type': 'application/json'}
        
        # Hitting the standard REST endpoint
        with self.client.post("/api/v1/investigate", data=json.dumps(payload), headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("status") in ["COMPLETE", "HUMAN_REVIEW", "WITHHELD"]:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {result.get('status')}")
            else:
                response.failure(f"Failed with status code: {response.status_code}")

    @task(1)
    def check_health(self):
        """
        Simulates regular health checks by monitoring systems.
        """
        self.client.get("/api/v1/health")

    def on_start(self):
        """
        Called when a Locust user starts before any task is scheduled.
        Could be used for authentication if required in the future.
        """
        pass
