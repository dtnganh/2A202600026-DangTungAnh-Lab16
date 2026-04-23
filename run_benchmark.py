from __future__ import annotations
import json
from pathlib import Path
import typer
from rich import print
from rich.progress import track
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent, LatsAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl
app = typer.Typer(add_completion=False)

@app.command()
def main(dataset: str = "data/hotpot_mini.json", out_dir: str = "outputs/sample_run", reflexion_attempts: int = 3) -> None:
    examples = load_dataset(dataset)
    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)
    lats = LatsAgent(max_attempts=reflexion_attempts, branch_factor=3)
    
    react_records = [react.run(example) for example in track(examples, description="[cyan]Running ReAct Agent...")]
    reflexion_records = [reflexion.run(example) for example in track(examples, description="[magenta]Running Reflexion Agent...")]
    lats_records = [lats.run(example) for example in track(examples, description="[green]Running LATS Agent...")]
    
    all_records = react_records + reflexion_records + lats_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    save_jsonl(out_path / "lats_runs.jsonl", lats_records)
    report = build_report(all_records, dataset_name=Path(dataset).name, mode="mock")
    json_path, md_path = save_report(report, out_path)
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(json.dumps(report.summary, indent=2))

if __name__ == "__main__":
    app()
