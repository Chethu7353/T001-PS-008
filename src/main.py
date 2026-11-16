"""Entry point for Mutual Fund Order Processing System.

Supports both interactive terminal application mode and batch processing.
"""

from pathlib import Path
import sys

from src.command_processor import CommandProcessor
from src.interactive import InteractiveApp


def run_batch():
    """Execute the command processing engine on official dataset and generate CSV outputs."""
    print("Mutual Fund Order Processing System - Batch Execution")
    workspace_dir = Path(__file__).resolve().parent.parent
    sample_dir = workspace_dir / "data" / "sample_pack"

    processor = CommandProcessor(data_dir=sample_dir)
    processor.process_file()
    conf_file, sip_file, folio_file = processor.write_csv_outputs(output_dir=workspace_dir)

    print(
        f"Processed {processor.commands_processed} commands: "
        f"{processor.commands_accepted} accepted, {processor.commands_rejected} rejected."
    )
    print(f"Generated {conf_file.name} ({len(processor.confirmations)} rows)")
    print(f"Generated {sip_file.name} ({len(processor.sip_statuses)} rows)")
    print(f"Generated {folio_file.name} ({len(processor.folio_statements)} rows)")


def main():
    """Main application launcher."""
    # If invoked with --batch, execute batch mode directly
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        run_batch()
        return

    # Default: launch interactive terminal application
    app = InteractiveApp()
    app.run()


if __name__ == "__main__":
    main()
