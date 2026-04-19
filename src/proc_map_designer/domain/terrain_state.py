from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from proc_map_designer.domain.validators import require_bool, require_float, require_int, require_mapping, require_string


@dataclass(slots=True)
class TerrainNoiseSettings:
    enabled: bool = False
    scale: float = 1.0
    strength: float = 0.25
    octaves: int = 4
    roughness: float = 0.5
    seed: int = 0

    def __post_init__(self) -> None:
        self.enabled = require_bool(self.enabled, "terrain_settings.noise.enabled")
        self.scale = require_float(self.scale, "terrain_settings.noise.scale", min_value=0.01, max_value=100.0)
        self.strength = require_float(self.strength, "terrain_settings.noise.strength", min_value=0.0, max_value=1.0)
        self.octaves = require_int(self.octaves, "terrain_settings.noise.octaves", min_value=1, max_value=8)
        self.roughness = require_float(
            self.roughness,
            "terrain_settings.noise.roughness",
            min_value=0.0,
            max_value=1.0,
        )
        self.seed = require_int(self.seed, "terrain_settings.noise.seed")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerrainNoiseSettings":
        mapping = require_mapping(data, "terrain_settings.noise")
        return cls(
            enabled=mapping.get("enabled", False),
            scale=mapping.get("scale", 1.0),
            strength=mapping.get("strength", 0.25),
            octaves=mapping.get("octaves", 4),
            roughness=mapping.get("roughness", 0.5),
            seed=mapping.get("seed", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "scale": self.scale,
            "strength": self.strength,
            "octaves": self.octaves,
            "roughness": self.roughness,
            "seed": self.seed,
        }


@dataclass(slots=True)
class TerrainSettings:
    enabled: bool = False
    max_height: float = 10.0
    viewport_subdivision: int = 6
    export_subdivision: int = 7
    heightfield_resolution: int = 512
    heightfield_path: str = ""
    noise: TerrainNoiseSettings = field(default_factory=TerrainNoiseSettings)

    def __post_init__(self) -> None:
        self.enabled = require_bool(self.enabled, "terrain_settings.enabled")
        self.max_height = require_float(self.max_height, "terrain_settings.max_height", min_value=0.0)
        self.viewport_subdivision = require_int(
            self.viewport_subdivision,
            "terrain_settings.viewport_subdivision",
            min_value=4,
            max_value=8,
        )
        self.export_subdivision = require_int(
            self.export_subdivision,
            "terrain_settings.export_subdivision",
            min_value=4,
            max_value=9,
        )
        self.heightfield_resolution = require_int(
            self.heightfield_resolution,
            "terrain_settings.heightfield_resolution",
            min_value=64,
            max_value=4096,
        )
        self.heightfield_path = require_string(
            self.heightfield_path,
            "terrain_settings.heightfield_path",
            allow_empty=True,
        )
        if not isinstance(self.noise, TerrainNoiseSettings):
            self.noise = TerrainNoiseSettings.from_dict(require_mapping(self.noise, "terrain_settings.noise"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerrainSettings":
        mapping = require_mapping(data, "terrain_settings")
        return cls(
            enabled=mapping.get("enabled", False),
            max_height=mapping.get("max_height", 10.0),
            viewport_subdivision=mapping.get("viewport_subdivision", 6),
            export_subdivision=mapping.get("export_subdivision", 7),
            heightfield_resolution=mapping.get("heightfield_resolution", 512),
            heightfield_path=mapping.get("heightfield_path", ""),
            noise=TerrainNoiseSettings.from_dict(require_mapping(mapping.get("noise", {}), "terrain_settings.noise")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_height": self.max_height,
            "viewport_subdivision": self.viewport_subdivision,
            "export_subdivision": self.export_subdivision,
            "heightfield_resolution": self.heightfield_resolution,
            "heightfield_path": self.heightfield_path,
            "noise": self.noise.to_dict(),
        }
