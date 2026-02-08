"""Report generation for SENTINEL Arena."""
from .generator import generate_report
from .charts import generate_asr_chart

__all__ = ["generate_report", "generate_asr_chart"]
