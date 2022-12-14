from __future__ import annotations

import abc
import contextlib
import copy
import dataclasses
import datetime
import hashlib
import json
import logging
import os
import pprint
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, NoReturn, Sequence
from urllib.parse import quote, urlparse, urlunparse

from kraken.common import (
    EnvironmentType,
    NotSet,
    RequirementSpec,
    datetime_to_iso8601,
    iso8601_to_datetime,
    lazy_str,
    not_none,
    safe_rmpath,
)
from kraken.common.pyenv import VirtualEnvInfo
from pex.pex import PEX
from pex.pex_bootstrapper import bootstrap_pex_env

from ._config import AuthModel
from ._lockfile import Distribution, Lockfile
from ._pex import PEXBuildConfig, PEXLayout

logger = logging.getLogger(__name__)

KRAKEN_MAIN_IMPORT_SNIPPET = """
try:
    from kraken.core.cli.main import main  # >= 0.9.0
except ImportError:
    from kraken.cli.main import main  # < 0.9.0
""".strip()


class BuildEnv(abc.ABC):
    """Interface for the build environment."""

    @abc.abstractmethod
    def get_type(self) -> EnvironmentType:
        """Return the type of build environment that this is."""

    @abc.abstractmethod
    def get_path(self) -> Path:
        """Return the path to the build environment."""

    @abc.abstractmethod
    def get_installed_distributions(self) -> list[Distribution]:
        """Return the distributions that are currently installed in the environment."""

    @abc.abstractmethod
    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        """Build the environment from the given requirement spec."""

    @abc.abstractmethod
    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        """Dispatch the kraken cli command in *argv* to the build environment.

        :param argv: The arguments to pass to the kraken cli (without the "kraken" command name itself)."""


@dataclasses.dataclass(frozen=True)
class BuildEnvMetadata:
    created_at: datetime.datetime
    environment_type: EnvironmentType
    requirements_hash: str
    hash_algorithm: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BuildEnvMetadata:
        return cls(
            created_at=iso8601_to_datetime(data["created_at"]),
            environment_type=EnvironmentType[data["environment_type"]],
            requirements_hash=data["requirements_hash"],
            hash_algorithm=data["hash_algorithm"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "created_at": datetime_to_iso8601(self.created_at),
            "environment_type": self.environment_type.name,
            "requirements_hash": self.requirements_hash,
            "hash_algorithm": self.hash_algorithm,
        }


@dataclasses.dataclass
class BuildEnvMetadataStore:
    path: Path

    def __post_init__(self) -> None:
        self._metadata: BuildEnvMetadata | None | NotSet = NotSet.Value

    def get(self) -> BuildEnvMetadata | None:
        if self._metadata is NotSet.Value:
            if self.path.is_file():
                self._metadata = BuildEnvMetadata.from_json(json.loads(self.path.read_text()))
            else:
                self._metadata = None
        return self._metadata

    def set(self, metadata: BuildEnvMetadata) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(metadata.to_json()))
        self._metadata = metadata


