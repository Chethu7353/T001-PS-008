"""Entry point for Mutual Fund Order Processing System."""

from pathlib import Path
from src.command_processor import CommandProcessor


def main():
    """Execute the command processing engine on official dataset and generate CSV outputs."""
    print("Mutual Fund Order Processing System")
    workspace_dir = Path(__file__).resolve().parent.parent
    sample_dir = workspace_dir / "data" / "sample_pack"

    processor = CommandProcessor(data_dir=sample_dir)
    processor.process_file()
    conf_file, sip_file, folio_file = processor.write_csv_outputs(output_dir=workspace_dir)

    print(f"Processed {processor.commands_processed} commands: "
          f"{processor.commands_accepted} accepted, {processor.commands_rejected} rejected.")
    print(f"Generated {conf_file.name} ({len(processor.confirmations)} rows)")
    print(f"Generated {sip_file.name} ({len(processor.sip_statuses)} rows)")
    print(f"Generated {folio_file.name} ({len(processor.folio_statements)} rows)")


if __name__ == "__main__":
    main()
