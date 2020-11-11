import logging, logging.config
import pkg_resources

import click

from . import core
from . import config as CFG

log = logging.getLogger(__name__)


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    version = pkg_resources.require("jackup")[0].version
    print(f"jackup v{version}")
    ctx.exit()


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-V", "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True,)
@click.option("-v", "--verbose", count=True, type=click.IntRange(0, 2))
def main(verbose):
    verbosity = {
        0: {"root": {"handlers": ["default"], "level": "INFO"}},
        1: {"root": {"handlers": ["extended"], "level": "INFO"}},
        2: {"root": {"handlers": ["extended"], "level": "DEBUG"}},
    }

    CFG.LOG_CONFIG.update(verbosity.get(verbose))
    logging.config.dictConfig(CFG.LOG_CONFIG)

    # load config from conf file and environment
    CFG.CONFIG.update(CFG.load())
    CFG.CONFIG.update({"verbosity": verbose})

    log.debug(f"{CFG.CONFIG=}")


@main.command()
@click.argument("profiles", nargs=-1)
def list(profiles):
    log.debug(f"{profiles=}")
    core.list(profiles)


@main.command()
@click.argument("profiles", nargs=-1)
def sync(profiles):
    log.debug(f"{profiles=}")
    core.sync(profiles)


if __name__ == "__main__":
    main()
