"""
Research Controller - Central Investigation Intelligence
=========================================================
The most critical missing piece in the pipeline.

This module sits between LLM reasoning and the database,
deciding what evidence is required BEFORE answering.

Pipeline:
1. Analyze question → identify information needs
2. Plan retrieval strategy (what indexes, what filters)
3. Execute retrieval → check sufficiency
4. Refine search if needed → iterate
5. Return verified evidence bundle
"""

from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib

from .knowledge_port import KnowledgePort, knowledge_port
from engine.Layer3_StateModel.evidence_gate import evidence_gate
from Core.evidence_db.evidence_store import evidence_store


class QueryType(Enum):
    """Types of diplomatic queries."""
    LEGAL = "legal"           # What does the law/treaty say?
    FACTUAL = "factual"       # What happened?
    TEMPORAL = "temporal"     # How did X change over time?
    COMPARATIVE = "comparative"  # Compare X and Y
    CAUSAL = "causal"         # Why did X happen?
    PREDICTIVE = "predictive" # What will happen if...?
    PROCEDURAL = "procedural" # How to do X?


class EvidenceType(Enum):
    """Types of evidence needed."""
    TREATY_TEXT = "treaty_text"
    LEGAL_PROVISION = "legal_provision"
    OFFICIAL_STATEMENT = "official_statement"
    NEWS_REPORT = "news_report"
    STATISTICAL_DATA = "statistical_data"
    HISTORICAL_RECORD = "historical_record"
    EXPERT_ANALYSIS = "expert_analysis"


@dataclass
class QueryAnalysis:
    """Result of analyzing a query."""
    original_query: str
    query_type: QueryType
    entities: List[Dict[str, str]]      # Countries, orgs, treaties
    temporal_context: Optional[str]      # Time period if relevant
    required_evidence: List[EvidenceType]
    knowledge_spaces: List[str]          # Which indexes to search
    confidence: float
    reasoning: str


@dataclass
class RetrievalPlan:
    """Plan for evidence retrieval."""
    query_analysis: QueryAnalysis
    search_queries: List[Dict[str, Any]]  # {query, index, filters}
    priority_order: List[str]             # Which searches first
    max_documents: int
    time_filter: Optional[Tuple[str, str]]  # (start_date, end_date)


@dataclass
class EvidenceBundle:
    """Bundle of retrieved evidence."""
    documents: List[Dict[str, Any]]
    coverage: Dict[EvidenceType, int]    # How many docs per type
    sufficiency_score: float              # 0-1, is this enough?
    gaps: List[str]                       # What's missing?
    sources_used: Set[str]
    retrieval_rounds: int
    legal_signal_pack: Optional[Dict[str, Any]] = None
    claims: List[Dict[str, Any]] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    evidence_gate: Optional[Dict[str, Any]] = None


