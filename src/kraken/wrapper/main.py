from __future__ import annotations

import argparse
import builtins
import logging
import os
import sys
import time
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from . import __version__
from .lockfile import calculate_lockfile

if TYPE_CHECKING:
    from kraken.util.requirements import RequirementSpec

    from kraken.wrapper.buildenv import BuildEnvManager, BuildEnvType
    from kraken.wrapper.lockfile import Lockfile

BUILDENV_PATH = Path("build/.kraken/venv")
BUILDSCRIPT_FILENAME = ".kraken.py"
BUILD_SUPPORT_DIRECTORY = "build-support"
LOCK_FILENAME = ".kraken.lock"
_FormatterClass = lambda prog: argparse.RawTextHelpFormatter(prog, max_help_position=60, width=120)  # noqa: 731
logger = logging.getLogger(__name__)
print = partial(builtins.print, "[krakenw]", flush=True)
eprint = partial(print, file=sys.stderr)


def _get_argument_parser() -> argparse.ArgumentParser:
    from kraken._vendor.termcolor import colored
    from kraken.cli.option_sets import LoggingOptions
    from kraken.util.text import inline_text

    from kraken.wrapper.option_sets import EnvOptions

    parser = argparse.ArgumentParser(
        "krakenw",
        formatter_class=_FormatterClass,
        description=inline_text(
            f"""
            This is kraken-wrapper v{__version__}.

            {colored("krakenw", attrs=["bold"])} is a thin wrapper around the {colored("kraken", attrs=["bold"])} cli
            that executes builds in an isolated \\
            build environment. This ensures that builds are reproducible (especially when using \\
            lock files).

            To learn more about kraken, visit https://github.com/kraken-build/kraken-core.
            """
        ),
    )
    parser.add_argument("-V", "--version", version=__version__, action="version")
    LoggingOptions.add_to_parser(parser)
    EnvOptions.add_to_parser(parser)

    # NOTE (@NiklasRosenstein): If we combine "+" with remainder, we get options passed after the `cmd`
    #       passed directly into `args` without argparse treating it like an option. This is not the case
    #       when using `nargs=1` for `cmd`.
    parser.add_argument("cmd", nargs="*", metavar="cmd", help="{lock,l} or a kraken command")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="additional arguments")
    return parser


def _get_lock_argument_parser(prog: str) -> argparse.ArgumentParser:
    from kraken._vendor.termcolor import colored
    from kraken.util.text import inline_text

    parser = argparse.ArgumentParser(
        prog,
        formatter_class=_FormatterClass,
        description=inline_text(
            f"""
            Rewrite the lock file ({colored(LOCK_FILENAME, attrs=["bold"])}) from the current build environment.
            """
        ),
    )

    return parser


def lock(prog: str, argv: list[str], manager: BuildEnvManager, requirements: RequirementSpec) -> NoReturn:
    parser = _get_lock_argument_parser(prog)
    parser.parse_args(argv)

    if not manager.exists():
        print("error: cannot lock without a build environment")
        sys.exit(1)

    environment = manager.get_environment()
    distributions = environment.get_installed_distributions()
    lockfile, extra_distributions = calculate_lockfile(requirements, distributions)
    extra_distributions.discard("pip")  # We'll always have that in a virtual env.

    if extra_distributions:
        eprint("found extra distributions in build enviroment:", ", ".join(extra_distributions))

    had_lockfile = Path(LOCK_FILENAME).exists()
    lockfile.write_to(Path(LOCK_FILENAME))
    manager.set_locked(lockfile)

    eprint("lock file", "updated" if had_lockfile else "created", f"({LOCK_FILENAME})")
    sys.exit(0)


def _print_env_status(
    manager: BuildEnvManager,
    requirements: RequirementSpec,
    lockfile: Lockfile | None,
) -> None:
    from kraken.util.asciitable import AsciiTable
    from kraken.util.json import dt2json

    hash_algorithm = manager.get_hash_algorithm()

    table = AsciiTable()
    table.headers = ["Key", "Source", "Value"]
    table.rows.append(("Requirements", BUILDSCRIPT_FILENAME, requirements.to_hash(hash_algorithm)))
    if lockfile:
        table.rows.append(("Lockfile", LOCK_FILENAME, "-"))
        table.rows.append(("  Requirements hash", "", lockfile.requirements.to_hash(hash_algorithm)))
        table.rows.append(("  Pinned hash", "", lockfile.to_pinned_requirement_spec().to_hash(hash_algorithm)))
    else:
        table.rows.append(("Lockfile", LOCK_FILENAME, "n/a"))
    if manager.exists():
        metadata = manager.get_metadata()
        environment = manager.get_environment()
        table.rows.append(("Environment", str(environment.get_path()), environment.get_type().name))
        table.rows.append(("  Metadata", str(manager.get_metadata_file()), "-"))
        table.rows.append(("    Created at", "", dt2json(metadata.created_at)))
        table.rows.append(("    Requirements hash", "", metadata.requirements_hash))
    else:
        table.rows.append(("Environment", str(manager.get_environment().get_path()), "n/a"))
    table.print()


