"""Run all data processing scripts in order."""
import sys
import subprocess
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent
project_root = scripts_dir.parent

print("=" * 60)
print("Building All Data Files")
print("=" * 60)
print()

# Run scripts in order
scripts = [
    "ingest_csv_to_parquet.py",
    "build_tag_month_stats.py",
    "build_tag_summary.py"
]

for script in scripts:
    script_path = scripts_dir / script
    print(f"\n{'=' * 60}")
    print(f"Running {script}...")
    print(f"{'=' * 60}\n")
    
    # Run script as subprocess
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(project_root),
        check=False
    )
    
    if result.returncode != 0:
        print(f"\nERROR: {script} failed with exit code {result.returncode}")
        sys.exit(1)

print("\n" + "=" * 60)
print("All data processing complete!")
print("=" * 60)