class PexBuildEnv(BuildEnv):
    STYLES = (EnvironmentType.PEX_ZIPAPP, EnvironmentType.PEX_PACKED, EnvironmentType.PEX_LOOSE)

    def __init__(self, style: EnvironmentType, path: Path) -> None:
        assert style in self.STYLES
        self._style = style
        self._path = path

    @contextlib.contextmanager
    def activate(self) -> Iterator[None]:
        assert self._path.exists(), f'expected PEX file at "{self._path}"'
        pex = PEX(self._path)

        state = {}
        for key in ["displayhook", "excepthook", "modules", "path", "path_importer_cache"]:
            state[key] = copy.copy(getattr(sys, key))

        try:
            bootstrap_pex_env(str(pex.path()))
            pex.activate()
            yield
        finally:
            for key, value in state.items():
                setattr(sys, key, value)

    # BuildEnv

    def get_path(self) -> Path:
        return self._path

    def get_type(self) -> EnvironmentType:
        return self._style

    def get_installed_distributions(self) -> list[Distribution]:
        return _get_installed_distributions([sys.executable, str(self._path)])

    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        config = PEXBuildConfig(
            interpreter_constraints=(
                [requirements.interpreter_constraint] if requirements.interpreter_constraint else []
            ),
            script="kraken",
            requirements=requirements.to_args(Path.cwd(), with_options=False),
            index_url=requirements.index_url,
            extra_index_urls=list(requirements.extra_index_urls),
            transitive=True,  # Our lockfiles are not fully cross platform compatible (see kraken-wrapper#2)
        )

        layout = {
            EnvironmentType.PEX_ZIPAPP: PEXLayout.ZIPAPP,
            EnvironmentType.PEX_PACKED: PEXLayout.PACKED,
            EnvironmentType.PEX_LOOSE: PEXLayout.LOOSE,
        }[self._style]

        logger.debug("PEX build configuration is %s", lazy_str(lambda: pprint.pformat(config)))

        logger.info('begin PEX resolve for build environment "%s"', self._path)
        installed = config.resolve()

        logger.info('building PEX for build environment "%s"', self._path)
        builder = config.builder(installed)
        builder.build(str(self._path), layout=layout)

    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        with self.activate():
            import logging

            scope: dict[str, Any] = {}
            exec(KRAKEN_MAIN_IMPORT_SNIPPET, scope)
            main: Callable[[str, Sequence[str]], NoReturn] = scope["main"]

            # We need to un-initialize the logger such that kraken-core can re-initialize it.
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)

            env_backup = os.environ.copy()
            self.get_type().set(os.environ)

            try:
                main("krakenw", argv)
            finally:
                os.environ.clear()
                os.environ.update(env_backup)

        assert False, "should not be reached"


