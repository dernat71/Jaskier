"""
This is the entry point for the Jaskier command-line interface (CLI) application.
It can be used as a handy facility for running the task from a command line.
"""
from dateutil import parser as date_parser
import logging
from pathlib import Path
import click
from .__init__ import __version__

from .financial import run_date_to_date_performances_analysis
from .utils import print_figlet, Context


LOGGING_LEVELS = {
    0: logging.NOTSET,
    1: logging.ERROR,
    2: logging.WARN,
    3: logging.INFO,
    4: logging.DEBUG,
}  #: a mapping of `verbose` option counts to logging levels

# Generate a logger
logger = logging.getLogger(__name__)


# pass_info is a decorator for functions that pass 'Info' objects.
#: pylint: disable=invalid-name
pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@pass_context
def cli(ctx: Context, verbose: int):
    """Run jaskier."""
    # Use the verbosity count to determine the logging level...
    if verbose > 0:
        logging.basicConfig(
            level=LOGGING_LEVELS[verbose]
            if verbose in LOGGING_LEVELS
            else logging.DEBUG
        )
        click.echo(
            click.style(
                f"Verbose logging is enabled. "
                f"(LEVEL={logging.getLogger().getEffectiveLevel()})",
                fg="yellow",
            )
        )
    ctx.verbose = verbose


@cli.command()
@click.option(
    "--positions-file",
    "-p",
    required=True,
    help="Path to files tracking positions.",
    type=click.Path(exists=True),
)
@click.option(
    "--start", "-s", help="Start date for analysis (format '1994/08/26')", type=str
)
@click.option(
    "--end", "-e", help="End date for analysis (format '1994/08/26')", type=str
)
@click.option("--benchmark", "-b", default="SPY", help="Benchmark for comparison.")
@pass_context
def run_performances_analysis(
    ctx: Context, positions_file: str, start: str, end: str, benchmark: str
) -> None:
    """
    Run a performance analysis of the portfolio defined by the positions_file CSV file between
    the start and end date against the benchmark symbol given.
    """
    if start is not None:
        start = date_parser.parse(start)
    
    if end is not None:
        end = date_parser.parse(end)

    performances_analysis = run_date_to_date_performances_analysis(ctx=ctx,
                                                                   positions_tracking_file=Path(positions_file),
                                                                   start_analysis_at=start,
                                                                   end_analysis_at=end,
                                                                   benchmark=benchmark)
    
    print(performances_analysis.info())



@cli.command()
@pass_context
def version(ctx: Context):
    """Get the library version."""
    print_figlet()
    click.echo(click.style(f"{__version__}", bold=True))
