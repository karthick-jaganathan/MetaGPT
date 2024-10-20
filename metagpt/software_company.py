#!/usr/bin/env python
# -*- coding: utf-8 -*-
# software_company.py

import asyncio
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich import box
import re
import agentops
import typer
from utils.metrics_logger import MetricsLogger
from utils.metrics_report import MetricsReportGenerator
from metagpt.const import CONFIG_ROOT
from metagpt.utils.project_repo import ProjectRepo
from metagpt.dynamic_sop import DynamicSOP
from metagpt.utils.common import CodeParser  # Imported from write_prd.py
from metagpt.actions.write_prd import CONTEXT_TEMPLATE  # Importing CONTEXT_TEMPLATE from write_prd
from metagpt.utils.git_repository import GitRepository  # Import the GitRepository class


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


def display_agents_overview(idea: str, domain: str, agents: list[dict]):
    # Initialize the console
    console = Console()

    # Create a table with a title
    table = Table(title="Agents Overview", box=box.SIMPLE)

    # Define column headers with styles
    table.add_column("Task ID", style="cyan bold", justify="center")
    table.add_column("Description", style="magenta", justify="left")
    table.add_column("Agent", style="green", justify="left")
    table.add_column("Skill", style="yellow", justify="left")
    table.add_column("Actions", style="white", justify="left")
    table.add_column("Watch", style="blue", justify="left")
    table.add_column("Trigger", style="bright_white", justify="left")

    # Add rows to the table
    for index, item in enumerate(agents):
        table.add_row(
            str(item['subtask_number']),
            str(item['subtask_description']),
            str(item['agent']),
            str(item['skill']),
            str(item['actions']),
            str(item['watch_items']),
            str(item['trigger']),
        )
        # Insert a blank row for height
        table.add_row("", "", "", "", "", "", "")  # Empty row for gap

    # Customize the table borders
    table.border_style = "bright_blue"  # Set the border color

    # Create the content for the panel
    overview_content = f"""\
    [bright_cyan bold]Task/Idea :[/bright_cyan bold] [magenta]{idea}[/magenta]
    [bright_cyan bold]Domain    :[/bright_cyan bold] [yellow]{domain}[/yellow]
    """

    # Create a single panel combining both overview and table
    combined_panel = Panel(
        Group(overview_content, table),
        title="Dynamic SOP Overview",
        border_style="bright_blue"
    )

    console.print()
    # Print the combined panel
    console.print(combined_panel)


def generate_repo(
    idea,
    investment=3.0,
    n_round=5,
    code_review=True,
    run_tests=False,
    implement=True,
    project_name="",  # Default is still empty
    inc=False,
    project_path="",
    reqa_file="",
    max_auto_summarize_code=0,
    recover_path=None,
    collect_feedback=False,
    dynamic_sop=False,
) -> ProjectRepo:
    """Run the startup logic. Can be called from CLI or other Python scripts."""
    from metagpt.config2 import config
    from metagpt.context import Context  # Import the Context class
    from metagpt.roles import (
        Architect,
        Engineer,
        ProductManager,
        ProjectManager,
        QaEngineer,
    )
    from metagpt.team import Team
    from metagpt.utils.feedback_collector import FEEDBACK_REGISTRY

    # Generate consistent project_name from the idea for both dynamic and non-dynamic sop
    project_name="hello_world_script"

    print(f"Project Name: {project_name}")

    # Fetch the current Git repository directory using GitRepository
    git_repo = GitRepository(local_path=config.workspace.path)  # Initialize the repository
    repo_dir = git_repo.workdir if git_repo.is_valid else str(config.workspace.path)

    # Merge the current repo directory with the project name to create the workspace directory
    workspace_dir = os.path.join(repo_dir, project_name)

    # Ensure workspace directory creation (if it doesn't exist)
    #os.makedirs(workspace_dir, exist_ok=True)


    print(f"Workspace Directory: {workspace_dir}")

    # Initialize context here
    ctx = Context(config=config)

    # Initialize the metrics logger using the same workspace directory for both flows
    metrics_logger = MetricsLogger(workspace_dir)
    metrics_logger.start_timer()  # Start logging the execution time

    if not recover_path:
        if not dynamic_sop:
            company = Team(context=ctx)
            company.hire(
                [
                    ProductManager(),
                    Architect(),
                    ProjectManager(),
                ]
            )

            if implement or code_review:
                company.hire([Engineer(n_borg=5, use_code_review=code_review)])

            if run_tests:
                company.hire([QaEngineer()])
        else:
            dyn_sop = DynamicSOP(Context(config=config))
            asyncio.run(dyn_sop.generate_dynamic_sop(idea))
            display_agents_overview(idea, domain=dyn_sop.domain, agents=dyn_sop.req_agents_dedup.values())
            company = Team(context=ctx)
            company.hire(dyn_sop.agent_instances)
    else:
        stg_path = Path(recover_path)
        if not stg_path.exists() or not str(stg_path).endswith("team"):
            raise FileNotFoundError(f"{recover_path} not exists or not endswith `team`")

        company = Team.deserialize(stg_path=stg_path, context=ctx)
        idea = company.idea

    # Log token usage for idea processing
    metrics_logger.log_token_usage(idea)

    company.invest(investment)

    try:
        # Run the project simulation before generating reports
        company.run_project(idea)
        asyncio.run(company.run(n_round=n_round))

        # Now that code has been generated, calculate code statistics and complexity
        metrics_logger.log_code_statistics()  # <-- After file generation
        metrics_logger.log_code_complexity()  # <-- After file generation

        # Log executability after execution
        metrics_logger.log_executability(success=True)
    except Exception as e:
        # If there's an error, log executability as failure
        metrics_logger.log_executability(success=False)
        metrics_logger.log_error_rate(1)  # Log error rate
        raise e
    finally:
        # Stop timer and log the rest of the metrics
        metrics_logger.stop_timer()
        metrics_logger.log_memory_usage()

        # Export metrics
        metrics_logger.export_metrics(output_format="json")

        # Generate final report
        report_generator = MetricsReportGenerator(workspace_dir, report_format="json")
        report_generator.generate_report()

    if config.agentops_api_key != "":
        agentops.end_session("Success")

    return ctx.repo


