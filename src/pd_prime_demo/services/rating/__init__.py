"""Rating engine services package.

This package provides comprehensive rating calculations with:
- Premium calculation algorithms
- Discount stacking logic
- Surcharge calculations for high-risk factors
- AI-enhanced risk scoring
- Performance optimizations for <50ms calculations
- Advanced caching strategies
- State-specific rating rules
- Business rule validation
"""

from .business_rules import BusinessRuleViolation, RatingBusinessRules
from .cache_strategy import RatingCacheManager, RatingCacheStrategy
from .calculators import (
    AdvancedPerformanceCalculator,
    AIRiskScorer,
    CreditBasedInsuranceScorer,
    DiscountCalculator,
    ExternalDataIntegrator,
    PremiumCalculator,
    RegulatoryComplianceCalculator,
    StatisticalRatingModels,
)
from .performance import RatingPerformanceOptimizer
from .performance_optimizer import RatingPerformanceOptimizer as PerformanceOptimizer
from .rate_tables import RateTableService
from .rating_engine import RatingEngine
from .state_rules import (
    CaliforniaRules,
    FloridaRules,
    MichiganRules,
    NewYorkRules,
    PennsylvaniaRules,
    StateRatingRules,
    TexasRules,
    get_state_rules,
    validate_coverage_limits,
)
from .surcharge_calculator import SurchargeCalculator
from .territory_management import TerritoryDefinition, TerritoryManager

__all__ = [
    # Main Engine
    "RatingEngine",
    # Core calculators
    "PremiumCalculator",
    "DiscountCalculator",
    "SurchargeCalculator",
    "AIRiskScorer",
    "CreditBasedInsuranceScorer",
    "ExternalDataIntegrator",
    "StatisticalRatingModels",
    "AdvancedPerformanceCalculator",
    "RegulatoryComplianceCalculator",
    # Business Rules
    "RatingBusinessRules",
    "BusinessRuleViolation",
    # Territory Management
    "TerritoryManager",
    "TerritoryDefinition",
    # Performance optimization
    "RatingPerformanceOptimizer",
    "PerformanceOptimizer",
    # Caching
    "RatingCacheStrategy",
    "RatingCacheManager",
    # Services
    "RateTableService",
    # State rules
    "StateRatingRules",
    "CaliforniaRules",
    "TexasRules",
    "NewYorkRules",
    "FloridaRules",
    "MichiganRules",
    "PennsylvaniaRules",
    "get_state_rules",
    "validate_coverage_limits",
]
