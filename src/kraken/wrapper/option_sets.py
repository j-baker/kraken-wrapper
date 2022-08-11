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
    use_env_type: BuildEnvType | None

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
            "--use-env-type",
            choices=[v.name for v in BuildEnvType],
            default=os.getenv("KRAKENW_ENV_TYPE"),
            help="use the specified build environment type; reinstalls the environment on change [default: PEX_ZIPAPP]",
        )

    @classmethod
    def collect(cls, args: argparse.Namespace) -> EnvOptions:
        from kraken.wrapper.buildenv import BuildEnvType

        return cls(
            status=args.status,
            upgrade=args.upgrade,
            reinstall=args.reinstall,
            uninstall=args.uninstall,
            use_env_type=BuildEnvType[args.use_env_type] if args.use_env_type else None,
        )

    def any(self) -> bool:
        return bool(self.status or self.upgrade or self.reinstall or self.uninstall or self.use_env_type)
