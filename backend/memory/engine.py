import os
from .base import BaseMemoryEngine, DB_PATH
from .voice_biometrics import VoiceBiometricsMixin
from .semantic_rag import SemanticRAGMixin
from .tasks_projects import TasksProjectsMixin
from .chat_sessions import ChatSessionsMixin
from .providers_tokens import ProvidersTokensMixin


class AnaraMemoryEngine(
    VoiceBiometricsMixin,
    SemanticRAGMixin,
    TasksProjectsMixin,
    ChatSessionsMixin,
    ProvidersTokensMixin,
    BaseMemoryEngine,
):
    """
    SQLite-backed JARVIS-style Cognitive Brain & Voice Biometrics Engine for Project Anara.
    Stores and recalls user profiles, personal preferences, voiceprints, notes, to-dos,
    and episodic conversation history with strict deduplication and zero-shot AI distillation.
    Modularized using Python Class Mixins for enterprise-grade separation of concerns.
    """
    pass


# Global singleton instance
memory_engine = AnaraMemoryEngine()
