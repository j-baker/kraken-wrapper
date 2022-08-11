from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kraken.util.requirements import RequirementSpec


@dataclasses.dataclass
class Lockfile:
    requirements: RequirementSpec
    pinned: dict[str, str]

    @staticmethod
    def from_path(path: Path) -> Lockfile:
        import tomli

        with path.open("rb") as fp:
            return Lockfile.from_json(tomli.load(fp))

    def write_to(self, path: Path) -> None:
        import tomli_w

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)

    @staticmethod
    def from_json(data: dict[str, Any]) -> Lockfile:
        from kraken.util.requirements import RequirementSpec

        return Lockfile(
            requirements=RequirementSpec.from_json(data["requirements"]),
            pinned=data["pinned"],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "requirements": self.requirements.to_json(),
            "pinned": self.pinned,
        }

    def to_pinned_requirement_spec(self) -> RequirementSpec:
        """Converts the pinned versions in the lock file to a :class:`RequirementSpec` with the pinned requirements."""

        from kraken.util.requirements import LocalRequirement, RequirementSpec

        requirements = RequirementSpec(
            requirements=(),
            index_url=self.requirements.index_url,
            extra_index_urls=self.requirements.extra_index_urls[:],
            pythonpath=self.requirements.pythonpath[:],
            interpreter_constraint=self.requirements.interpreter_constraint,
        )

        # Make sure that local requirements keep being installed from the local source.
        local_requirements = {
            dep.name: dep for dep in self.requirements.requirements if isinstance(dep, LocalRequirement)
        }
        requirements = requirements.with_requirements(local_requirements.values())

        # Add all non-local requirements with exact version numbers.
        requirements = requirements.with_requirements(
            f"{key}=={value}" for key, value in sorted(self.pinned.items()) if key not in local_requirements
        )

        return requirements
