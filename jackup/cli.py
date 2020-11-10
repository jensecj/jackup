import logging, logging.config

import click

from . import core
from . import config as CFG

log = logging.getLogger(__name__)


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    version = open("__version__.py", "r").read().strip()
    print(f"jackup v{version}")
    ctx.exit()


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-V", "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True,)
@click.option("-v", "--verbose", help="", count=True)
def cli(verbose):
    verbosity = {
        0: {"root": {"handlers": ["default"], "level": "INFO"}},
        1: {"root": {"handlers": ["extended"], "level": "INFO"}},
        2: {"root": {"handlers": ["extended"], "level": "DEBUG"}},
    }
    CFG.LOG_CONFIG.update(verbosity.get(verbose))
    logging.config.dictConfig(CFG.LOG_CONFIG)
    CFG.update({"verbosity": verbose})

    log.debug(f"{CFG.CONFIG=}")


@cli.command()
@click.argument("profiles", nargs=-1)
def list(profiles):
    log.debug(f"{profiles=}")
    core.list(CFG.CONFIG, profiles)


@cli.command()
@click.argument("profiles", nargs=-1)
def sync(profiles):
    log.debug(f"{profiles=}")
    core.sync(CFG.CONFIG, profiles)


if __name__ == "__main__":
    cli()
