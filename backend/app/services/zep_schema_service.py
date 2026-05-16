"""Enhanced Zep GraphRAG schema for long-term memory.

The original project already uses Zep for ontology-based graph construction and
simulation memory updates. This module only adds a reusable schema for active
ingestion memory, keeping the old graph builder untouched.
"""

from dataclasses import dataclass
from typing import Dict, List


ENTITY_TYPES = ["person", "organization", "event", "opinion", "evidence", "stance"]

RELATION_TYPES = [
    "supports",
    "opposes",
    "publishes",
    "mentions",
    "causes",
    "influences",
    "based_on",
    "expresses",
    "responds_to",
    "changes_stance",
]


@dataclass(frozen=True)
class GraphEntitySpec:
    """A simple entity schema description."""

    name: str
    class_name: str
    description: str


@dataclass(frozen=True)
class GraphRelationSpec:
    """A simple relation schema description."""

    name: str
    class_name: str
    description: str
    source_targets: List[Dict[str, str]]


class ZepSchemaService:
    """Define and optionally apply the enhanced Zep GraphRAG schema."""

    def entity_specs(self) -> List[GraphEntitySpec]:
        """Return enhanced entity definitions."""
        return [
            GraphEntitySpec("person", "Person", "A human actor, public figure, expert, or agent."),
            GraphEntitySpec("organization", "Organization", "A company, institution, agency, media, or group."),
            GraphEntitySpec("event", "Event", "An event, action, policy move, conflict, or market change."),
            GraphEntitySpec("opinion", "Opinion", "A stated claim, interpretation, forecast, or judgment."),
            GraphEntitySpec("evidence", "Evidence", "A quote, source sentence, data point, or supporting snippet."),
            GraphEntitySpec("stance", "Stance", "A support, opposition, neutral, or shifting position."),
        ]

    def relation_specs(self) -> List[GraphRelationSpec]:
        """Return enhanced relation definitions."""
        any_actor = [{"source": "Person", "target": "Opinion"}, {"source": "Organization", "target": "Opinion"}]
        return [
            GraphRelationSpec("supports", "Supports", "The source supports the target.", any_actor),
            GraphRelationSpec("opposes", "Opposes", "The source opposes the target.", any_actor),
            GraphRelationSpec("publishes", "Publishes", "The source publishes evidence or an opinion.", [
                {"source": "Organization", "target": "Evidence"},
                {"source": "Person", "target": "Opinion"},
            ]),
            GraphRelationSpec("mentions", "Mentions", "The source mentions the target.", [
                {"source": "Evidence", "target": "Person"},
                {"source": "Evidence", "target": "Organization"},
                {"source": "Evidence", "target": "Event"},
                {"source": "Opinion", "target": "Event"},
            ]),
            GraphRelationSpec("causes", "Causes", "The source event causes the target event.", [
                {"source": "Event", "target": "Event"},
            ]),
            GraphRelationSpec("influences", "Influences", "The source influences the target.", [
                {"source": "Event", "target": "Opinion"},
                {"source": "Organization", "target": "Event"},
                {"source": "Person", "target": "Opinion"},
            ]),
            GraphRelationSpec("based_on", "BasedOn", "The source opinion or stance is based on evidence.", [
                {"source": "Opinion", "target": "Evidence"},
                {"source": "Stance", "target": "Evidence"},
            ]),
            GraphRelationSpec("expresses", "Expresses", "The source actor expresses an opinion or stance.", [
                {"source": "Person", "target": "Opinion"},
                {"source": "Organization", "target": "Opinion"},
                {"source": "Person", "target": "Stance"},
                {"source": "Organization", "target": "Stance"},
            ]),
            GraphRelationSpec("responds_to", "RespondsTo", "The source responds to an event or opinion.", [
                {"source": "Opinion", "target": "Event"},
                {"source": "Stance", "target": "Opinion"},
            ]),
            GraphRelationSpec("changes_stance", "ChangesStance", "The source actor changes stance.", [
                {"source": "Person", "target": "Stance"},
                {"source": "Organization", "target": "Stance"},
            ]),
        ]

    def ontology_dict(self) -> Dict[str, List[Dict]]:
        """Return a documentation-friendly ontology dictionary."""
        return {
            "entity_types": [
                {"name": spec.name, "class_name": spec.class_name, "description": spec.description}
                for spec in self.entity_specs()
            ],
            "relation_types": [
                {
                    "name": spec.name,
                    "class_name": spec.class_name,
                    "description": spec.description,
                    "source_targets": spec.source_targets,
                }
                for spec in self.relation_specs()
            ],
        }

    def build_zep_models(self):
        """Build dynamic models for Zep's ontology API."""
        from pydantic import Field
        from zep_cloud import EntityEdgeSourceTarget
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel

        entity_models = {}
        for spec in self.entity_specs():
            attrs = {
                "__doc__": spec.description,
                "description": Field(description="Short description of the entity.", default=None),
                "source_url": Field(description="Source URL where this entity was observed.", default=None),
                "__annotations__": {
                    "description": EntityText,
                    "source_url": EntityText,
                },
            }
            entity_models[spec.class_name] = type(spec.class_name, (EntityModel,), attrs)

        edge_models = {}
        for spec in self.relation_specs():
            attrs = {
                "__doc__": spec.description,
                "source_url": Field(description="Source URL for this relationship.", default=None),
                "publish_time": Field(description="Publish time for this relationship.", default=None),
                "mysql_id": Field(description="MySQL memory_item id.", default=None),
                "evidence_text": Field(description="Evidence text supporting this relationship.", default=None),
                "__annotations__": {
                    "source_url": str,
                    "publish_time": str,
                    "mysql_id": str,
                    "evidence_text": str,
                },
            }
            source_targets = [
                EntityEdgeSourceTarget(source=item["source"], target=item["target"])
                for item in spec.source_targets
            ]
            # Zep's ontology API requires edge type names such as
            # "RESPONDS_TO" instead of the lower-case labels used internally.
            zep_relation_name = spec.name.upper()
            edge_models[zep_relation_name] = (type(spec.class_name, (EdgeModel,), attrs), source_targets)

        return entity_models, edge_models

    def apply_to_graph(self, client, graph_id: str) -> None:
        """Apply the enhanced schema to a Zep standalone graph."""
        entity_models, edge_models = self.build_zep_models()
        client.graph.set_ontology(
            graph_ids=[graph_id],
            entities=entity_models,
            edges=edge_models,
        )