def _ensure_installed(
    manager: BuildEnvManager,
    requirements: RequirementSpec,
    lockfile: Lockfile | None,
    reinstall: bool,
    upgrade: bool,
    env_type: BuildEnvType | None = None,
) -> None:

    exists = manager.exists()
    install = reinstall or upgrade or not exists

    operation: str
    reason: str | None = None

    if not exists:
        env_type = env_type or env_type or manager.get_environment().get_type()
        operation = "initializing"
    elif upgrade:
        operation = "upgrading"
    elif reinstall:
        operation = "reinstalling"
    else:
        operation = "reusing"

    current_type = manager.get_environment().get_type()
    if env_type is not None:
        type_changed = exists and env_type != current_type
        if not install and type_changed:
            install = True
            manager.remove()
            operation = "re-initializing"
            reason = f"type changed from {current_type.name}"
        elif install and type_changed:
            reason = f"type changed from {current_type.name}"

    if not install and exists:
        metadata = manager.get_metadata()
        if lockfile and metadata.requirements_hash != lockfile.to_pinned_requirement_spec().to_hash(
            metadata.hash_algorithm
        ):
            install = True
            operation = "re-initializing"
            reason = "outdated compared to lockfile"
        if not lockfile and metadata.requirements_hash != requirements.to_hash(metadata.hash_algorithm):
            install = True
            operation = "re-initializing"
            reason = "outdated compared to requirements"

    if install:
        if not lockfile or upgrade:
            source_name = "requirements"
            source = requirements
            transitive = True
        else:
            source_name = "lock file"
            source = lockfile.to_pinned_requirement_spec()
            lockfile = None
            transitive = False

        env_type = env_type or manager.get_environment().get_type()
        eprint(
            operation,
            "build environment of type",
            env_type.name,
            "from",
            source_name,
            f"({reason})" if reason else "",
        )

        tstart = time.perf_counter()
        manager.install(source, env_type, transitive)
        duration = time.perf_counter() - tstart
        eprint(f"operation complete after {duration:.3f}s")

    else:
        eprint(operation, "build environment of type", current_type.name)


def main() -> NoReturn:
    from kraken.cli.option_sets import LoggingOptions
    from kraken.util.requirements import parse_requirements_from_python_script

    from kraken.wrapper.buildenv import BuildEnvManager
    from kraken.wrapper.lockfile import Lockfile
    from kraken.wrapper.option_sets import EnvOptions

    parser = _get_argument_parser()
    args = parser.parse_args()
    LoggingOptions.collect(args).init_logging()
    env_options = EnvOptions.collect(args)

    if not args.cmd and not env_options.any():
        parser.print_usage()
        sys.exit(0)

    if not Path(BUILDSCRIPT_FILENAME).is_file():
        print(f'error: no "{BUILDSCRIPT_FILENAME}" in current directory', file=sys.stderr)
        sys.exit(1)

    # Load requirement spec from build script.
    logger.debug('loading requirements from "%s"', BUILDSCRIPT_FILENAME)
    with Path(BUILDSCRIPT_FILENAME).open() as fp:
        requirements = parse_requirements_from_python_script(fp)
        if not requirements.requirements:
            print(f'error: no requirements in "{BUILDSCRIPT_FILENAME}"')
            sys.exit(1)
        if BUILD_SUPPORT_DIRECTORY not in requirements.pythonpath:
            requirements = requirements.with_pythonpath([BUILD_SUPPORT_DIRECTORY])

    # Load lockfile if it exists.
    if Path(LOCK_FILENAME).is_file():
        logger.debug('loading lockfile from "%s"', LOCK_FILENAME)
        lockfile = Lockfile.from_path(Path(LOCK_FILENAME))
        if not env_options.upgrade and lockfile.requirements != requirements:
            eprint(f'lock file "{LOCK_FILENAME}" is outdated compared to requirements in "{BUILDSCRIPT_FILENAME}"')
            eprint("consider updating the lock file with `krakenw --upgrade lock`")
    else:
        lockfile = None

    manager = BuildEnvManager(BUILDENV_PATH)

    if env_options.status:
        if args.cmd or args.args:
            eprint("error: --status option must be used alone")
            sys.exit(1)
        _print_env_status(manager, requirements, lockfile)
        sys.exit(0)

    if env_options.uninstall:
        if args.cmd or args.args:
            eprint("error: --uninstall option must be used alone")
            sys.exit(1)
        manager.remove()
        sys.exit(0)

    cmd: str | None = args.cmd[0] if args.cmd else None
    argv: list[str] = args.cmd[1:] + args.args

    is_lock_command = cmd in ("lock", "l")

    if env_options.any() or not is_lock_command:
        _ensure_installed(
            manager,
            requirements,
            lockfile,
            env_options.reinstall or (os.getenv("KRAKENW_REINSTALL") == "1"),
            env_options.upgrade,
            env_options.use,
        )

    if cmd is None:
        assert not argv
        sys.exit(0)

    elif is_lock_command:
        lock(f"{parser.prog} lock", argv, manager, requirements)

    else:
        environment = manager.get_environment()
        environment.dispatch_to_kraken_cli([cmd, *argv])


if __name__ == "__main__":
    main()
