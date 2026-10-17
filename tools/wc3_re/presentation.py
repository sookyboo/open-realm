"""Static WC3 ability presentation references, without inventing runtime effects.

`ability_audit -json` owns authored ability/buff decoding; mdxtool owns MDX
metadata parsing; mpqtool owns archive lookup. This module links their evidence.
No MPQ bytes or decompiled game assets are written to the reconstruction.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

from wc3_re.lookup import check_rawcode

MODEL_SUFFIXES = {".mdx", ".mdl"}
IMAGE_SUFFIXES = {".blp", ".tga", ".dds", ".png"}
ART_KEYS = {
    "casterart", "targetart", "specialart", "effectart", "areaeffectart",
    "missileart", "buff_art", "target_art", "special_art", "effect_art", "missile_art",
}
SOUND_KEYS = {"effectsound", "effectsoundlooped", "effect_sound", "effect_sound_looped"}
MAX_MODELS = 128


class PresentationError(RuntimeError):
    """Malformed lookup, invalid executable output or unsafe asset input."""


def normalized_path(value: str) -> str:
    path = value.strip().strip('"').replace("/", "\\")
    if (not path or path.startswith("\\") or ":" in path or "\x00" in path
            or any(part in (".", "..") for part in path.split("\\"))):
        raise PresentationError(f"unsafe asset path: {value!r}")
    return path


def split_references(value: str) -> list[str]:
    if not isinstance(value, str):
        raise PresentationError("art reference must be text")
    return [part.strip().strip('"') for part in value.split(",") if part.strip().strip('"')]


def classify_art(value: str, key: str) -> tuple[str, str]:
    path = normalized_path(value)
    suffix = Path(path).suffix.casefold()
    if key.casefold() == "art" or suffix in IMAGE_SUFFIXES:
        return "texture_or_icon", path
    if suffix == ".mdl":
        path = path[:-4] + ".mdx"
    elif suffix == "":
        path += ".mdx"
    elif suffix != ".mdx":
        return "unclassified_art_reference", path
    return "model", path


def _capture(command: list[str]) -> bytes | None:
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


class ArchiveResolver:
    """Queries only the archives selected by the edition-specific audit."""

    def __init__(self, archives: list[str], mpqtool: Path, mdxtool: Path):
        self.archives = [Path(name) for name in archives if isinstance(name, str)]
        self.mpqtool, self.mdxtool = mpqtool, mdxtool
        self.contents: dict[tuple[str, str], bytes | None] = {}
        self.models: dict[str, dict[str, Any]] = {}

    def read(self, path: str) -> tuple[bytes | None, str | None]:
        # ability_audit preserves the engine collector's first-wins ordering:
        # localized/expansion overlays precede the base archive. Keep that
        # order so an authored override is not shadowed by a lower-priority row.
        for archive in self.archives:
            key = (str(archive), path.casefold())
            if key not in self.contents:
                self.contents[key] = _capture([str(self.mpqtool), "-mpq", str(archive),
                                               "cat", path])
            if self.contents[key] is not None:
                return self.contents[key], str(archive)
        return None, None

    def inspect_model(self, path: str) -> dict[str, Any]:
        key = path.casefold()
        if key in self.models:
            return self.models[key]
        contents, source = self.read(path)
        if contents is None or source is None:
            result = {"path": path, "status": "not_found_in_selected_archives"}
        else:
            output = _capture([str(self.mdxtool), "-mpq", source, "-model", path,
                               "--info-json"])
            if output is None:
                result = {"path": path, "archive": source, "status": "metadata_unavailable"}
            else:
                try:
                    doc = json.loads(output)
                except (ValueError, UnicodeDecodeError) as error:
                    raise PresentationError(f"mdxtool returned invalid JSON for {path}: {error}") from error
                if (not isinstance(doc, dict) or doc.get("schema_version") != 1
                        or doc.get("path", "").casefold() != path.casefold()
                        or not isinstance(doc.get("sequences"), list)
                        or not isinstance(doc.get("textures"), list)):
                    raise PresentationError(f"mdxtool returned invalid metadata for {path}")
                result = {**doc, "archive": source, "status": "static_model_metadata"}
        self.models[key] = result
        return result


def parse_sylk(raw: bytes) -> list[dict[str, str]]:
    """Read the simple C;X;Y;K cell subset in Warcraft's SYLK sound tables.

    Unsupported cell commands are ignored, and no absent field is filled in.
    """
    try:
        lines = raw.decode("cp1252").splitlines()
    except UnicodeDecodeError as error:
        raise PresentationError(f"cannot decode sound table: {error}") from error
    grid: dict[int, dict[int, str]] = {}
    x = y = 1
    for line in lines:
        if not line.startswith("C;"):
            continue
        match_x = re.search(r"(?:^|;)X(\d+)(?:;|$)", line)
        match_y = re.search(r"(?:^|;)Y(\d+)(?:;|$)", line)
        if match_x:
            x = int(match_x.group(1))
        if match_y:
            y = int(match_y.group(1))
        match_value = re.search(r"(?:^|;)K(.*)$", line)
        if not match_value:
            continue
        value = match_value.group(1)
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('""', '"')
        if x > 4096 or y > 200000:
            raise PresentationError("SYLK table exceeds supported dimensions")
        grid.setdefault(y, {})[x] = value
    headers = {x: value for x, value in grid.get(1, {}).items()}
    if not headers:
        return []
    return [{name: cell[x] for x, name in headers.items() if x in cell}
            for y, cell in sorted(grid.items()) if y > 1]


def _sound_rows(resolver: ArchiveResolver) -> tuple[list[dict[str, str]], str | None]:
    data, source = resolver.read("UI\\SoundInfo\\AbilitySounds.slk")
    if data is None:
        return [], None
    return parse_sylk(data), source


def _sound_match(alias: str, rows: list[dict[str, str]], source: str | None) -> dict[str, Any]:
    row = next((item for item in rows if any(
        name.casefold() in {"soundname", "name", "id", ""} and value.casefold() == alias.casefold()
        for name, value in item.items())), None)
    if row is None:
        return {"alias": alias, "status": "unresolved_sound_alias", "table": source}
    result = {"alias": alias, "status": "authored_sound_row", "table": source,
              "fields": row, "note": "File variants and pitch data are authored; no runtime selection is inferred."}
    directory = next((v for k, v in row.items() if k.casefold() == "directorybase"), "")
    variants = next((v for k, v in row.items() if k.casefold() == "filenames"), "")
    if variants:
        result["authored_file_candidates"] = [directory.rstrip("\\/") + "\\" + name.strip()
                                              if directory else name.strip()
                                              for name in variants.split(",") if name.strip()]
    return result


EVENT_TABLES = {
    "SPN": ("Splats\\SpawnData.slk", "Model"),
    "SPL": ("Splats\\SplatData.slk", None),
    "FPT": ("Splats\\SplatData.slk", None),
    "UBR": ("Splats\\UberSplatData.slk", None),
    "SND": ("UI\\SoundInfo\\AnimLookups.slk", "SoundLabel"),
}
UNIT_UI_TABLE = "Units\\UnitUI.slk"


def _unit_ui_row(rows: list[dict[str, str]], unit_id: str) -> dict[str, str] | None:
    """Find the authored UnitUI display row for an AbilityData UnitID."""
    return next((row for row in rows if any(
        key.casefold() == "unituiid" and value.casefold() == unit_id.casefold()
        for key, value in row.items())), None)


def _field(row: dict[str, str], name: str) -> str:
    return next((value for key, value in row.items() if key.casefold() == name.casefold()), "")


def _lookup_row(rows: list[dict[str, str]], name: str) -> dict[str, str] | None:
    lookup_columns = {"id", "name", "soundname", "animsoundevent", ""}
    return next((row for row in rows if any(
        k.casefold() in lookup_columns and v.casefold() == name.casefold()
        for k, v in row.items())), None)


def resolve_model_events(resolver: ArchiveResolver, models: dict[str, dict[str, Any]],
                         max_models: int, gaps: list[str], sounds: dict[str, dict[str, Any]]) -> None:
    """Follow only the explicitly decoded MDX event families and data tables."""
    tables: dict[str, tuple[list[dict[str, str]], str | None]] = {}
    queue = [(key, 0) for key in models]
    visited: set[str] = set()
    while queue:
        key, depth = queue.pop(0)
        if key in visited:
            continue
        visited.add(key)
        metadata = models[key]
        if metadata.get("status") != "static_model_metadata":
            continue
        if not metadata.get("event_objects_decoded", False):
            if metadata.get("chunks", {}).get("EVTS"):
                gaps.append(f"MDX event objects not decoded: {metadata['path']}")
            continue
        event_links: list[dict[str, Any]] = []
        for event in metadata.get("events", []):
            if not isinstance(event, dict) or not isinstance(event.get("name"), str):
                raise PresentationError("mdxtool returned malformed event objects")
            name = event["name"]
            family = name[:3]
            if family not in EVENT_TABLES or len(name) <= 4:
                continue
            identifier = name[4:].strip()
            table, _ = EVENT_TABLES[family]
            if table not in tables:
                raw, archive = resolver.read(table)
                tables[table] = (parse_sylk(raw) if raw is not None else [], archive)
            rows, archive = tables[table]
            row = _lookup_row(rows, identifier)
            link: dict[str, Any] = {"family": family, "event_name": name,
                                    "id": identifier, "keys_ms": event.get("keys_ms", []),
                                    "table": table, "table_archive": archive,
                                    "status": "authored_table_row" if row else "unresolved_event_row"}
            if row:
                link["fields"] = row
                if family == "SPN":
                    child = next((v for k, v in row.items() if k.casefold() == "model"), "")
                    if child:
                        kind, child_path = classify_art(child, "EffectArt")
                        link["child_model"] = child_path
                        if kind == "model" and child_path.casefold() not in models:
                            if depth < 3 and len(models) < max_models:
                                models[child_path.casefold()] = resolver.inspect_model(child_path)
                                queue.append((child_path.casefold(), depth + 1))
                            else:
                                gaps.append(f"Child model budget/depth reached: {child_path}")
                elif family == "SND":
                    label = next((v for k, v in row.items() if k.casefold() == "soundlabel"), identifier)
                    if label:
                        link["sound_alias"] = label
                        sounds.setdefault("animation:" + label.casefold(), {"alias": label,
                                            "source_type": "animation", "status": "unresolved_sound_alias"})
            else:
                gaps.append(f"Unresolved {family} event table row {identifier} in {metadata['path']}")
            event_links.append(link)
        metadata["event_dependencies"] = event_links


def build_presentation(lookup: dict[str, Any], *, mpqtool: Path,
                       mdxtool: Path, inspect_assets: bool = True,
                       max_models: int = MAX_MODELS) -> dict[str, Any]:
    if not isinstance(lookup, dict) or lookup.get("schema_version") != 1:
        raise PresentationError("unsupported lookup schema")
    rawcode = check_rawcode(lookup.get("rawcode", ""))
    editions = lookup.get("editions")
    if not isinstance(editions, dict):
        raise PresentationError("lookup lacks editions")
    if not isinstance(max_models, int) or not (1 <= max_models <= 1024):
        raise PresentationError("max_models must be between 1 and 1024")
    output: dict[str, Any] = {"schema_version": 1, "rawcode": rawcode,
                              "state": "authored_presentation_and_static_model_metadata_only",
                              "editions": {}, "runtime_effect_timing_verified": False}
    for edition, doc in editions.items():
        if edition not in ("roc", "tft") or not isinstance(doc, dict):
            raise PresentationError("invalid edition in lookup")
        if not doc.get("found"):
            output["editions"][edition] = {"found": False}
            continue
        archives = doc.get("archives", [])
        if not isinstance(archives, list) or any(not isinstance(a, str) for a in archives):
            raise PresentationError("invalid archive list")
        resolver = ArchiveResolver(archives, mpqtool, mdxtool)
        unit_ui_rows: list[dict[str, str]] | None = None
        unit_ui_archive: str | None = None
        references: list[dict[str, Any]] = []
        models: dict[str, dict[str, Any]] = {}
        sounds: dict[str, dict[str, Any]] = {}
        gaps: list[str] = ["Runtime choice/timing, attachment spawning and effect lifetime require native evidence."]
        row = doc.get("ability", {})
        if not isinstance(row, dict):
            raise PresentationError("missing ability data")

        def add_fields(fields: dict[str, Any], source: str, *, rank: int | None = None) -> None:
            if not isinstance(fields, dict):
                raise PresentationError(f"presentation source {source} is not an object")
            for field, value in sorted(fields.items()):
                if not isinstance(value, str) or not value.strip():
                    continue
                name = field.casefold()
                if name in ART_KEYS or name == "art":
                    for raw in split_references(value):
                        category, asset = classify_art(raw, field)
                        references.append({"source": source, "field": field, "rank": rank,
                                           "value": raw, "asset": asset, "kind": category,
                                           "evidence": "authored_data_only"})
                        if category == "model" and asset.casefold() not in models:
                            if len(models) < max_models and inspect_assets:
                                models[asset.casefold()] = resolver.inspect_model(asset)
                            elif len(models) >= max_models:
                                gaps.append("Model inspection limit reached; remaining references preserved.")
                            else:
                                models[asset.casefold()] = {"path": asset, "status": "not_inspected"}
                elif name in SOUND_KEYS:
                    for alias in split_references(value):
                        references.append({"source": source, "field": field, "rank": rank,
                                           "value": alias, "kind": "sound_alias",
                                           "evidence": "authored_data_only"})
                        sounds.setdefault("ability:" + alias.casefold(), {"alias": alias,
                                            "source_type": "ability", "status": "unresolved_sound_alias"})

        if "presentation" not in doc:
            gaps.append("Lookup was generated before ability_audit gained AbilityFunc presentation fields; regenerate lookup.")
        if "effects" not in doc:
            gaps.append("Lookup lacks decoded EfctID presentation rows; regenerate lookup with updated ability_audit.")
        add_fields(doc.get("presentation", {}), f"AbilityFunc:{rawcode}")
        for key in ("buffs", "effects"):
            for buff in doc.get(key, []):
                if not isinstance(buff, dict) or not isinstance(buff.get("id"), str):
                    raise PresentationError(f"malformed {key} row")
                add_fields(buff, f"AbilityBuffData:{buff['id']}")
        # Rank-level relationships are retained even if the referenced
        # UnitUI/EfctID or custom object is not present in the audit output.
        rank_links = []
        for rank in doc.get("ranks", []):
            rank_link = {"level": rank.get("level"), "unit_id": rank.get("unit_id"),
                         "buff_ids": rank.get("buff_ids", []),
                         "effect_id": rank.get("effect_id")}
            unit_id = rank.get("unit_id")
            if unit_id:
                unit_link: dict[str, Any] = {"unit_id": unit_id, "status": "not_inspected"}
                if inspect_assets:
                    if unit_ui_rows is None:
                        raw, unit_ui_archive = resolver.read(UNIT_UI_TABLE)
                        unit_ui_rows = parse_sylk(raw) if raw is not None else []
                    unit_row = _unit_ui_row(unit_ui_rows, unit_id)
                    if unit_row is None:
                        unit_link["status"] = "unit_ui_row_not_found"
                        gaps.append(f"UnitID {unit_id} has no UnitUI row in selected archives.")
                    else:
                        unit_link.update({"status": "authored_unit_ui_row",
                                          "table": UNIT_UI_TABLE,
                                          "table_archive": unit_ui_archive,
                                          "fields": unit_row})
                        file_name = _field(unit_row, "file")
                        if file_name and file_name != "-":
                            kind, unit_model = classify_art(file_name, "TargetArt")
                            unit_link["model"] = unit_model
                            unit_link["model_kind"] = kind
                            if kind == "model":
                                key = unit_model.casefold()
                                if key not in models:
                                    if len(models) < max_models:
                                        models[key] = resolver.inspect_model(unit_model)
                                    else:
                                        gaps.append("Model inspection limit reached; UnitUI model metadata omitted.")
                                unit_link["model_status"] = models.get(key, {}).get("status", "inspection_limit")
                        else:
                            unit_link["model_status"] = "no_authored_model_path"
                rank_link["unit_ui"] = unit_link
            rank_links.append(rank_link)
            if rank.get("effect_id"):
                linked = [effect for effect in doc.get("effects", [])
                          if isinstance(effect, dict) and effect.get("id") == rank["effect_id"]]
                if not linked or not any(value for field, value in linked[0].items()
                                         if field != "id"):
                    gaps.append(f"EfctID {rank['effect_id']} lacks a resolved presentation row.")
        if inspect_assets:
            resolve_model_events(resolver, models, max_models, gaps, sounds)
        if sounds and inspect_assets:
            ability_rows, ability_source = _sound_rows(resolver)
            anim_data, anim_source = resolver.read("UI\\SoundInfo\\AnimSounds.slk")
            anim_rows = parse_sylk(anim_data) if anim_data is not None else []
            for key, item in list(sounds.items()):
                if item.get("source_type") == "animation":
                    value = _sound_match(item["alias"], anim_rows, anim_source)
                else:
                    value = _sound_match(item["alias"], ability_rows, ability_source)
                value["source_type"] = item.get("source_type", "ability")
                sounds[key] = value
        if any(m.get("status") != "static_model_metadata" for m in models.values()):
            gaps.append("One or more referenced models were not inspected successfully.")
        if any(m.get("chunks", {}).get("EVTS") and not m.get("event_objects_decoded")
               for m in models.values()):
            gaps.append("Some MDX EVTS payloads could not be decoded safely.")
        output["editions"][edition] = {
            "found": True, "archives": archives, "rank_links": rank_links,
            "references": references, "models": list(models.values()),
            "sounds": list(sounds.values()), "gaps": list(dict.fromkeys(gaps)),
            "notes": ["Source archive identity is selected from the audit's edition archive list.",
                      "No runtime effects, model sequence selections or timings are proven."],
        }
    return output


def write_presentation(report: dict[str, Any], directory: Path) -> None:
    if directory.exists():
        raise PresentationError(f"refusing existing output directory: {directory}")
    directory.mkdir(parents=True)
    (directory / "assets.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = [f"# Presentation references — {report['rawcode']}", "",
             "Authoring evidence and model metadata only; **not an observed runtime timeline**.", ""]
    for edition, data in report["editions"].items():
        lines += [f"## {edition.upper()}", ""]
        if not data["found"]:
            lines += ["Ability absent in this edition.", ""]
            continue
        for ref in data["references"]:
            lines.append(f"- `{ref['source']}.{ref['field']}` → `{ref['value']}` ({ref['kind']})")
        lines.extend(["", "### Unresolved", ""])
        lines.extend(f"- {gap}" for gap in data["gaps"])
        lines.append("")
    (directory / "review.md").write_text("\n".join(lines), encoding="utf-8")
