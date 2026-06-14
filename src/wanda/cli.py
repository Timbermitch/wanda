"""
Wanda command-line interface.

    wanda LoadSalesPipeline           # investigate a failed pipeline
    wanda LoadSalesPipeline --scan    # pre-run audit before it runs

(Also runnable as `python -m wanda ...`.)
"""
import sys

from .config import ConfigError
from .core import Wanda
from .log_setup import get_logger

logger = get_logger("cli")


def main() -> None:
    # Windows consoles default to cp1252, which can't encode emoji a model may
    # put in a report. Force UTF-8 so printing never crashes the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    # Parse args: support --scan flag
    args = sys.argv[1:]
    scan_mode = "--scan" in args
    args = [a for a in args if a != "--scan"]
    pipeline_name = args[0] if args else "LoadSalesPipeline"

    try:
        wanda = Wanda()
        report = wanda.scan(pipeline_name) if scan_mode else wanda.investigate(pipeline_name)
    except ConfigError as e:
        # Missing/invalid configuration — the message says exactly what to set.
        logger.error("Configuration problem: %s", e)
        sys.exit(2)
    except KeyboardInterrupt:
        logger.error("Interrupted.")
        sys.exit(130)
    except Exception as e:  # a tester must never be greeted by a raw traceback
        # The LLM and Fabric layers already raise plain-English messages
        # (invalid/unfunded API key, wrong Service Principal secret, 401/403/404).
        # Surface that and the usual culprits — never a stack trace.
        logger.error("Wanda could not complete the run: %s", e)
        logger.error(
            "Most first-run failures are one of: an invalid or unfunded LLM API key, "
            "a wrong Fabric Service Principal secret, or a pipeline name that doesn't "
            "exist in this workspace. Re-check your .env values and the pipeline name. "
            "See docs/GETTING_STARTED.md for the full setup."
        )
        sys.exit(1)

    # Save the HTML artifact first — a console hiccup must never lose the report.
    report_path = report.save()

    print("\n========== WANDA REPORT ==========")
    print(report.content)
    print("===================================\n")

    logger.info("Report saved: %s", report_path)
    logger.info("Open in browser: %s", report_path.resolve().as_uri())


if __name__ == "__main__":
    main()
