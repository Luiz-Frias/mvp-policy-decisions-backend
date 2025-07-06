"""Rating engine services package.

This package provides comprehensive rating calculations with:
- Premium calculation algorithms
- Discount stacking logic
- AI-enhanced risk scoring
- Performance optimizations for <50ms calculations
- Advanced caching strategies
- State-specific rating rules
"""

from .cache_strategy import RatingCacheManager, RatingCacheStrategy
from .calculators import (
    AIRiskScorer,
    CreditBasedInsuranceScorer,
    DiscountCalculator,
    ExternalDataIntegrator,
    PremiumCalculator,
)
from .performance import RatingPerformanceOptimizer
from .state_rules import (
    CaliforniaRules,
    FloridaRules,
    NewYorkRules,
    StateRatingRules,
    TexasRules,
    get_state_rules,
    validate_coverage_limits,
)

__all__ = [
    # Core calculators
    "PremiumCalculator",
    "DiscountCalculator",
    "AIRiskScorer",
    "CreditBasedInsuranceScorer",
    "ExternalDataIntegrator",
    # Performance optimization
    "RatingPerformanceOptimizer",
    # Caching
    "RatingCacheStrategy",
    "RatingCacheManager",
    # State rules
    "StateRatingRules",
    "CaliforniaRules",
    "TexasRules",
    "NewYorkRules",
    "FloridaRules",
    "get_state_rules",
    "validate_coverage_limits",
]
