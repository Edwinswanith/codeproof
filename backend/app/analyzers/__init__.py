"""Analyzer registry."""

from app.analyzers.base import Analyzer, AnalyzerContext, FindingMatch
from app.analyzers.security_analyzer import SecurityAnalyzer
from app.analyzers.privacy_analyzer import PrivacyAnalyzer
from app.analyzers.reliability_analyzer import ReliabilityAnalyzer
from app.analyzers.performance_analyzer import PerformanceAnalyzer
from app.analyzers.maintainability_analyzer import MaintainabilityAnalyzer
from app.analyzers.architecture_analyzer import ArchitectureAnalyzer

__all__ = [
    "Analyzer",
    "AnalyzerContext",
    "FindingMatch",
    "SecurityAnalyzer",
    "PrivacyAnalyzer",
    "ReliabilityAnalyzer",
    "PerformanceAnalyzer",
    "MaintainabilityAnalyzer",
    "ArchitectureAnalyzer",
]
