"""
Wanda — an AI Data Engineer for Microsoft Fabric.

Investigates failed Fabric pipelines (and audits them pre-run) and produces
evidence-backed root-cause reports, by driving an LLM through an agentic
tool-use loop over the Fabric REST API and SQL endpoint.

    from wanda import Wanda
    report = Wanda(anthropic_api_key="sk-ant-...").investigate("MyPipeline")
    report.display()
"""
from .core import Wanda, WandaReport

__all__ = ["Wanda", "WandaReport"]

try:
    from importlib.metadata import version
    __version__ = version("wanda-fabric")
except Exception:  # running from a source tree that isn't installed
    __version__ = "0.1.1"
