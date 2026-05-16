"""Build Agent-ready context from recalled long-term memory."""

from typing import Dict, List, Optional

from .memory_retriever import MemoryRetriever


class ContextInjector:
    """Turn recalled memory rows into compact context text for an Agent."""

    def __init__(self, retriever: Optional[MemoryRetriever] = None):
        self.retriever = retriever or MemoryRetriever()

    def build_agent_context(self, question: str, top_k: int = 5) -> Dict[str, object]:
        """Recall memories and format them as traceable context."""
        memories = self.retriever.recall_memory(question, top_k=top_k)
        lines: List[str] = []

        for index, memory in enumerate(memories, start=1):
            lines.append(
                "\n".join(
                    [
                        f"[memory {index}]",
                        f"summary: {memory.get('summary') or ''}",
                        f"source: {memory.get('source') or ''}",
                        f"time: {memory.get('publish_time') or ''}",
                        f"importance_score: {memory.get('importance_score')}",
                        f"url: {memory.get('url') or ''}",
                        f"final_score: {round(float(memory.get('final_score') or 0.0), 4)}",
                    ]
                )
            )

        return {
            "question": question,
            "context": "\n\n".join(lines),
            "memories": memories,
        }


def build_agent_context(question: str, top_k: int = 5) -> Dict[str, object]:
    """Convenience function required by the phase 3 interface."""
    return ContextInjector().build_agent_context(question, top_k=top_k)
