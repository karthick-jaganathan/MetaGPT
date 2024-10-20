import os
import json
import csv
from rich.console import Console
from rich.table import Table
from rich import box  # Ensure box styles are imported

class MetricsReportGenerator:
    def __init__(self, workspace_dir, report_format="json", dynamic_sop=False):
        self.workspace_dir = workspace_dir
        self.report_format = report_format
        self.metrics_file = os.path.join(self.workspace_dir, f'execution_metrics.{report_format}')
        self.dynamic_sop = dynamic_sop  # Initialize the dynamic_sop flag based on software_company.py

    def generate_report(self):
        if os.path.exists(self.metrics_file):
            if self.report_format == "json":
                with open(self.metrics_file, 'r') as file:
                    metrics = json.load(file)
                    self._print_json_report(metrics)
            elif self.report_format == "csv":
                with open(self.metrics_file, 'r') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        print(f'{row[0]}: {row[1]}')
        else:
            print("No metrics file found. Please run the pipeline first.")
    
    def _print_json_report(self, metrics):
        console = Console()

        column_title = "Dynamic SOP" if self.dynamic_sop else "Native MetaGPT"

        table = Table(title="Statistical Analysis on SoftwareDev", box=box.SIMPLE)

        table.add_column("Statistical Index", style="cyan bold", justify="left")
        table.add_column(column_title, style="magenta", justify="center")

        table.add_row("(A) Executability", str(metrics.get('executability', 'N/A')))
        table.add_row("(B) Cost#1: Running Times (s)", str(metrics.get('running_time', 'N/A')))
        table.add_row("(B) Cost#2: Token Usage", str(metrics.get('token_usage', 'N/A')))
        table.add_row("(C) Code Statistic#1: Code Files", str(metrics.get('code_files', 'N/A')))
        table.add_row("(C) Code Statistic#2: Avg Lines of Code per File", str(metrics.get('avg_lines_per_file', 'N/A')))
        table.add_row("(C) Code Statistic#3: Total Code Lines", str(metrics.get('total_code_lines', 'N/A')))
        table.add_row("(D) Productivity", str(metrics.get('productivity', 'N/A')))
        table.add_row("(E) Human Revision Cost", str(metrics.get('human_revision_cost', 'N/A')))

        console.print(table)