class VenvBuildEnv(BuildEnv):
    def __init__(self, path: Path, incremental: bool = False) -> None:
        self._path = path
        self._venv = VirtualEnvInfo(self._path)
        self._incremental = incremental

    # BuildEnv

    def get_path(self) -> Path:
        return self._path

    def get_type(self) -> EnvironmentType:
        return EnvironmentType.VENV

    def get_installed_distributions(self) -> list[Distribution]:
        python = self._venv.get_bin("python")
        return _get_installed_distributions([str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()"])

    def build(self, requirements: RequirementSpec, transitive: bool) -> None:
        if not self._incremental and self._path.exists():
            logger.debug("Removing existing virtual environment at %s", self._path)
            safe_rmpath(self._path)

        python_bin = str(self._venv.get_bin("python"))

        if not self._path.exists():
            command = [sys.executable, "-m", "venv", str(self._path)]
            logger.debug("Creating virtual environment at %s: %s", self._path, " ".join(command))
            subprocess.check_call(command)

            # Upgrade Pip.
            command = [python_bin, "-m", "pip", "install", "--upgrade", "pip"]
            logger.debug("Upgrading Pip: %s", command)
            subprocess.check_call(command)

        else:
            logger.debug("Reusing virtual environment at %s", self._path)

        # Install requirements.
        command = [
            python_bin,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--no-input",
        ]
        # Must enable transitive resolution because lock files are not currently cross platform (see kraken-wrapper#2).
        # if not transitive:
        #     command += ["--no-deps"]
        # TODO (@NiklasRosenstein): Handle requirements interpreter constraint (see kraken-wrapper#5).
        command += requirements.to_args()
        logger.debug("Installing into build environment with Pip: %s", " ".join(command))
        subprocess.check_call(command)

        # Make sure the pythonpath from the requirements is encoded into the enviroment.
        command = [python_bin, "-c", "from sysconfig import get_path; print(get_path('purelib'))"]
        site_packages = Path(subprocess.check_output(command).decode().strip())
        pth_file = site_packages / "krakenw.pth"
        if requirements.pythonpath:
            logger.debug("Writing .pth file at %s", pth_file)
            pth_file.write_text("\n".join(str(Path(path).absolute()) for path in requirements.pythonpath))
        elif pth_file.is_file():
            logger.debug("Removing .pth file at %s", pth_file)
            pth_file.unlink()

    def dispatch_to_kraken_cli(self, argv: list[str]) -> NoReturn:
        python = self._venv.get_bin("python")
        command = [str(python), "-c", f"{KRAKEN_MAIN_IMPORT_SNIPPET}\nmain()", *argv]
        env = os.environ.copy()
        self.get_type().set(env)
        sys.exit(subprocess.call(command, env=env))


class BuildEnvManager:
    def __init__(
        self,
        path: Path,
        auth: AuthModel,
        default_type: EnvironmentType = EnvironmentType.VENV,
        default_hash_algorithm: str = "sha256",
    ) -> None:
        assert (
            default_hash_algorithm in hashlib.algorithms_available
        ), f"hash algoritm {default_hash_algorithm!r} is not available"

        self._path = path
        self._auth = auth
        self._metadata_store = BuildEnvMetadataStore(path.parent / (path.name + ".meta"))
        self._default_type = default_type
        self._default_hash_algorithm = default_hash_algorithm

    def _inject_auth(self, url: str) -> str:
        parsed_url = urlparse(url)
        credentials = self._auth.get_credentials(parsed_url.netloc)
        if credentials is None:
            return url

        logger.info('Injecting username and password into index url "%s"', url)
        domain = parsed_url.netloc.rpartition("@")[-1]
        parsed_url = parsed_url._replace(netloc=f"{quote(credentials.username)}:{quote(credentials.password)}@{domain}")
        url = urlunparse(parsed_url)
        return url

    def exists(self) -> bool:
        if self._metadata_store.get() is None:
            return False  # If we don't have metadata, we assume the environment does not exist.
        return self.get_environment().get_path().exists()

    def remove(self) -> None:
        safe_rmpath(self._metadata_store.path)
        safe_rmpath(self.get_environment().get_path())

    def install(
        self,
        requirements: RequirementSpec,
        env_type: EnvironmentType | None = None,
        transitive: bool = True,
    ) -> None:
        """
        :param requirements: The requirements to build the environment with.
        :param env_type: The environment type to use. If not specified, falls back to the last used or default.
        :param transitive: If set to `False`, it indicates that the *requirements* are fully resolved and the
            build environment installer does not need to resolve transitve dependencies.
        """

        if env_type is None:
            metadata = self._metadata_store.get()
            env_type = metadata.environment_type if metadata else self._default_type

        # Inject credentials into the requirements.
        requirements = RequirementSpec(
            requirements=requirements.requirements,
            index_url=self._inject_auth(requirements.index_url) if requirements.index_url else None,
            extra_index_urls=tuple(self._inject_auth(url) for url in requirements.extra_index_urls),
            interpreter_constraint=requirements.interpreter_constraint,
            pythonpath=requirements.pythonpath,
        )

        env = _get_environment_for_type(env_type, self._path)
        env.build(requirements, transitive)
        hash_algorithm = self.get_hash_algorithm()
        metadata = BuildEnvMetadata(
            datetime.datetime.utcnow(),
            env.get_type(),
            requirements.to_hash(hash_algorithm),
            hash_algorithm,
        )
        self._metadata_store.set(metadata)

    def get_metadata_file(self) -> Path:
        return self._metadata_store.path

    def get_metadata(self) -> BuildEnvMetadata:
        return not_none(self._metadata_store.get(), "metadata does not exist")

    def get_hash_algorithm(self) -> str:
        metadata = self._metadata_store.get()
        return metadata.hash_algorithm if metadata else self._default_hash_algorithm

    def get_environment(self) -> BuildEnv:
        metadata = self._metadata_store.get()
        environment_type = self._default_type if metadata is None else metadata.environment_type
        return _get_environment_for_type(environment_type, self._path)

    def set_locked(self, lockfile: Lockfile) -> None:
        metadata = self._metadata_store.get()
        assert metadata is not None
        metadata = BuildEnvMetadata(
            metadata.created_at,
            metadata.environment_type,
            lockfile.to_pinned_requirement_spec().to_hash(metadata.hash_algorithm),
            metadata.hash_algorithm,
        )
        self._metadata_store.set(metadata)


def _get_environment_for_type(environment_type: EnvironmentType, base_path: Path) -> BuildEnv:
    if environment_type in PexBuildEnv.STYLES:
        return PexBuildEnv(environment_type, base_path.parent / (base_path.name + ".pex"))
    elif environment_type == EnvironmentType.VENV:
        return VenvBuildEnv(base_path, incremental=os.getenv("KRAKENW_INCREMENTAL") == "1")
    else:
        raise RuntimeError(f"unsupported environment type: {environment_type!r}")


def _get_installed_distributions(kraken_command_prefix: Sequence[str]) -> list[Distribution]:
    command = [*kraken_command_prefix, "query", "env"]
    output = subprocess.check_output(command).decode()
    return [Distribution(x["name"], x["version"], x["requirements"], x["extras"]) for x in json.loads(output)]