@app.command("", help="Start a new project.")
def startup(
    idea: str = typer.Argument(None, help="Your innovative idea, such as 'Create a 2048 game.'"),
    investment: float = typer.Option(default=3.0, help="Dollar amount to invest in the AI company."),
    n_round: int = typer.Option(default=5, help="Number of rounds for the simulation."),
    code_review: bool = typer.Option(default=True, help="Whether to use code review."),
    run_tests: bool = typer.Option(default=False, help="Whether to enable QA for adding & running tests."),
    implement: bool = typer.Option(default=True, help="Enable or disable code implementation."),
    project_name: str = typer.Option(default="", help="Unique project name, such as 'game_2048'."),
    inc: bool = typer.Option(default=False, help="Incremental mode. Use it to coop with existing repo."),
    project_path: str = typer.Option(
        default="",
        help="Specify the directory path of the old version project to fulfill the incremental requirements.",
    ),
    reqa_file: str = typer.Option(
        default="", help="Specify the source file name for rewriting the quality assurance code."
    ),
    max_auto_summarize_code: int = typer.Option(
        default=0,
        help="The maximum number of times the 'SummarizeCode' action is automatically invoked, with -1 indicating "
        "unlimited. This parameter is used for debugging the workflow.",
    ),
    recover_path: str = typer.Option(default=None, help="Recover the project from existing serialized storage"),
    init_config: bool = typer.Option(default=False, help="Initialize the configuration file for MetaGPT."),
    collect_feedback: bool = typer.Option(default=False, help="Collect user feedbacks to adjust prompts in real-time."),
    dynamic_sop: bool = typer.Option(default=False, help="Generate SOPS dynamically."),
):
    """Run a startup. Be a boss."""
    if init_config:
        copy_config_to()
        return

    if idea is None:
        typer.echo("Missing argument 'IDEA'. Run 'metagpt --help' for more information.")
        raise typer.Exit()

    return generate_repo(
        idea,
        investment,
        n_round,
        code_review,
        run_tests,
        implement,
        project_name,  # <- This argument is passed to generate_repo()
        inc,
        project_path,
        reqa_file,
        max_auto_summarize_code,
        recover_path,
        collect_feedback,
        dynamic_sop,
    )


DEFAULT_CONFIG = """# Full Example: https://github.com/geekan/MetaGPT/blob/main/config/config2.example.yaml
# Reflected Code: https://github.com/geekan/MetaGPT/blob/main/metagpt/config2.py
# Config Docs: https://docs.deepwisdom.ai/main/en/guide/get_started/configuration.html
llm:
  api_type: "openai"  # or azure / ollama / groq etc.
  model: "gpt-4-turbo"  # or gpt-3.5-turbo
  base_url: "https://api.openai.com/v1"  # or forward url / other llm url
  api_key: "YOUR_API_KEY"
"""


def copy_config_to():
    """Initialize the configuration file for MetaGPT."""
    target_path = CONFIG_ROOT / "config2.yaml"


    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        backup_path = target_path.with_suffix(".bak")
        target_path.rename(backup_path)
        print(f"Existing configuration file backed up at {backup_path}")


    target_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    print(f"Configuration file initialized at {target_path}")


if __name__ == "__main__":
    app()
