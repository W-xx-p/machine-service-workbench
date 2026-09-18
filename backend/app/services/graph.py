from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


class GraphService:
    """Neo4j access restricted to parameterized, read-only query templates."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.driver = None
        if (
            self.settings.neo4j_enabled
            and GraphDatabase
            and self.settings.neo4j_password
        ):
            try:
                self.driver = GraphDatabase.driver(
                    self.settings.neo4j_uri,
                    auth=(self.settings.neo4j_user, self.settings.neo4j_password),
                )
            except Exception:
                logger.exception("Neo4j driver initialization failed")

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def health(self) -> bool:
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def sync_catalog(self, products: list[dict[str, Any]]) -> None:
        if not self.driver:
            return
        query = """
        UNWIND $products AS product
        MERGE (s:Series {code: product.series_code})
        SET s.name = product.series_name, s.manufacturer = product.manufacturer
        MERGE (m:MachineModel {code: product.code})
        SET m.name = product.name, m.source_url = product.source_url
        MERGE (m)-[:BELONGS_TO]->(s)
        """
        try:
            with self.driver.session(default_access_mode="WRITE") as session:
                session.run(query, products=products).consume()
        except Exception:
            logger.exception("Catalog graph synchronization failed")

    def sync_knowledge(
        self, alarms: list[dict[str, Any]], parts: list[dict[str, Any]], cases: list[dict[str, Any]]
    ) -> None:
        if not self.driver:
            return
        alarm_query = """
        UNWIND $items AS item
        MERGE (a:Alarm {code: item.code})
        SET a.title = item.title, a.severity = item.severity,
            a.data_classification = item.data_classification
        WITH a, item
        UNWIND item.applies_to AS model_code
        MATCH (m:MachineModel {code: model_code})
        MERGE (m)-[:HAS_ALARM]->(a)
        """
        part_query = """
        UNWIND $items AS item
        MERGE (p:Part {part_no: item.part_no})
        SET p.name = item.name, p.data_classification = item.data_classification
        WITH p, item
        UNWIND item.applies_to AS model_code
        MATCH (m:MachineModel {code: model_code})
        MERGE (p)-[:APPLIES_TO]->(m)
        """
        case_query = """
        UNWIND $items AS item
        MERGE (c:MaintenanceCase {case_no: item.case_no})
        SET c.title = item.title, c.data_classification = item.data_classification
        WITH c, item
        MATCH (m:MachineModel {code: item.model_code})
        MERGE (c)-[:OCCURRED_ON]->(m)
        WITH c, item
        OPTIONAL MATCH (a:Alarm {code: item.alarm_code})
        FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (c)-[:INVOLVES]->(a))
        """
        try:
            with self.driver.session(default_access_mode="WRITE") as session:
                session.run(alarm_query, items=alarms).consume()
                session.run(part_query, items=parts).consume()
                session.run(case_query, items=cases).consume()
        except Exception:
            logger.exception("Knowledge graph synchronization failed")

    def sync_fault_paths(
        self,
        subsystems: list[dict[str, Any]],
        fault_paths: list[dict[str, Any]],
    ) -> None:
        """Publish reviewed model/subsystem/fault links used by troubleshooting.

        Long-form instructions stay in PostgreSQL. Neo4j only stores the reviewed
        applicability and association edges needed to constrain retrieval.
        """
        if not self.driver:
            return
        subsystem_query = """
        UNWIND $items AS item
        MERGE (s:Subsystem {code: item.code})
        SET s.name = item.name,
            s.source_title = item.source_title,
            s.source_url = item.source_url,
            s.source_section = item.source_section,
            s.data_classification = item.data_classification
        WITH s, item
        UNWIND item.model_codes AS model_code
        MATCH (m:MachineModel {code: model_code})
        MERGE (m)-[r:HAS_SUBSYSTEM]->(s)
        SET r.source_title = item.source_title,
            r.source_url = item.source_url,
            r.source_section = item.source_section,
            r.data_classification = item.data_classification
        """
        alarm_subsystem_query = """
        UNWIND $items AS item
        MATCH (a:Alarm {code: item.alarm_code})
        MATCH (s:Subsystem {code: item.subsystem_code})
        MERGE (a)-[r:LOCATED_IN]->(s)
        SET r.source_title = item.source_title,
            r.source_url = item.source_url,
            r.source_section = item.source_section,
            r.data_classification = item.data_classification
        """
        alarm_part_query = """
        UNWIND $items AS item
        MATCH (a:Alarm {code: item.alarm_code})
        UNWIND item.part_nos AS part_no
        MATCH (p:Part {part_no: part_no})
        MERGE (a)-[r:MAY_REQUIRE_VERIFICATION_OF]->(p)
        SET r.source_title = item.source_title,
            r.source_url = item.source_url,
            r.source_section = item.source_section,
            r.data_classification = item.data_classification
        """
        try:
            with self.driver.session(default_access_mode="WRITE") as session:
                session.run(subsystem_query, items=subsystems).consume()
                session.run(alarm_subsystem_query, items=fault_paths).consume()
                session.run(alarm_part_query, items=fault_paths).consume()
        except Exception:
            logger.exception("Troubleshooting graph synchronization failed")

    def fault_context(self, model_code: str, alarm_code: str) -> dict[str, Any] | None:
        """Return a reviewed explanation path for one model/alarm pair.

        The application still reads actionable text from PostgreSQL. This query
        supplies graph associations and provenance, never free-form Cypher.
        """
        if not self.driver:
            return None
        query = """
        MATCH (m:MachineModel {code: $model_code})-[:HAS_ALARM]->(a:Alarm {code: $alarm_code})
        MATCH (m)-[ms:HAS_SUBSYSTEM]->(s:Subsystem)<-[as:LOCATED_IN]-(a)
        OPTIONAL MATCH (a)-[ap:MAY_REQUIRE_VERIFICATION_OF]->(p:Part)
        OPTIONAL MATCH (c:MaintenanceCase)-[:INVOLVES]->(a)
        RETURN m.code AS model_code,
               a.code AS alarm_code,
               a.title AS alarm_title,
               collect(DISTINCT CASE WHEN s IS NULL THEN null ELSE {
                   code: s.code,
                   name: s.name,
                   source_title: ms.source_title,
                   source_url: ms.source_url,
                   source_section: ms.source_section,
                   data_classification: ms.data_classification,
                   alarm_source_title: as.source_title,
                   alarm_source_url: as.source_url,
                   alarm_source_section: as.source_section,
                   alarm_data_classification: as.data_classification
               } END) AS subsystems,
               collect(DISTINCT CASE WHEN p IS NULL THEN null ELSE {
                   part_no: p.part_no,
                   name: p.name,
                   source_title: ap.source_title,
                   source_url: ap.source_url,
                   source_section: ap.source_section,
                   data_classification: ap.data_classification
               } END) AS parts,
               collect(DISTINCT CASE WHEN c IS NULL THEN null ELSE {
                   case_no: c.case_no,
                   title: c.title,
                   data_classification: c.data_classification
               } END) AS cases
        LIMIT 1
        """
        try:
            with self.driver.session(default_access_mode="READ") as session:
                record = session.run(
                    query,
                    model_code=model_code,
                    alarm_code=alarm_code,
                ).single()
                if not record:
                    return None
                data = record.data()
                data["subsystems"] = [item for item in data.get("subsystems", []) if item]
                data["parts"] = [item for item in data.get("parts", []) if item]
                data["cases"] = [item for item in data.get("cases", []) if item]
                return data
        except Exception:
            logger.exception("Troubleshooting graph read failed")
            return None

    def coverage_summary(self) -> dict[str, int | bool]:
        """Return live coverage counts for the reviewed troubleshooting graph."""
        empty = {
            "available": False,
            "subsystems": 0,
            "models": 0,
            "alarms": 0,
            "parts": 0,
            "cases": 0,
        }
        if not self.driver:
            return empty
        query = """
        OPTIONAL MATCH (s:Subsystem)
        OPTIONAL MATCH (m:MachineModel)-[:HAS_SUBSYSTEM]->(s)
        OPTIONAL MATCH (a:Alarm)-[:LOCATED_IN]->(s)
        OPTIONAL MATCH (a)-[:MAY_REQUIRE_VERIFICATION_OF]->(p:Part)
        OPTIONAL MATCH (c:MaintenanceCase)-[:INVOLVES]->(a)
        RETURN count(DISTINCT s) AS subsystems,
               count(DISTINCT m) AS models,
               count(DISTINCT a) AS alarms,
               count(DISTINCT p) AS parts,
               count(DISTINCT c) AS cases
        """
        try:
            with self.driver.session(default_access_mode="READ") as session:
                record = session.run(query).single()
                if not record:
                    return empty
                data = record.data()
                return {
                    "available": True,
                    "subsystems": int(data.get("subsystems") or 0),
                    "models": int(data.get("models") or 0),
                    "alarms": int(data.get("alarms") or 0),
                    "parts": int(data.get("parts") or 0),
                    "cases": int(data.get("cases") or 0),
                }
        except Exception:
            logger.exception("Graph coverage query failed")
            return empty

    def related(self, model_code: str, alarm_code: str | None = None) -> list[dict]:
        if not self.driver:
            return []
        query = """
        MATCH (m:MachineModel {code: $model_code})
        OPTIONAL MATCH (m)-[:HAS_ALARM]->(a:Alarm)
        WHERE $alarm_code IS NULL OR a.code = $alarm_code
        OPTIONAL MATCH (a)-[:REFERENCES_PART]->(p:Part)
        RETURN m.code AS model, a.code AS alarm, a.title AS alarm_title,
               collect(DISTINCT {part_no: p.part_no, name: p.name})[0..10] AS parts
        LIMIT 20
        """
        try:
            with self.driver.session(default_access_mode="READ") as session:
                return [record.data() for record in session.run(query, model_code=model_code, alarm_code=alarm_code)]
        except Exception:
            logger.exception("Graph read failed")
            return []


graph_service = GraphService()
