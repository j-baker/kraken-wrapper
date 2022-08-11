from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from kraken.wrapper.buildenv import BuildEnvType


@dataclasses.dataclass(frozen=True)
class EnvOptions:
    status: bool
    upgrade: bool
    reinstall: bool
    uninstall: bool
    use: BuildEnvType | None

    @staticmethod
    def add_to_parser(parser: argparse.ArgumentParser) -> None:
        from kraken.wrapper.buildenv import BuildEnvType

        parser.add_argument(
            "--status",
            action="store_true",
            help="print the status of the build environment and exit",
        )
        parser.add_argument(
            "--upgrade",
            action="store_true",
            help="reinstall the build environment from the original requirements",
        )
        parser.add_argument(
            "--reinstall",
            action="store_true",
            help="reinstall the build environment from the lock file",
        )
        parser.add_argument(
            "--uninstall",
            action="store_true",
            help="uninstall the build environment",
        )
        parser.add_argument(
            "--use",
            choices=[v.name for v in BuildEnvType],
            default=os.getenv("KRAKENW_USE"),
            help="use the specified environment type. If the environment type changes it will trigger a reinstall.\n"
            "Defaults to the value of the KRAKENW_USE environment variable. If that variable is unset, and\nif a build "
            "environment already exists, that environment's type will be used. The default\nenvironment type that is "
            "used for new environments is PEX_ZIPAPP.",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> EnvOptions:
        from kraken.wrapper.buildenv import BuildEnvType

        return cls(
            status=args.status,
            upgrade=args.upgrade,
            reinstall=args.reinstall,
            uninstall=args.uninstall,
            use=BuildEnvType[args.use] if args.use else None,
        )

    def any(self) -> bool:
        return bool(self.status or self.upgrade or self.reinstall or self.uninstall or self.use)