class ResearchController:
    """
    Central intelligence that investigates before answering.
    
    Key Principle:
    "The system must know what evidence is required before answering"
    
    This prevents:
    - Hallucination (answering without evidence)
    - Incomplete answers (missing key sources)
    - Wrong timeframe answers (using outdated info)
    
    Usage:
        controller = ResearchController()
        evidence = await controller.investigate("What is RCEP?", ctx)
        # Now evidence.sufficiency_score tells you if you can answer
    """
    
    def __init__(
        self,
        llm_client=None,
        knowledge: Optional[KnowledgePort] = None,
        gap_collector: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    ):
        self.llm = llm_client
        self._knowledge = knowledge or knowledge_port
        self._gap_collector = gap_collector
        self._moltbot_agent = None
        
        # Entity patterns for extraction
        self._country_patterns = [
            r'\b(India|China|USA|United States|Japan|Australia|EU|European Union)\b',
            r'\b(Russia|UK|United Kingdom|Germany|France|Brazil|Canada|South Korea)\b',
            r'\b(Pakistan|Bangladesh|Sri Lanka|Nepal|Myanmar|Thailand|Vietnam)\b',
            r'\b(Indonesia|Malaysia|Singapore|Philippines|ASEAN)\b',
        ]
        
        self._org_patterns = [
            r'\b(UN|United Nations|WTO|World Trade Organization|IMF|World Bank)\b',
            r'\b(NATO|G20|G7|BRICS|SCO|QUAD|AUKUS)\b',
            r'\b(MEA|Ministry of External Affairs|DGFT)\b',
        ]
        
        self._treaty_patterns = [
            r'\b(RCEP|TPP|CPTPP|FTA|Free Trade Agreement)\b',
            r'\b(UNCLOS|Paris Agreement|Geneva Convention)\b',
            r'\b(BIT|Bilateral Investment Treaty|MoU)\b',
        ]
        
        # Query type indicators
        self._query_indicators = {
            QueryType.LEGAL: ['treaty', 'law', 'provision', 'article', 'legal', 'allowed', 'prohibited'],
            QueryType.FACTUAL: ['what', 'who', 'when', 'where', 'happened', 'did'],
            QueryType.TEMPORAL: ['over time', 'history', 'evolution', 'changed', 'trend'],
            QueryType.COMPARATIVE: ['compare', 'versus', 'difference', 'similar', 'vs'],
            QueryType.CAUSAL: ['why', 'because', 'reason', 'caused', 'led to'],
            QueryType.PREDICTIVE: ['will', 'would', 'if', 'future', 'predict'],
            QueryType.PROCEDURAL: ['how to', 'process', 'steps', 'procedure'],
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze a query to determine what evidence is needed.
        
        This is the first step - understanding what we're looking for
        before we search for it.
        """
        query_lower = query.lower()
        
        # 1. Extract entities
        entities = self._extract_entities(query)
        
        # 2. Determine query type
        query_type = self._determine_query_type(query_lower)
        
        # 3. Detect temporal context
        temporal_context = self._detect_temporal_context(query)
        
        # 4. Determine required evidence types
        required_evidence = self._determine_required_evidence(query_type, entities)
        
        # 5. Determine which knowledge spaces to search
        knowledge_spaces = self._determine_knowledge_spaces(query_type, required_evidence)
        
        # 6. Generate reasoning
        reasoning = self._generate_analysis_reasoning(
            query, query_type, entities, temporal_context, required_evidence
        )
        
        return QueryAnalysis(
            original_query=query,
            query_type=query_type,
            entities=entities,
            temporal_context=temporal_context,
            required_evidence=required_evidence,
            knowledge_spaces=knowledge_spaces,
            confidence=0.8 if entities else 0.5,
            reasoning=reasoning
        )
    
    def _extract_entities(self, query: str) -> List[Dict[str, str]]:
        """Extract named entities from query."""
        entities = []
        
        # Countries
        for pattern in self._country_patterns:
            for match in re.finditer(pattern, query, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "type": "country",
                    "normalized": match.group().upper()
                })
        
        # Organizations
        for pattern in self._org_patterns:
            for match in re.finditer(pattern, query, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "type": "organization",
                    "normalized": match.group().upper()
                })
        
        # Treaties
        for pattern in self._treaty_patterns:
            for match in re.finditer(pattern, query, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "type": "treaty",
                    "normalized": match.group().upper()
                })
        
        # Deduplicate
        seen = set()
        unique_entities = []
        for e in entities:
            key = e["normalized"]
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return unique_entities
    
    def _determine_query_type(self, query_lower: str) -> QueryType:
        """Determine the type of query."""
        scores = {}
        
        for qtype, indicators in self._query_indicators.items():
            score = sum(1 for ind in indicators if ind in query_lower)
            scores[qtype] = score
        
        if not any(scores.values()):
            return QueryType.FACTUAL  # Default
        
        return max(scores, key=scores.get)
    
    def _detect_temporal_context(self, query: str) -> Optional[str]:
        """Detect time-related context in query."""
        # Year patterns
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        if year_match:
            return year_match.group()
        
        # Relative time
        if 'current' in query.lower() or 'now' in query.lower():
            return 'current'
        if 'recent' in query.lower():
            return 'recent'
        if 'historical' in query.lower() or 'history' in query.lower():
            return 'historical'
        
        return None
    
    def _determine_required_evidence(
        self, 
        query_type: QueryType, 
        entities: List[Dict]
    ) -> List[EvidenceType]:
        """Determine what types of evidence are needed."""
        required = []
        
        # Based on query type
        if query_type == QueryType.LEGAL:
            required.extend([EvidenceType.TREATY_TEXT, EvidenceType.LEGAL_PROVISION])
        elif query_type == QueryType.FACTUAL:
            required.extend([EvidenceType.NEWS_REPORT, EvidenceType.OFFICIAL_STATEMENT])
        elif query_type == QueryType.TEMPORAL:
            required.extend([EvidenceType.HISTORICAL_RECORD, EvidenceType.NEWS_REPORT])
        elif query_type == QueryType.CAUSAL:
            required.extend([EvidenceType.EXPERT_ANALYSIS, EvidenceType.NEWS_REPORT])
        elif query_type == QueryType.COMPARATIVE:
            required.extend([EvidenceType.TREATY_TEXT, EvidenceType.STATISTICAL_DATA])
        else:
            required.append(EvidenceType.NEWS_REPORT)
        
        # If treaties mentioned, always need treaty text
        if any(e['type'] == 'treaty' for e in entities):
            if EvidenceType.TREATY_TEXT not in required:
                required.append(EvidenceType.TREATY_TEXT)
        
        return required
    
    def _determine_knowledge_spaces(
        self, 
        query_type: QueryType,
        required_evidence: List[EvidenceType]
    ) -> List[str]:
        """Determine which knowledge indexes to search."""
        spaces = set()
        
        # Map evidence types to knowledge spaces
        evidence_to_space = {
            EvidenceType.TREATY_TEXT: "legal",
            EvidenceType.LEGAL_PROVISION: "legal",
            EvidenceType.OFFICIAL_STATEMENT: "event",
            EvidenceType.NEWS_REPORT: "event",
            EvidenceType.STATISTICAL_DATA: "economic",
            EvidenceType.HISTORICAL_RECORD: "event",
            EvidenceType.EXPERT_ANALYSIS: "strategic",
        }
        
        for evidence in required_evidence:
            if evidence in evidence_to_space:
                spaces.add(evidence_to_space[evidence])
        
        return list(spaces) if spaces else ["event"]  # Default to event
    
    def _generate_analysis_reasoning(
        self,
        query: str,
        query_type: QueryType,
        entities: List[Dict],
        temporal_context: Optional[str],
        required_evidence: List[EvidenceType]
    ) -> str:
        """Generate human-readable reasoning for the analysis."""
        parts = [f"Query classified as {query_type.value}."]
        
        if entities:
            entity_strs = [f"{e['text']} ({e['type']})" for e in entities]
            parts.append(f"Entities identified: {', '.join(entity_strs)}.")
        
        if temporal_context:
            parts.append(f"Temporal context: {temporal_context}.")
        
        evidence_strs = [e.value for e in required_evidence]
        parts.append(f"Required evidence: {', '.join(evidence_strs)}.")
        
        return " ".join(parts)
    
    def create_retrieval_plan(self, analysis: QueryAnalysis) -> RetrievalPlan:
        """
        Create a plan for retrieving evidence.
        
        This determines:
        - What queries to run
        - In what order
        - With what filters
        """
        search_queries = []
        
        # Primary query - the original question
        primary_query = {
            "query": analysis.original_query,
            "indexes": analysis.knowledge_spaces,
            "filters": {},
            "priority": 1
        }
        
        # Add entity filter if available
        if analysis.entities:
            primary_query["filters"]["entities"] = [
                e["normalized"] for e in analysis.entities
            ]
        
        search_queries.append(primary_query)
        
        # Secondary queries - focused on specific entities
        for entity in analysis.entities:
            if entity["type"] == "treaty":
                search_queries.append({
                    "query": f"{entity['text']} provisions articles",
                    "indexes": ["legal"],
                    "filters": {"document_type": "treaty"},
                    "priority": 2
                })
            elif entity["type"] == "country":
                search_queries.append({
                    "query": f"{entity['text']} foreign policy relations",
                    "indexes": ["event", "strategic"],
                    "filters": {"country": entity["normalized"]},
                    "priority": 3
                })
        
        # Time filter
        time_filter = None
        if analysis.temporal_context:
            if analysis.temporal_context == "current":
                time_filter = ("2024-01-01", "2026-12-31")
            elif analysis.temporal_context == "recent":
                time_filter = ("2023-01-01", "2026-12-31")
            elif analysis.temporal_context.isdigit():
                year = analysis.temporal_context
                time_filter = (f"{year}-01-01", f"{year}-12-31")
        
        return RetrievalPlan(
            query_analysis=analysis,
            search_queries=search_queries,
            priority_order=["legal", "event", "economic", "strategic"],
            max_documents=20,
            time_filter=time_filter
        )
    
    async def execute_retrieval(
        self, 
        plan: RetrievalPlan,
        retriever=None
    ) -> EvidenceBundle:
        """
        Execute the retrieval plan and gather evidence.
        
        This is where we actually search the knowledge base.
        """
        all_documents = []
        sources_used = set()
        
        # Execute each search query
        for search_config in sorted(plan.search_queries, key=lambda x: x.get("priority", 99)):
            try:
                if retriever:
                    # Use the actual retriever
                    results = retriever.hybrid_search(
                        query=search_config["query"],
                        date_filter=plan.time_filter[0] if plan.time_filter else None,
                        top_k=10
                    )
                else:
                    # Primary Layer-3 -> Layer-2 contract path.
                    response = self._knowledge.search_documents(
                        query=search_config["query"],
                        indexes=search_config.get("indexes") or plan.query_analysis.knowledge_spaces,
                        filters=search_config.get("filters", {}),
                        time_filter=plan.time_filter,
                        top_k=min(10, plan.max_documents),
                    )
                    results = response.documents
                
                for doc in results:
                    doc["_search_query"] = search_config["query"]
                    doc["_search_priority"] = search_config.get("priority", 99)
                    all_documents.append(doc)
                    
                    # Track source
                    source = doc.get("metadata", {}).get("source", "unknown")
                    sources_used.add(source)
                    
            except Exception as e:
                print(f"[ResearchController] Search failed: {e}")
        
        # Layer-1 style dedupe to prevent syndicated-news inflation.
        all_documents = self._deduplicate_documents(all_documents)

        # Calculate coverage
        coverage = self._calculate_coverage(all_documents, plan.query_analysis.required_evidence)
        
        # Calculate sufficiency
        sufficiency_score = self._calculate_sufficiency(coverage, plan.query_analysis.required_evidence)
        
        # Identify gaps
        gaps = self._identify_gaps(coverage, plan.query_analysis.required_evidence)

        # If Layer 3 still has gaps, ask orchestrator-provided collector for more evidence.
        if gaps:
            supplemental = self._collect_with_moltbot(plan.query_analysis, gaps)
            if supplemental:
                for doc in supplemental:
                    doc["_search_query"] = "moltbot_gap_collection"
                    doc["_search_priority"] = 0
                    all_documents.append(doc)
                    source = doc.get("metadata", {}).get("source", "moltbot_scrape")
                    sources_used.add(source)

                coverage = self._calculate_coverage(all_documents, plan.query_analysis.required_evidence)
                sufficiency_score = self._calculate_sufficiency(coverage, plan.query_analysis.required_evidence)
                gaps = self._identify_gaps(coverage, plan.query_analysis.required_evidence)

        legal_signal_pack = None
        if plan.query_analysis.query_type == QueryType.LEGAL and all_documents:
            try:
                legal_signal_pack = self._knowledge.extract_legal_signals(all_documents)
            except Exception as exc:
                print(f"[ResearchController] Legal signal extraction failed: {exc}")

        claims: List[Dict[str, Any]] = []
        try:
            claims = self._knowledge.extract_claims(all_documents)
        except Exception as exc:
            print(f"[ResearchController] Claim extraction failed: {exc}")

        evidence_ids = evidence_store.upsert_documents(all_documents)

        for claim in claims:
            if not claim.get("document_id") and evidence_ids:
                claim["document_id"] = evidence_ids[0]
            try:
                evidence_store.insert_claim(claim)
            except Exception as exc:
                print(f"[ResearchController] Claim persistence failed: {exc}")

        if legal_signal_pack:
            doc_lookup = self._build_document_lookup(all_documents, evidence_ids)
            for signal in legal_signal_pack.get("signals", []):
                provision_id = str(signal.get("provision_id", ""))
                source_hint = provision_id.split(":clause:")[0] if ":clause:" in provision_id else ""
                document_id = doc_lookup.get(source_hint, evidence_ids[0] if evidence_ids else "unknown")
                try:
                    evidence_store.insert_legal_signal(document_id, signal)
                except Exception as exc:
                    print(f"[ResearchController] Legal signal persistence failed: {exc}")

        gate_result = evidence_gate.evaluate(
            documents=all_documents,
            required_evidence=plan.query_analysis.required_evidence,
            claims=claims,
            claim_constraints=self._build_claim_constraints(plan.query_analysis),
        )
        sufficiency_score = min(sufficiency_score, gate_result.score)
        if gate_result.gaps:
            gap_set = set(gaps)
            gap_set.update(gate_result.gaps)
            gaps = sorted(gap_set)
        
        return EvidenceBundle(
            documents=all_documents,
            coverage=coverage,
            sufficiency_score=sufficiency_score,
            gaps=gaps,
            sources_used=sources_used,
            retrieval_rounds=1,
            legal_signal_pack=legal_signal_pack,
            claims=claims,
            evidence_ids=evidence_ids,
            evidence_gate=gate_result.to_dict(),
        )
    
    def _calculate_coverage(
        self, 
        documents: List[Dict], 
        required: List[EvidenceType]
    ) -> Dict[EvidenceType, int]:
        """Calculate how many documents cover each evidence type."""
        coverage = {etype: 0 for etype in required}
        
        # Map document types to evidence types
        type_mapping = {
            "treaty": EvidenceType.TREATY_TEXT,
            "legal": EvidenceType.LEGAL_PROVISION,
            "statement": EvidenceType.OFFICIAL_STATEMENT,
            "news": EvidenceType.NEWS_REPORT,
            "data": EvidenceType.STATISTICAL_DATA,
            "historical": EvidenceType.HISTORICAL_RECORD,
            "analysis": EvidenceType.EXPERT_ANALYSIS,
        }
        
        for doc in documents:
            doc_type = doc.get("metadata", {}).get("type", "news")
            evidence_type = type_mapping.get(doc_type, EvidenceType.NEWS_REPORT)
            
            if evidence_type in coverage:
                coverage[evidence_type] += 1
        
        return coverage
    
    def _calculate_sufficiency(
        self, 
        coverage: Dict[EvidenceType, int],
        required: List[EvidenceType]
    ) -> float:
        """Calculate overall evidence sufficiency score (0-1)."""
        if not required:
            return 1.0
        
        # Each required evidence type should have at least 1 document
        satisfied = sum(1 for etype in required if coverage.get(etype, 0) > 0)
        base_score = satisfied / len(required)
        
        # Bonus for having multiple sources
        total_docs = sum(coverage.values())
        depth_bonus = min(0.2, total_docs * 0.02)  # Up to 0.2 bonus
        
        return min(1.0, base_score + depth_bonus)
    
    def _identify_gaps(
        self, 
        coverage: Dict[EvidenceType, int],
        required: List[EvidenceType]
    ) -> List[str]:
        """Identify what evidence is missing."""
        gaps = []
        
        for etype in required:
            if coverage.get(etype, 0) == 0:
                gaps.append(f"Missing {etype.value} evidence")
        
        return gaps

    def _deduplicate_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique: List[Dict[str, Any]] = []
        for doc in documents:
            digest = self._document_digest(doc)
            if digest in seen:
                continue
            seen.add(digest)
            unique.append(doc)
        return unique

    def _document_digest(self, document: Dict[str, Any]) -> str:
        content = str(document.get("content", "") or "").strip().lower()
        if not content:
            meta = document.get("metadata", {}) or {}
            content = f"{meta.get('source','')}|{meta.get('type','')}|{meta.get('date','')}"
        normalized = " ".join(content.split())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _build_document_lookup(
        self,
        documents: List[Dict[str, Any]],
        evidence_ids: List[str],
    ) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for doc, doc_id in zip(documents, evidence_ids):
            doc_ref = str(doc.get("id") or "")
            source = str(doc.get("metadata", {}).get("source") or "")
            if doc_ref:
                lookup[doc_ref] = doc_id
            if source and source not in lookup:
                lookup[source] = doc_id
        return lookup

    def _build_claim_constraints(self, analysis: QueryAnalysis) -> Optional[Dict[str, Any]]:
        """
        Build claim-level constraints for evidence gating.

        This ensures the gate validates relationship-specific support rather than
        generic document presence.
        """
        countries = [
            str(entity.get("text", "")).strip()
            for entity in analysis.entities
            if entity.get("type") == "country" and str(entity.get("text", "")).strip()
        ]
        if len(countries) < 2:
            return None

        query_lower = analysis.original_query.lower()
        hostile_tokens = (
            "threat", "attack", "war", "military", "sanction",
            "coerc", "blockade", "mobiliz", "warn", "violat",
        )
        hostile_only = any(token in query_lower for token in hostile_tokens)

        return {
            "actors": countries[:2],
            "directed": True,
            "hostile_only": hostile_only,
        }

    def set_gap_collector(self, collector: Optional[Callable[..., List[Dict[str, Any]]]]) -> None:
        """
        Inject a gap-collection function from the orchestrator layer.
        """
        self._gap_collector = collector

    def _get_moltbot_agent(self):
        """
        Backward-compatible accessor used by tests and legacy callers.

        This method no longer imports Layer-1 directly. A collector must be
        injected by orchestration or assigned explicitly.
        """
        if self._moltbot_agent is False:
            return None
        if self._moltbot_agent is not None:
            return self._moltbot_agent
        return self._gap_collector

    def _collect_with_moltbot(
        self,
        analysis: QueryAnalysis,
        gaps: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Route gap-driven collection to Layer 1.
        Returns documents in retrieval-compatible format.
        """
        collector = self._get_moltbot_agent()
        if not collector or not gaps:
            return []

        countries = [
            entity["normalized"]
            for entity in analysis.entities
            if entity.get("type") == "country"
        ]
        required_evidence = [ev.value for ev in analysis.required_evidence]

        try:
            docs: List[Dict[str, Any]]
            if callable(collector):
                docs = collector(
                    query=analysis.original_query,
                    required_evidence=required_evidence,
                    countries=countries,
                    missing_gaps=gaps,
                    limit=10,
                )
            elif hasattr(collector, "collect_documents"):
                docs = collector.collect_documents(
                    query=analysis.original_query,
                    required_evidence=required_evidence,
                    countries=countries,
                    missing_gaps=gaps,
                    limit=10,
                )
            else:
                return []
            return self._annotate_gap_documents(docs, countries)
        except Exception as exc:
            print(f"[ResearchController] MoltBot collection failed: {exc}")
            return []

    def _annotate_gap_documents(
        self,
        documents: List[Dict[str, Any]] | Any,
        countries: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Ensure supplemental docs carry minimum actor metadata for claim-level gating.
        """
        rows = list(documents or []) if isinstance(documents, list) else []
        if not rows:
            return []

        actor_pair = countries[:2] if isinstance(countries, list) else []
        out: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            doc = dict(item)
            meta = dict(doc.get("metadata", {}) or {})
            if actor_pair and "actors" not in meta:
                meta["actors"] = list(actor_pair)
            if "source" not in meta:
                meta["source"] = "moltbot_scrape"
            if "type" not in meta:
                meta["type"] = "news"
            doc["metadata"] = meta
            out.append(doc)
        return out
    
    async def investigate(
        self, 
        query: str, 
        context=None,
        max_rounds: int = 3
    ) -> EvidenceBundle:
        """
        Main entry point - investigate a query completely.
        
        This orchestrates the full investigation loop:
        1. Analyze query
        2. Create retrieval plan
        3. Execute retrieval
        4. Check sufficiency
        5. Refine and repeat if needed
        """
        print(f"[ResearchController] Starting investigation: {query[:50]}...")
        
        # Step 1: Analyze
        analysis = self.analyze_query(query)
        print(f"[ResearchController] Query type: {analysis.query_type.value}")
        print(f"[ResearchController] Entities: {[e['text'] for e in analysis.entities]}")
        print(f"[ResearchController] Required evidence: {[e.value for e in analysis.required_evidence]}")
        
        # Step 2: Plan
        plan = self.create_retrieval_plan(analysis)
        print(f"[ResearchController] Searching {len(plan.search_queries)} queries")
        
        # Step 3: Execute with iteration
        evidence = await self.execute_retrieval(plan)
        round_num = 1
        
        # Step 4: Check and iterate
        while evidence.sufficiency_score < 0.7 and round_num < max_rounds:
            print(f"[ResearchController] Round {round_num}: Sufficiency {evidence.sufficiency_score:.2f}")
            print(f"[ResearchController] Gaps: {evidence.gaps}")
            
            # Refine plan based on gaps
            refined_plan = self._refine_plan(plan, evidence.gaps)
            
            # Execute again
            new_evidence = await self.execute_retrieval(refined_plan)
            
            # Merge results
            evidence.documents.extend(new_evidence.documents)
            evidence.sources_used.update(new_evidence.sources_used)
            evidence.retrieval_rounds += 1
            if new_evidence.legal_signal_pack:
                evidence.legal_signal_pack = new_evidence.legal_signal_pack
            evidence.claims.extend(new_evidence.claims)
            evidence.evidence_ids.extend(new_evidence.evidence_ids)
            if new_evidence.evidence_gate:
                evidence.evidence_gate = new_evidence.evidence_gate
            
            # Recalculate
            evidence.coverage = self._calculate_coverage(
                evidence.documents, 
                analysis.required_evidence
            )
            evidence.sufficiency_score = self._calculate_sufficiency(
                evidence.coverage, 
                analysis.required_evidence
            )
            evidence.gaps = self._identify_gaps(
                evidence.coverage, 
                analysis.required_evidence
            )
            
            round_num += 1
        
        print(f"[ResearchController] Investigation complete.")
        print(f"[ResearchController] Final sufficiency: {evidence.sufficiency_score:.2f}")
        print(f"[ResearchController] Documents collected: {len(evidence.documents)}")
        print(f"[ResearchController] Rounds: {evidence.retrieval_rounds}")
        
        # Store in context if available
        if context:
            context.set("evidence_bundle", evidence)
            context.set("query_analysis", analysis)
        
        return evidence
    
    def _refine_plan(
        self, 
        original_plan: RetrievalPlan, 
        gaps: List[str]
    ) -> RetrievalPlan:
        """Refine retrieval plan based on gaps."""
        new_queries = []
        
        for gap in gaps:
            if "treaty_text" in gap.lower():
                new_queries.append({
                    "query": f"{original_plan.query_analysis.original_query} treaty full text",
                    "indexes": ["legal"],
                    "filters": {"document_type": "treaty"},
                    "priority": 1
                })
            elif "official_statement" in gap.lower():
                new_queries.append({
                    "query": f"{original_plan.query_analysis.original_query} official statement press release",
                    "indexes": ["event"],
                    "filters": {"document_type": "statement"},
                    "priority": 1
                })
            elif "statistical" in gap.lower():
                new_queries.append({
                    "query": f"{original_plan.query_analysis.original_query} data statistics",
                    "indexes": ["economic"],
                    "filters": {},
                    "priority": 1
                })
        
        return RetrievalPlan(
            query_analysis=original_plan.query_analysis,
            search_queries=new_queries,
            priority_order=original_plan.priority_order,
            max_documents=original_plan.max_documents,
            time_filter=original_plan.time_filter
        )


# Singleton instance
research_controller = ResearchController()


__all__ = [
    "ResearchController",
    "research_controller",
    "QueryType",
    "EvidenceType",
    "QueryAnalysis",
    "RetrievalPlan",
    "EvidenceBundle",
]
