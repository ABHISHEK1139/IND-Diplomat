import logging
import requests

logger = logging.getLogger("DIP3.Layer11.AcademicSearch")

class OpenAlexSearch:
    def __init__(self):
        self.base_url = "https://api.openalex.org/works"

    def search(self, query: str) -> list[dict]:
        try:
            # Example endpoint hitting OpenAlex
            res = requests.get(f"{self.base_url}?search={query}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                results = []
                for work in data.get("results", [])[:5]:
                    results.append({
                        "title": work.get("title"),
                        "doi": work.get("doi")
                    })
                return results
            return []
        except Exception as e:
            logger.warning(f"OpenAlex timeout, using mock. {e}")
            return [{"title": f"Mocked paper for {query}", "doi": "10.mock"}]
