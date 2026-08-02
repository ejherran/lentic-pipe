#!/usr/bin/env python
"""Validate the locked-analysis contract for the thesis closure experiments."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_PLAN = Path("configs/closure_v1/analysis_plan.yaml")
DEFAULT_ANALYSIS_SCHEMA = Path("configs/closure_v1/analysis_plan.schema.json")
DEFAULT_EXPERIMENTAL_MATRIX = Path("configs/closure_v1/experimental_matrix.yaml")

ANALYSIS_SCHEMA_VERSION = "closure_analysis_plan_v1_1"
EXPERIMENT_ID = "closure_v1"
PLAN_VERSION = "1.1"
REGISTRATION_CLASS = "internal_git_locked_pseudoprospective"
EXPECTED_SEEDS = [1729, 20260612, 20260613, 20260614, 314159]
EXPECTED_GROUP_KEY = ["source_id", "site_id"]
EXPECTED_DENOMINATORS = [
    "assigned_units",
    "intent_to_predict_origins",
    "metric_evaluable_origins",
    "shared_success_origins",
]
EXPECTED_PROTOCOL_COMPONENTS = [
    "docs/closure_v1/ANALYSIS_PLAN.md",
    "docs/closure_v1/PROTOCOL_AMENDMENT_V1_1.md",
    "configs/closure_v1/analysis_plan.yaml",
    "configs/closure_v1/analysis_plan.schema.json",
    "configs/closure_v1/surface_primary.yaml",
    "configs/closure_v1/surface_secondary.yaml",
    "configs/closure_v1/location_holdout.yaml",
    "configs/closure_v1/model_benchmark.yaml",
    "configs/closure_v1/experimental_matrix.yaml",
    "configs/counterfactual_planning_v1.yaml",
    "src/experiments/closure_contract.py",
    "src/experiments/lock_closure_protocol.py",
    "src/experiments/build_closure_holdout.py",
]
EXPECTED_SOURCE_ARTIFACTS = [
    "data/freeze/data_freeze_manifest_v0.json",
    "data/freeze/DATA_FREEZE.md",
    "data/panel/panel_monthly_v0.parquet",
    "data/targets/monthly_targets_model_v0.parquet",
    "data/targets/target_manifest_v0.json",
    "data/splits/monthly_model_splits_v0.parquet",
    "data/splits/split_manifest.json",
    "configs/site_resolution.yaml",
    "configs/variables.yaml",
    "configs/dvc_artifacts.yaml",
]
EXPECTED_E6_SCENARIOS = [
    "control",
    "mcar_10",
    "mcar_25",
    "mcar_50",
    "block_1m_10",
    "block_3m_10",
    "block_6m_25",
    "ablate_nutrients",
    "ablate_physchem",
    "ablate_light",
    "ablate_temperature",
    "combined_moderate",
    "combined_severe",
]
EXPECTED_E9_SCENARIOS = [
    "no_action",
    "tp_reduction_10",
    "tp_reduction_25",
    "tn_reduction_10",
    "tp_tn_reduction_10",
    "clarity_mild",
    "clarity_strong",
    "oxygen_support_05",
    "nutrient_clarity_mild",
    "nutrient_clarity_strong",
]
FORBIDDEN_DECISION_STRINGS = {
    "auto",
    "automatic",
    "decide_later",
    "null",
    "unknown",
    "placeholder",
    "tbd",
    "todo",
    "to_be_decided",
}
MONTH_PATTERN = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])$")
SUPPORTED_JSON_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "allOf",
        "oneOf",
        "not",
        "type",
        "const",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "prefixItems",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "pattern",
    }
)
JSON_SCHEMA_TYPES = frozenset({"null", "boolean", "object", "array", "number", "integer", "string"})


class ClosureContractError(ValueError):
    """Raised when a closure protocol violates a locked decision."""


class _JsonSchemaDefinitionError(ClosureContractError):
    """Raised when the bundled schema uses an invalid or unsupported construct."""


class _JsonSchemaInstanceError(ClosureContractError):
    """Raised when the analysis plan does not satisfy the bundled schema."""


def _schema_sequence(value: Any, *, keyword: str, schema_path: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.{keyword} must be an array")
    return list(value)


def _schema_child_path(schema_path: str, keyword: str, child: str | int | None = None) -> str:
    path = f"{schema_path}/{keyword}"
    return path if child is None else f"{path}/{child}"


def _instance_child_path(instance_path: str, child: str | int) -> str:
    if isinstance(child, int):
        return f"{instance_path}[{child}]"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", child):
        return f"{instance_path}.{child}"
    return f"{instance_path}[{child!r}]"


def _require_non_negative_schema_integer(value: Any, *, keyword: str, schema_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _JsonSchemaDefinitionError(
            f"JSON Schema {schema_path}.{keyword} must be a non-negative integer"
        )
    return value


def _assert_supported_json_schema(
    schema: Any,
    *,
    schema_path: str = "#",
    root_schema: Mapping[str, Any] | None = None,
) -> None:
    """Validate the closed JSON Schema subset before inspecting an instance."""
    if isinstance(schema, bool):
        return
    if not isinstance(schema, Mapping):
        raise _JsonSchemaDefinitionError(f"JSON Schema node {schema_path} must be an object or boolean")
    if root_schema is None:
        root_schema = schema

    unsupported = sorted(str(key) for key in schema if key not in SUPPORTED_JSON_SCHEMA_KEYWORDS)
    if unsupported:
        raise _JsonSchemaDefinitionError(
            f"Unsupported JSON Schema keyword(s) at {schema_path}: {unsupported}"
        )

    for annotation in ("$schema", "$id", "title", "description"):
        if annotation in schema and not isinstance(schema[annotation], str):
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.{annotation} must be a string")

    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or (reference != "#" and not reference.startswith("#/")):
            raise _JsonSchemaDefinitionError(
                f"JSON Schema {schema_path}.$ref must be a local JSON Pointer"
            )
        _resolve_local_schema_reference(reference, root_schema)

    if "type" in schema:
        raw_types = schema["type"]
        if isinstance(raw_types, str):
            type_names = [raw_types]
        else:
            type_names = _schema_sequence(raw_types, keyword="type", schema_path=schema_path)
        if not type_names or any(not isinstance(value, str) or value not in JSON_SCHEMA_TYPES for value in type_names):
            raise _JsonSchemaDefinitionError(
                f"JSON Schema {schema_path}.type contains an unsupported JSON type"
            )
        if len(set(type_names)) != len(type_names):
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.type contains duplicates")

    definitions = schema.get("$defs", {})
    if not isinstance(definitions, Mapping):
        raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.$defs must be an object")
    for name, child_schema in definitions.items():
        if not isinstance(name, str):
            raise _JsonSchemaDefinitionError(f"JSON Schema definition names at {schema_path} must be strings")
        _assert_supported_json_schema(
            child_schema,
            schema_path=_schema_child_path(schema_path, "$defs", name),
            root_schema=root_schema,
        )

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.properties must be an object")
    for name, child_schema in properties.items():
        if not isinstance(name, str):
            raise _JsonSchemaDefinitionError(f"JSON Schema property names at {schema_path} must be strings")
        _assert_supported_json_schema(
            child_schema,
            schema_path=_schema_child_path(schema_path, "properties", name),
            root_schema=root_schema,
        )

    for keyword in ("allOf", "oneOf", "prefixItems"):
        if keyword not in schema:
            continue
        children = _schema_sequence(schema[keyword], keyword=keyword, schema_path=schema_path)
        if not children:
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.{keyword} must not be empty")
        for index, child_schema in enumerate(children):
            _assert_supported_json_schema(
                child_schema,
                schema_path=_schema_child_path(schema_path, keyword, index),
                root_schema=root_schema,
            )

    for keyword in ("not", "items", "additionalProperties"):
        if keyword in schema:
            _assert_supported_json_schema(
                schema[keyword],
                schema_path=_schema_child_path(schema_path, keyword),
                root_schema=root_schema,
            )

    if "required" in schema:
        required = _schema_sequence(schema["required"], keyword="required", schema_path=schema_path)
        if any(not isinstance(value, str) for value in required):
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.required must contain strings")
        if len(set(required)) != len(required):
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.required contains duplicates")

    if "enum" in schema:
        enum = _schema_sequence(schema["enum"], keyword="enum", schema_path=schema_path)
        if not enum:
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.enum must not be empty")
        for left_index, left in enumerate(enum):
            if any(_json_equal(left, right) for right in enum[left_index + 1 :]):
                raise _JsonSchemaDefinitionError(
                    f"JSON Schema {schema_path}.enum contains duplicate JSON values"
                )

    minimum_items = None
    maximum_items = None
    if "minItems" in schema:
        minimum_items = _require_non_negative_schema_integer(
            schema["minItems"], keyword="minItems", schema_path=schema_path
        )
    if "maxItems" in schema:
        maximum_items = _require_non_negative_schema_integer(
            schema["maxItems"], keyword="maxItems", schema_path=schema_path
        )
    if minimum_items is not None and maximum_items is not None and minimum_items > maximum_items:
        raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path} has minItems greater than maxItems")

    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.uniqueItems must be boolean")
    if "minLength" in schema:
        _require_non_negative_schema_integer(
            schema["minLength"], keyword="minLength", schema_path=schema_path
        )
    if "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str):
            raise _JsonSchemaDefinitionError(f"JSON Schema {schema_path}.pattern must be a string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise _JsonSchemaDefinitionError(
                f"JSON Schema {schema_path}.pattern is not a valid regular expression"
            ) from exc


def _decode_json_pointer_token(token: str, *, reference: str) -> str:
    if re.search(r"~(?![01])", token):
        raise _JsonSchemaDefinitionError(f"JSON Schema $ref contains an invalid escape: {reference!r}")
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_local_schema_reference(reference: str, root_schema: Mapping[str, Any]) -> Any:
    if reference == "#":
        return root_schema
    if not reference.startswith("#/"):
        raise _JsonSchemaDefinitionError(f"Only local JSON Schema references are supported: {reference!r}")
    current: Any = root_schema
    for raw_token in reference[2:].split("/"):
        token = _decode_json_pointer_token(raw_token, reference=reference)
        if isinstance(current, Mapping):
            if token not in current:
                raise _JsonSchemaDefinitionError(f"JSON Schema $ref does not resolve: {reference!r}")
            current = current[token]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            if not token.isdigit() or int(token) >= len(current):
                raise _JsonSchemaDefinitionError(f"JSON Schema $ref does not resolve: {reference!r}")
            current = current[int(token)]
        else:
            raise _JsonSchemaDefinitionError(f"JSON Schema $ref does not resolve: {reference!r}")
    if not isinstance(current, (Mapping, bool)):
        raise _JsonSchemaDefinitionError(f"JSON Schema $ref target is not a schema: {reference!r}")
    return current


def _json_equal(left: Any, right: Any) -> bool:
    """Compare values with JSON Schema equality rather than Python bool/int equality."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and left == right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item) for left_item, right_item in zip(left, right, strict=True)
        )
    return type(left) is type(right) and left == right


def _json_type_matches(instance: Any, expected_type: str) -> bool:
    if expected_type == "null":
        return instance is None
    if expected_type == "boolean":
        return isinstance(instance, bool)
    if expected_type == "object":
        return isinstance(instance, Mapping) and all(isinstance(key, str) for key in instance)
    if expected_type == "array":
        return isinstance(instance, list)
    if expected_type == "number":
        return (
            not isinstance(instance, bool)
            and isinstance(instance, (int, float))
            and math.isfinite(float(instance))
        )
    if expected_type == "integer":
        return not isinstance(instance, bool) and isinstance(instance, int)
    if expected_type == "string":
        return isinstance(instance, str)
    raise _JsonSchemaDefinitionError(f"Unsupported JSON Schema type: {expected_type!r}")


def _validate_json_schema_node(
    instance: Any,
    schema: Any,
    *,
    root_schema: Mapping[str, Any],
    instance_path: str,
    schema_path: str,
) -> None:
    if schema is True:
        return
    if schema is False:
        raise _JsonSchemaInstanceError(f"JSON Schema rejected {instance_path} via {schema_path}")
    if not isinstance(schema, Mapping):
        raise _JsonSchemaDefinitionError(f"JSON Schema node {schema_path} must be an object or boolean")

    if "$ref" in schema:
        reference = str(schema["$ref"])
        referenced_schema = _resolve_local_schema_reference(reference, root_schema)
        _validate_json_schema_node(
            instance,
            referenced_schema,
            root_schema=root_schema,
            instance_path=instance_path,
            schema_path=reference,
        )

    for index, child_schema in enumerate(schema.get("allOf", [])):
        _validate_json_schema_node(
            instance,
            child_schema,
            root_schema=root_schema,
            instance_path=instance_path,
            schema_path=_schema_child_path(schema_path, "allOf", index),
        )

    if "oneOf" in schema:
        matches = 0
        for index, child_schema in enumerate(schema["oneOf"]):
            try:
                _validate_json_schema_node(
                    instance,
                    child_schema,
                    root_schema=root_schema,
                    instance_path=instance_path,
                    schema_path=_schema_child_path(schema_path, "oneOf", index),
                )
            except _JsonSchemaInstanceError:
                continue
            matches += 1
        if matches != 1:
            raise _JsonSchemaInstanceError(
                f"JSON Schema oneOf at {schema_path} matched {matches} branches for {instance_path}"
            )

    if "not" in schema:
        try:
            _validate_json_schema_node(
                instance,
                schema["not"],
                root_schema=root_schema,
                instance_path=instance_path,
                schema_path=_schema_child_path(schema_path, "not"),
            )
        except _JsonSchemaInstanceError:
            pass
        else:
            raise _JsonSchemaInstanceError(f"JSON Schema not at {schema_path} matched {instance_path}")

    if "type" in schema:
        raw_types = schema["type"]
        expected_types = [raw_types] if isinstance(raw_types, str) else list(raw_types)
        if not any(_json_type_matches(instance, expected_type) for expected_type in expected_types):
            raise _JsonSchemaInstanceError(
                f"JSON Schema type at {schema_path} rejected {instance_path}; expected {expected_types}"
            )

    if "const" in schema and not _json_equal(instance, schema["const"]):
        raise _JsonSchemaInstanceError(
            f"JSON Schema const at {schema_path} rejected {instance_path}: {instance!r}"
        )
    if "enum" in schema and not any(_json_equal(instance, candidate) for candidate in schema["enum"]):
        raise _JsonSchemaInstanceError(f"JSON Schema enum at {schema_path} rejected {instance_path}")

    if isinstance(instance, Mapping):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise _JsonSchemaInstanceError(
                f"JSON Schema required at {schema_path} found missing properties at {instance_path}: {missing}"
            )
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in instance:
                _validate_json_schema_node(
                    instance[key],
                    child_schema,
                    root_schema=root_schema,
                    instance_path=_instance_child_path(instance_path, key),
                    schema_path=_schema_child_path(schema_path, "properties", key),
                )
        additional = schema.get("additionalProperties", True)
        for key in instance.keys() - properties.keys():
            child_path = _instance_child_path(instance_path, str(key))
            if additional is False:
                raise _JsonSchemaInstanceError(
                    f"JSON Schema additionalProperties at {schema_path} rejected {child_path}"
                )
            if additional is not True:
                _validate_json_schema_node(
                    instance[key],
                    additional,
                    root_schema=root_schema,
                    instance_path=child_path,
                    schema_path=_schema_child_path(schema_path, "additionalProperties"),
                )

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        maximum_items = schema.get("maxItems")
        if minimum_items is not None and len(instance) < minimum_items:
            raise _JsonSchemaInstanceError(
                f"JSON Schema minItems at {schema_path} rejected {instance_path}"
            )
        if maximum_items is not None and len(instance) > maximum_items:
            raise _JsonSchemaInstanceError(
                f"JSON Schema maxItems at {schema_path} rejected {instance_path}"
            )
        if schema.get("uniqueItems") is True:
            for left_index, left in enumerate(instance):
                for right_index in range(left_index + 1, len(instance)):
                    if _json_equal(left, instance[right_index]):
                        raise _JsonSchemaInstanceError(
                            f"JSON Schema uniqueItems at {schema_path} rejected duplicate indexes "
                            f"{left_index} and {right_index} at {instance_path}"
                        )
        prefix_items = schema.get("prefixItems", [])
        for index, child_schema in enumerate(prefix_items[: len(instance)]):
            _validate_json_schema_node(
                instance[index],
                child_schema,
                root_schema=root_schema,
                instance_path=_instance_child_path(instance_path, index),
                schema_path=_schema_child_path(schema_path, "prefixItems", index),
            )
        items_schema = schema.get("items", True)
        for index in range(len(prefix_items), len(instance)):
            _validate_json_schema_node(
                instance[index],
                items_schema,
                root_schema=root_schema,
                instance_path=_instance_child_path(instance_path, index),
                schema_path=_schema_child_path(schema_path, "items"),
            )

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(instance) < minimum_length:
            raise _JsonSchemaInstanceError(
                f"JSON Schema minLength at {schema_path} rejected {instance_path}"
            )
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            raise _JsonSchemaInstanceError(
                f"JSON Schema pattern at {schema_path} rejected {instance_path}: {instance!r}"
            )


def validate_json_schema(instance: Any, schema: Mapping[str, Any], *, instance_path: str = "$") -> None:
    """Validate an instance against the closed Draft 2020-12 subset used here."""
    _assert_supported_json_schema(schema)
    _validate_json_schema_node(
        instance,
        schema,
        root_schema=schema,
        instance_path=instance_path,
        schema_path="#",
    )


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repository-relative path without accepting external files."""
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ClosureContractError(f"Path is outside the repository: {path}") from exc
    return resolved


def repository_relative(path: str | Path) -> str:
    """Return a normalized path relative to the repository root."""
    return resolve_repo_path(path).relative_to(PROJECT_ROOT.resolve()).as_posix()


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without materializing it in memory."""
    resolved = resolve_repo_path(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: str | Path, *, role: str) -> dict[str, Any]:
    """Create a stable file record for a lock manifest."""
    resolved = resolve_repo_path(path)
    if not resolved.is_file():
        raise ClosureContractError(f"Required lock input is not a file: {repository_relative(resolved)}")
    return {
        "path": repository_relative(resolved),
        "role": role,
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a YAML document and require a mapping at its root."""
    resolved = resolve_repo_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ClosureContractError(f"Expected a YAML mapping in {repository_relative(resolved)}")
    return payload


def load_json_mapping(path: str | Path) -> dict[str, Any]:
    """Load a JSON document and require a mapping at its root."""
    resolved = resolve_repo_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ClosureContractError(f"Expected a JSON object in {repository_relative(resolved)}")
    return payload


def _mapping(payload: Mapping[str, Any], key: str, *, context: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosureContractError(f"{context}.{key} must be a mapping")
    return value


def _sequence(payload: Mapping[str, Any], key: str, *, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ClosureContractError(f"{context}.{key} must be a sequence")
    return list(value)


def _require_equal(payload: Mapping[str, Any], key: str, expected: Any, *, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise ClosureContractError(f"{context}.{key} must be {expected!r}; found {actual!r}")


def _period_ordinal(value: Any, *, field: str) -> int:
    if not isinstance(value, str):
        raise ClosureContractError(f"{field} must be a YYYY-MM string")
    match = MONTH_PATTERN.fullmatch(value)
    if match is None:
        raise ClosureContractError(f"{field} must be a valid YYYY-MM string; found {value!r}")
    return int(match.group("year")) * 12 + int(match.group("month")) - 1


def _walk_decisions(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if value is None:
        findings.append(f"{path}=null")
    elif isinstance(value, str) and value.strip().lower() in FORBIDDEN_DECISION_STRINGS:
        findings.append(f"{path}={value!r}")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            findings.extend(_walk_decisions(item, f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            findings.extend(_walk_decisions(item, f"{path}[{index}]"))
    return findings


def _component_paths(locking: Mapping[str, Any]) -> list[str]:
    values = _sequence(locking, "protocol_components", context="locking")
    paths: list[str] = []
    for index, value in enumerate(values):
        if isinstance(value, str):
            paths.append(value)
            continue
        if isinstance(value, Mapping) and isinstance(value.get("path"), str):
            paths.append(str(value["path"]))
            continue
        raise ClosureContractError(f"locking.protocol_components[{index}] must contain a path")
    return paths


def _validate_time_roles(time_roles: Mapping[str, Any]) -> None:
    train = _mapping(time_roles, "training", context="time_roles")
    selection = _mapping(time_roles, "model_selection", context="time_roles")
    calibration = _mapping(time_roles, "calibration_threshold", context="time_roles")
    evaluation = _mapping(time_roles, "locked_evaluation", context="time_roles")

    _require_equal(train, "target_end", "2018-12", context="time_roles.training")
    _require_equal(selection, "origin_start", "2019-01", context="time_roles.model_selection")
    _require_equal(selection, "target_end", "2020-12", context="time_roles.model_selection")
    _require_equal(calibration, "origin_start", "2021-01", context="time_roles.calibration_threshold")
    _require_equal(calibration, "target_end", "2021-12", context="time_roles.calibration_threshold")
    _require_equal(evaluation, "target_start", "2022-01", context="time_roles.locked_evaluation")

    train_end = _period_ordinal(train["target_end"], field="time_roles.training.target_end")
    selection_start = _period_ordinal(selection["origin_start"], field="time_roles.model_selection.origin_start")
    selection_end = _period_ordinal(selection["target_end"], field="time_roles.model_selection.target_end")
    calibration_start = _period_ordinal(
        calibration["origin_start"], field="time_roles.calibration_threshold.origin_start"
    )
    calibration_end = _period_ordinal(
        calibration["target_end"], field="time_roles.calibration_threshold.target_end"
    )
    evaluation_start = _period_ordinal(evaluation["target_start"], field="time_roles.locked_evaluation.target_start")
    if not train_end < selection_start <= selection_end < calibration_start <= calibration_end < evaluation_start:
        raise ClosureContractError("time_roles are overlapping or out of order")

    for role_name, role in (
        ("training", train),
        ("model_selection", selection),
        ("calibration_threshold", calibration),
        ("locked_evaluation", evaluation),
    ):
        _require_equal(role, "both_origin_and_target_within_role", True, context=f"time_roles.{role_name}")


def _validate_holdout(holdout: Mapping[str, Any]) -> None:
    _require_equal(holdout, "unit_type", "wqp_monitoring_location", context="holdout")
    _require_equal(holdout, "group_key", EXPECTED_GROUP_KEY, context="holdout")
    _require_equal(holdout, "source_ids", ["wqp"], context="holdout")
    _require_equal(holdout, "information_cutoff", "2021-12", context="holdout")
    _require_equal(holdout, "last_eligible_origin", "2021-09", context="holdout")
    _require_equal(holdout, "waterbody_claim_authorized", False, context="holdout")
    _require_equal(holdout, "external_validation_claim_authorized", False, context="holdout")
    _require_equal(holdout, "future_outcomes_used_for_assignment", False, context="holdout")
    _require_equal(holdout, "replacement_after_assignment", False, context="holdout")


def _validate_surface(path: str | Path, *, primary: bool) -> dict[str, Any]:
    surface = load_yaml_mapping(path)
    if primary:
        _require_equal(surface, "surface_id", "closure_v1_wqp_adaptive_no_current_chla", context="primary_surface")
        _require_equal(surface, "source_ids", ["wqp"], context="primary_surface")
        _require_equal(surface, "future_chla_target_only", True, context="primary_surface")
        _require_equal(surface, "history_length_months", 12, context="primary_surface")
        _require_equal(surface, "horizons_months", [1, 2, 3], context="primary_surface")
        chlorophyll = _mapping(surface, "chlorophyll_contract", context="primary_surface")
        _require_equal(chlorophyll, "observed_chla_at_any_input_lag", "forbidden", context="primary_surface.chlorophyll_contract")
        _require_equal(chlorophyll, "current_chla_in_inputs", False, context="primary_surface.chlorophyll_contract")
        _require_equal(chlorophyll, "lagged_chla_in_inputs", False, context="primary_surface.chlorophyll_contract")
        _require_equal(chlorophyll, "future_chla_target_only", True, context="primary_surface.chlorophyll_contract")
        forbidden = [str(item).lower() for item in _sequence(surface, "forbidden_predictors", context="primary_surface")]
        required_forbidden = {"risk_chla", "chl", "chl_prev", "x_irc1"}
        missing_forbidden = sorted(required_forbidden.difference(forbidden))
        if missing_forbidden:
            raise ClosureContractError(
                "primary_surface.forbidden_predictors is missing strict Chl-a channels: "
                f"{missing_forbidden}"
            )
    else:
        _require_equal(surface, "scientific_role", "monitoring_nowcasting_diagnostic", context="secondary_surface")
        claim_policy = _mapping(surface, "claim_policy", context="secondary_surface")
        _require_equal(
            claim_policy,
            "eligible_for_primary_early_warning_claim",
            False,
            context="secondary_surface.claim_policy",
        )
    return surface


def _validate_location_holdout(path: str | Path) -> dict[str, Any]:
    config = load_yaml_mapping(path)
    _require_equal(config, "schema_version", "closure_location_holdout_v1_1", context="location_holdout")
    inputs = _mapping(config, "inputs", context="location_holdout")
    _require_equal(
        inputs,
        "target_manifest",
        "data/targets/target_manifest_v0.json",
        context="location_holdout.inputs",
    )
    unit = _mapping(config, "unit", context="location_holdout")
    _require_equal(unit, "unit_type", "wqp_monitoring_location", context="location_holdout.unit")
    _require_equal(unit, "group_key", EXPECTED_GROUP_KEY, context="location_holdout.unit")
    _require_equal(unit, "source_ids", ["wqp"], context="location_holdout.unit")
    _require_equal(unit, "waterbody_claim_authorized", False, context="location_holdout.unit")
    _require_equal(unit, "external_validation_claim_authorized", False, context="location_holdout.unit")

    boundary = _mapping(config, "information_boundary", context="location_holdout")
    _require_equal(boundary, "information_cutoff", "2021-12", context="location_holdout.information_boundary")
    _require_equal(boundary, "last_eligible_origin", "2021-09", context="location_holdout.information_boundary")
    _require_equal(
        boundary,
        "post_cutoff_target_values_for_assignment",
        "forbidden",
        context="location_holdout.information_boundary",
    )
    _require_equal(
        boundary,
        "post_cutoff_target_availability_for_assignment",
        "forbidden",
        context="location_holdout.information_boundary",
    )
    _require_equal(
        boundary,
        "parquet_read_api_filter_required",
        "target_year_month_not_after_2021_12",
        context="location_holdout.information_boundary",
    )
    _require_equal(
        boundary,
        "post_cutoff_target_rows_materialized_to_selector_logic",
        False,
        context="location_holdout.information_boundary",
    )
    _require_equal(
        boundary,
        "storage_engine_internal_page_decoding_audited_or_claimed",
        False,
        context="location_holdout.information_boundary",
    )

    projection = _mapping(config, "selection_projection", context="location_holdout")
    _require_equal(
        projection,
        "permitted_historical_outcome_columns",
        ["bloom_h"],
        context="location_holdout.selection_projection",
    )
    forbidden_inputs = [str(value).lower() for value in _sequence(
        projection, "forbidden_chla_input_columns", context="location_holdout.selection_projection"
    )]
    if "risk_chla" not in forbidden_inputs or not any("chlorophyll" in value for value in forbidden_inputs):
        raise ClosureContractError("location_holdout must explicitly forbid Chl-a and risk_chla coverage inputs")
    forbidden_paths = _sequence(projection, "forbidden_input_paths", context="location_holdout.selection_projection")
    if "data/interim/site_registry.parquet" not in forbidden_paths:
        raise ClosureContractError("location_holdout must forbid the future-informed site registry during selection")

    eligibility = _mapping(config, "eligibility", context="location_holdout")
    _require_equal(eligibility, "history_length_months", 12, context="location_holdout.eligibility")
    _require_equal(eligibility, "complete_horizons_required", [1, 2, 3], context="location_holdout.eligibility")
    _require_equal(eligibility, "last_eligible_origin", "2021-09", context="location_holdout.eligibility")
    _require_equal(eligibility, "all_eligibility_targets_not_after", "2021-12", context="location_holdout.eligibility")
    _require_equal(eligibility, "post_cutoff_outcome_support_required", False, context="location_holdout.eligibility")

    coverage = _mapping(config, "precursor_coverage", context="location_holdout")
    _require_equal(
        coverage,
        "covered_month_rule",
        "nutrient_and_temperature_and_either_light_proxy_or_physicochemical",
        context="location_holdout.precursor_coverage",
    )

    sampling = _mapping(config, "sampling", context="location_holdout")
    _require_equal(sampling, "selection_fraction", 0.20, context="location_holdout.sampling")
    _require_equal(sampling, "seed", 20260802, context="location_holdout.sampling")
    _require_equal(
        sampling,
        "global_target_count_rule",
        "floor_eligible_count_times_fraction",
        context="location_holdout.sampling",
    )
    _require_equal(sampling, "row_order_independent", True, context="location_holdout.sampling")
    _require_equal(sampling, "sampling_without_replacement", True, context="location_holdout.sampling")

    assignment = _mapping(config, "assignment", context="location_holdout")
    _require_equal(assignment, "selected_role", "internal_holdout", context="location_holdout.assignment")
    _require_equal(assignment, "nonselected_role", "development", context="location_holdout.assignment")
    _require_equal(assignment, "all_rows_of_group_share_assignment", True, context="location_holdout.assignment")
    _require_equal(assignment, "immutable_after_creation", True, context="location_holdout.assignment")
    _require_equal(
        assignment,
        "replacement_for_missing_future_outcome",
        "forbidden",
        context="location_holdout.assignment",
    )

    zero_holdout = _mapping(config, "zero_holdout_policy", context="location_holdout")
    _require_equal(zero_holdout, "action", "fail_gate", context="location_holdout.zero_holdout_policy")
    _require_equal(
        zero_holdout,
        "minimum_holdout_locations",
        1,
        context="location_holdout.zero_holdout_policy",
    )
    _require_equal(
        zero_holdout,
        "permit_empty_assignment_artifact",
        False,
        context="location_holdout.zero_holdout_policy",
    )

    outputs = _mapping(config, "outputs", context="location_holdout")
    expected_output_paths = [
        "data/closure_v1/closure_holdout_assignment.csv",
        "reports/closure_v1/00_protocol/holdout_summary_pre_cutoff.csv",
        "reports/closure_v1/00_protocol/cohort_flow_preoutcome.csv",
        "reports/closure_v1/00_protocol/holdout_leakage_audit.json",
        "reports/closure_v1/00_protocol/holdout_manifest.json",
    ]
    _require_equal(outputs, "expected_output_count", 5, context="location_holdout.outputs")
    _require_equal(outputs, "write_order", expected_output_paths, context="location_holdout.outputs")
    _require_equal(outputs, "manifest_written_last", True, context="location_holdout.outputs")
    _require_equal(outputs, "output_contains_post_cutoff_outcome_values", False, context="location_holdout.outputs")
    _require_equal(outputs, "output_contains_post_cutoff_outcome_availability", False, context="location_holdout.outputs")
    return config


def _validate_model_benchmark(path: str | Path) -> dict[str, Any]:
    config = load_yaml_mapping(path)
    _require_equal(config, "schema_version", "closure_model_benchmark_v1_1", context="model_benchmark")
    _require_equal(config, "seeds", EXPECTED_SEEDS, context="model_benchmark")
    common = _mapping(config, "common_contract", context="model_benchmark")
    _require_equal(common, "strict_no_observed_chla_at_any_input_lag", True, context="model_benchmark.common_contract")
    _require_equal(common, "holdout_locations_excluded_from_all_fit_stages", True, context="model_benchmark.common_contract")
    models = _mapping(config, "models", context="model_benchmark")
    for model_id in ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0"):
        _mapping(models, model_id, context="model_benchmark.models")
    b1 = _mapping(models, "B1", context="model_benchmark.models")
    b1_forbidden = [str(value).lower() for value in _sequence(
        b1, "forbidden_persistence_inputs", context="model_benchmark.models.B1"
    )]
    if "risk_chla" not in b1_forbidden:
        raise ClosureContractError("model_benchmark B1 must forbid persistence of observed risk_chla")
    b0 = _mapping(models, "B0", context="model_benchmark.models")
    _require_equal(b0, "fit_role", "training", context="model_benchmark.models.B0")
    _require_equal(b0, "calibration_applied", False, context="model_benchmark.models.B0")
    _require_equal(b0, "evaluation_refit", "forbidden", context="model_benchmark.models.B0")
    p1 = _mapping(models, "P1", context="model_benchmark.models")
    _require_equal(p1, "canonical_grud", False, context="model_benchmark.models.P1")
    m0 = _mapping(models, "M0", context="model_benchmark.models")
    _require_equal(m0, "closure_eligibility", "blocked_pending_strict_adapter", context="model_benchmark.models.M0")
    return config


def _scenario_ids(section: Mapping[str, Any], *, context: str) -> list[str]:
    scenarios = _sequence(section, "scenarios", context=context)
    identifiers: list[str] = []
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, Mapping) or not isinstance(scenario.get("scenario_id"), str):
            raise ClosureContractError(f"{context}.scenarios[{index}] must contain scenario_id")
        identifiers.append(str(scenario["scenario_id"]))
    if len(set(identifiers)) != len(identifiers):
        raise ClosureContractError(f"{context}.scenarios contains duplicate scenario_id values")
    return identifiers


def _validate_experimental_matrix(path: str | Path) -> dict[str, Any]:
    matrix = load_yaml_mapping(path)
    _require_equal(
        matrix,
        "schema_version",
        "closure_experimental_matrix_v1_1",
        context="experimental_matrix",
    )
    _require_equal(matrix, "experiment_id", EXPERIMENT_ID, context="experimental_matrix")
    _require_equal(matrix, "plan_version", PLAN_VERSION, context="experimental_matrix")
    _require_equal(matrix, "status", "ready_to_lock", context="experimental_matrix")

    shared = _mapping(matrix, "shared_contract", context="experimental_matrix")
    _require_equal(shared, "source_ids", ["wqp"], context="experimental_matrix.shared_contract")
    _require_equal(
        shared,
        "strict_no_observed_chla_at_any_input_lag",
        True,
        context="experimental_matrix.shared_contract",
    )

    degradation = _mapping(matrix, "e6_matched_degradation", context="experimental_matrix")
    _require_equal(degradation, "status", "required", context="experimental_matrix.e6")
    _require_equal(degradation, "comparison", "M0_vs_P1", context="experimental_matrix.e6")
    _require_equal(degradation, "scenario_count", 13, context="experimental_matrix.e6")
    _require_equal(degradation, "degraded_scenario_count", 12, context="experimental_matrix.e6")
    _require_equal(degradation, "stochastic_seeds", EXPECTED_SEEDS, context="experimental_matrix.e6")
    _require_equal(
        degradation,
        "replicate_contract",
        {
            "ordered_seed_slots": EXPECTED_SEEDS,
            "P1_model_seed_by_slot": "same_as_ordered_seed_slot",
            "M0_model_seed_policy": (
                "deterministic_prediction_with_technical_seed_1729_reused_in_all_5_slots"
            ),
            "stochastic_degradation_seed_by_slot": "same_as_ordered_seed_slot",
            "stochastic_model_degradation_pairing": "one_to_one_by_ordered_seed_slot",
            "model_seed_by_degradation_seed_cross_product": "forbidden",
            "control_and_deterministic_degradation_seed_policy": (
                "technical_seed_1729_same_mask_in_all_5_slots"
            ),
            "exact_row_shared_success_requires_all_slots_for_both_models": True,
            "missing_slot_policy": (
                "exclude_exact_row_from_family_B_shared_success_and_report_failure_on_"
                "intent_to_predict"
            ),
            "endpoint_aggregation_order": [
                "resample_holdout_group_ids_with_all_exact_rows",
                "compute_each_model_endpoint_separately_within_each_of_5_seed_slots",
                "compute_M0_minus_P1_endpoint_delta_within_seed_slot",
                "average_the_5_seed_slot_deltas_with_equal_weight_within_bootstrap_replicate",
                "derive_one_two_sided_p_value_for_each_scenario_horizon_endpoint",
            ],
            "seeds_are_inference_units": False,
            "p_value_count_formula": "13_scenarios_times_3_horizons_times_2_endpoints",
        },
        context="experimental_matrix.e6",
    )
    degradation_ids = _scenario_ids(degradation, context="experimental_matrix.e6")
    if degradation_ids != EXPECTED_E6_SCENARIOS:
        raise ClosureContractError(
            "experimental_matrix.e6 scenarios must equal the locked ordered scenario universe"
        )
    degradation_by_id = {
        str(item["scenario_id"]): item
        for item in _sequence(degradation, "scenarios", context="experimental_matrix.e6")
        if isinstance(item, Mapping)
    }
    _require_equal(
        degradation_by_id["combined_severe"],
        "components",
        ["mcar_50", "block_6m_25", "ablate_nutrients"],
        context="experimental_matrix.e6.combined_severe",
    )
    expected_ablations = {
        "ablate_nutrients": {
            "raw_variables": ["mean_TP_ugL", "mean_TN_ugL"],
            "minimum_derived_variables_invalidated": ["TN_TP_ratio", "log_TP", "log_TN"],
        },
        "ablate_physchem": {
            "raw_variables": ["mean_DO_mgL", "mean_pH"],
            "minimum_derived_variables_invalidated": [],
        },
        "ablate_light": {
            "raw_variables": ["mean_turbidity_NTU", "mean_secchi_depth_m"],
            "minimum_derived_variables_invalidated": [],
        },
        "ablate_temperature": {
            "raw_variables": ["mean_temperature_C"],
            "minimum_derived_variables_invalidated": [],
        },
    }
    for scenario_id, expected in expected_ablations.items():
        scenario = degradation_by_id[scenario_id]
        _require_equal(
            scenario,
            "family",
            "deterministic_ablation",
            context=f"experimental_matrix.e6.{scenario_id}",
        )
        _require_equal(
            scenario,
            "stochastic",
            False,
            context=f"experimental_matrix.e6.{scenario_id}",
        )
        _require_equal(
            scenario,
            "operation",
            "set_raw_missing_and_invalidate_derived_lineage",
            context=f"experimental_matrix.e6.{scenario_id}",
        )
        for field, value in expected.items():
            _require_equal(
                scenario,
                field,
                value,
                context=f"experimental_matrix.e6.{scenario_id}",
            )
    mask_contract = _mapping(degradation, "mask_contract", context="experimental_matrix.e6")
    _require_equal(mask_contract, "digest_algorithm", "sha256", context="experimental_matrix.e6.mask")
    _require_equal(
        mask_contract,
        "digest_payload_serialization",
        "canonical_json_array_utf8",
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "digest_payload_json_settings",
        {
            "ensure_ascii": True,
            "separators": ["comma", "colon"],
            "whitespace": "forbidden",
            "unicode_normalization_before_serialization": "NFC",
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "digest_payload_types_in_order",
        [
            "json_string_literal_closure_v1",
            "json_string_literal_E6",
            "json_string_scenario_id",
            "json_integer_degradation_seed",
            "json_string_source_id",
            "json_string_site_id",
            "json_string_canonical_year_month",
            "json_string_raw_variable",
        ],
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "mcar_digest_fields_in_order",
        [
            "closure_v1",
            "E6",
            "scenario_id",
            "degradation_seed_base10",
            "source_id",
            "site_id",
            "year_month_yyyy_mm",
            "raw_variable",
        ],
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "block_start_digest_fields_in_order",
        [
            "closure_v1",
            "E6",
            "scenario_id",
            "degradation_seed_base10",
            "source_id",
            "site_id",
            "block_start_year_month_yyyy_mm",
            "raw_variable",
        ],
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "digest_to_unit_interval",
        {
            "bytes": "first_8",
            "byte_order": "big_endian_unsigned",
            "divisor": 18446744073709551616,
            "range": "half_open_0_1",
        },
        context="experimental_matrix.e6.mask",
    )
    expected_serialization_vectors = [
        {
            "rule": "mcar",
            "canonical_payload": (
                '["closure_v1","E6","mcar_25",1729,"wqp","site-001",'
                '"2021-01","mean_TP_ugL"]'
            ),
            "expected_sha256": (
                "df3b08f858cf4b76006eb8eeab4d9819f52901d40783cd8eb4cf354bce9f6714"
            ),
        },
        {
            "rule": "temporal_block_start",
            "canonical_payload": (
                '["closure_v1","E6","block_3m_10",1729,"wqp","site-001",'
                '"2021-01","mean_TP_ugL"]'
            ),
            "expected_sha256": (
                "1c56b8c4b5fd971abb3d2f30312c04ab9b7d8e13f5f73179dded2df2967d532e"
            ),
        },
    ]
    _require_equal(
        mask_contract,
        "serialization_test_vectors",
        expected_serialization_vectors,
        context="experimental_matrix.e6.mask",
    )
    for vector in expected_serialization_vectors:
        payload = str(vector["canonical_payload"])
        if json.dumps(json.loads(payload), ensure_ascii=True, separators=(",", ":")) != payload:
            raise ClosureContractError("experimental_matrix.e6 mask test vector is not canonical JSON")
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != vector["expected_sha256"]:
            raise ClosureContractError("experimental_matrix.e6 mask test vector SHA-256 mismatch")
    _require_equal(
        mask_contract,
        "unique_raw_cell_key",
        ["source_id", "site_id", "year_month", "raw_variable"],
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "eligible_raw_predictor_columns",
        [
            "mean_TP_ugL",
            "mean_TN_ugL",
            "mean_DO_mgL",
            "mean_pH",
            "mean_turbidity_NTU",
            "mean_secchi_depth_m",
            "mean_temperature_C",
        ],
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "existing_missing_cells_enter_mask_denominator",
        False,
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "repeated_appearances_of_a_raw_cell_share_one_mask_value",
        True,
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "mcar_rule",
        {
            "uniform_rule": "first_8_digest_bytes_as_uint64_divided_by_2_pow_64",
            "mask_if": "uniform_strictly_less_than_dropout_fraction",
            "exact_fraction_forced": False,
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "temporal_block_rule",
        {
            "series_key": ["source_id", "site_id", "raw_variable"],
            "eligible_cell_count": "finite_observed_unique_raw_cells",
            "candidate_starts": "every_calendar_month_allowing_a_full_block_within_series_span",
            "candidate_order": "digest_ascending_then_start_month_ascending",
            "target_block_count_scope": "independently_within_each_series_key",
            "target_block_count_formula": (
                "max_1_round_half_up_fraction_times_eligible_cells_divided_by_block_length"
            ),
            "round_half_up_definition": "floor_x_plus_0_5_for_nonnegative_x",
            "target_block_count_zero_when_no_eligible_cells_or_no_full_block_candidate": True,
            "block_interval": "start_through_start_plus_length_minus_1_calendar_months",
            "overlap_within_series": "forbidden",
            "overlap_resolution": "skip_candidate_and_continue_digest_order",
            "stop_rule": "target_block_count_selected_or_candidates_exhausted",
            "masked_cells": "eligible_observed_cells_whose_month_is_inside_selected_blocks",
            "partial_boundary_blocks": "forbidden",
            "exact_fraction_forced": False,
            "no_resampling_or_fraction_tuning": True,
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "combined_rule",
        {
            "operation": "union_named_component_masks_for_same_seed",
            "fresh_digest_for_combined_scenario": False,
            "deterministic_ablation_applied_after_random_mask_union": True,
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "deterministic_ablation_rule",
        {
            "raw_operation": "set_declared_raw_predictor_cells_to_missing",
            "application_stage": "after_random_mask_union_before_model_specific_transforms",
            "pre_degradation_derived_values_reused": False,
            "derived_lineage_policy": (
                "invalidate_every_direct_or_transitive_derived_feature_of_ablated_raw_"
                "variables_before_model_specific_imputation"
            ),
            "listed_derived_variables_are_minimum_required_lineage_audit": True,
            "unlisted_dependent_feature_policy": "fail_lineage_audit",
            "target_columns_affected": False,
            "assignment_columns_affected": False,
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "realized_fraction_reporting",
        {
            "denominator": "eligible_observed_unique_raw_cells",
            "required_dimensions": ["scenario_id", "degradation_seed", "raw_variable"],
            "planned_fraction_and_realized_fraction_both_required": True,
        },
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "generated_once_before_model_specific_transforms",
        True,
        context="experimental_matrix.e6.mask",
    )
    _require_equal(
        mask_contract,
        "shared_exactly_between_M0_and_P1",
        True,
        context="experimental_matrix.e6.mask",
    )
    family_b = _mapping(degradation, "family_B_universe", context="experimental_matrix.e6")
    _require_equal(family_b, "scenario_ids", EXPECTED_E6_SCENARIOS, context="experimental_matrix.e6.family_B")
    _require_equal(family_b, "horizons_months", [1, 2, 3], context="experimental_matrix.e6.family_B")
    _require_equal(family_b, "endpoints", ["pr_auc", "brier"], context="experimental_matrix.e6.family_B")
    _require_equal(family_b, "p_value_universe_size", 78, context="experimental_matrix.e6.family_B")

    anfis = _mapping(matrix, "e7_anfis_ablation", context="experimental_matrix")
    _require_equal(anfis, "status", "required", context="experimental_matrix.e7")
    _require_equal(
        anfis,
        "training_rows_per_module",
        [4096, 16384, 65536],
        context="experimental_matrix.e7",
    )
    _require_equal(anfis, "seeds", EXPECTED_SEEDS, context="experimental_matrix.e7")
    resource_policy = _mapping(anfis, "resource_failure_policy", context="experimental_matrix.e7")
    _require_equal(
        resource_policy,
        "experiment_may_be_silently_omitted",
        False,
        context="experimental_matrix.e7.resource_failure_policy",
    )

    uncertainty = _mapping(matrix, "e8_uncertainty", context="experimental_matrix")
    _require_equal(uncertainty, "status", "required", context="experimental_matrix.e8")
    _require_equal(
        uncertainty,
        "nominal_coverage_levels",
        [0.80, 0.90, 0.95],
        context="experimental_matrix.e8",
    )
    _require_equal(uncertainty, "primary_nominal_coverage", 0.90, context="experimental_matrix.e8")
    _require_equal(
        uncertainty,
        "acceptable_absolute_coverage_error",
        0.05,
        context="experimental_matrix.e8",
    )
    interval_recalibration = _mapping(
        uncertainty,
        "continuous_interval_recalibration",
        context="experimental_matrix.e8",
    )
    _require_equal(
        interval_recalibration,
        "method",
        "symmetric_scaled_sigma_split_conformal",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "calibration_role",
        "calibration_threshold",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "calibration_period",
        {"start": "2021-01", "end": "2021-12"},
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "calibration_population",
        "non_holdout_wqp_locations_only",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "calibration_group_key",
        ["model_id", "surface_id", "endpoint", "horizon_months", "model_seed"],
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "pooling_across_groups",
        "forbidden",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "minimum_finite_calibration_rows_per_group",
        30,
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "scale_floor",
        0.000001,
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "nonconformity_score",
        "absolute_y_minus_mu_divided_by_max_sigma_scale_floor",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "finite_sample_quantile",
        {
            "n": "finite_calibration_scores_in_exact_group",
            "order_index_one_based": "min_n_ceil_n_plus_1_times_nominal_coverage",
            "interpolation": "higher_order_statistic_no_interpolation",
            "q_definition": "sorted_score_at_one_based_order_index",
        },
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "native_before_factors",
        [
            {"nominal_coverage": 0.80, "central_gaussian_factor": 1.2815515655446004},
            {"nominal_coverage": 0.90, "central_gaussian_factor": 1.6448536269514722},
            {"nominal_coverage": 0.95, "central_gaussian_factor": 1.959963984540054},
        ],
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "before_interval",
        "mu_plus_or_minus_native_central_gaussian_factor_times_sigma",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "after_interval",
        "mu_plus_or_minus_locked_level_specific_q_times_sigma",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "q_locked_before_E0_U",
        True,
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "q_refit_or_adjustment_in_locked_evaluation",
        "forbidden",
        context="experimental_matrix.e8.recalibration",
    )
    _require_equal(
        interval_recalibration,
        "before_after_evaluated_on_identical_locked_rows",
        True,
        context="experimental_matrix.e8.recalibration",
    )
    conditional_coverage = _mapping(
        uncertainty,
        "conditional_coverage",
        context="experimental_matrix.e8",
    )
    _require_equal(
        conditional_coverage,
        "role",
        "diagnostic_not_a_source_of_conditional_q_factors",
        context="experimental_matrix.e8.conditional",
    )
    _require_equal(
        conditional_coverage,
        "q_is_never_refit_within_conditional_strata",
        True,
        context="experimental_matrix.e8.conditional",
    )
    _require_equal(
        conditional_coverage,
        "evaluation_role",
        "locked_evaluation",
        context="experimental_matrix.e8.conditional",
    )
    _require_equal(
        conditional_coverage,
        "stratum_boundary_fit_period",
        {"start": "2021-01", "end": "2021-12"},
        context="experimental_matrix.e8.conditional",
    )
    required_breakdowns = _sequence(
        conditional_coverage,
        "required_breakdowns",
        context="experimental_matrix.e8.conditional",
    )
    breakdown_ids = [
        item.get("breakdown_id") if isinstance(item, Mapping) else None
        for item in required_breakdowns
    ]
    if breakdown_ids != [
        "global",
        "horizon",
        "nutrient_evidence_quartile",
        "input_missingness_quartile",
        "predicted_risk_band",
        "location_input_frequency",
        "location_novelty",
        "degradation_scenario",
    ]:
        raise ClosureContractError(
            "experimental_matrix.e8.conditional required_breakdowns must equal the locked order"
        )
    degradation_breakdown = required_breakdowns[-1]
    if not isinstance(degradation_breakdown, Mapping):
        raise ClosureContractError("experimental_matrix.e8 degradation breakdown must be a mapping")
    _require_equal(
        degradation_breakdown,
        "values",
        EXPECTED_E6_SCENARIOS,
        context="experimental_matrix.e8.conditional.degradation_scenario",
    )
    family_e = _mapping(
        uncertainty,
        "confirmatory_family_E",
        context="experimental_matrix.e8",
    )
    _require_equal(family_e, "model_id", "P1", context="experimental_matrix.e8.family_E")
    _require_equal(
        family_e,
        "surface_id",
        "closure_v1_wqp_adaptive_no_current_chla",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "endpoints",
        ["yN", "yF", "yT"],
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "horizons_months",
        [1, 2, 3],
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "nominal_coverage_levels",
        [0.90],
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "row_loss",
        "winkler_interval_score_at_0_90",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "paired_delta_direction",
        "after_minus_before",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "primary_estimand",
        "observation_weighted_mean_paired_delta_equal_weight_over_endpoints_and_horizons",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "seed_handling",
        "average_paired_row_loss_across_5_locked_seeds_before_ecological_inference",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "required_seed_count_per_paired_row",
        5,
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "missing_seed_policy",
        "row_not_in_shared_success_family_E_and_failure_reported_on_intent_to_predict_denominator",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "aggregation_order",
        [
            "compute_paired_winkler_delta_per_seed_and_exact_row",
            "require_all_5_locked_seeds_on_the_exact_row",
            "average_delta_equal_weight_across_seeds_within_row",
            "average_rows_observation_weighted_within_each_endpoint_horizon",
            "average_the_9_endpoint_horizon_cell_means_with_equal_weight",
            "run_paired_location_clustered_inference",
        ],
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "seeds_are_inference_units",
        False,
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "alternative",
        "less_than_zero",
        context="experimental_matrix.e8.family_E",
    )
    _require_equal(
        family_e,
        "p_value_universe_size",
        1,
        context="experimental_matrix.e8.family_E",
    )

    planning = _mapping(matrix, "e9_planning_inference", context="experimental_matrix")
    _require_equal(planning, "status", "required", context="experimental_matrix.e9")
    _require_equal(planning, "closure_matrix_is_authoritative", True, context="experimental_matrix.e9")
    _require_equal(planning, "scenario_count", 10, context="experimental_matrix.e9")
    _require_equal(
        planning,
        "model_contract",
        {
            "model_id": "P1",
            "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
            "ordered_model_seeds": EXPECTED_SEEDS,
            "refit_for_planning": "forbidden",
            "action_and_no_action_use_same_model_seed": True,
            "exact_row_shared_success_requires_all_5_seeds_for_action_and_no_action": True,
            "missing_seed_policy": (
                "exclude_exact_row_from_family_D_shared_success_and_report_failure_on_"
                "intent_to_predict"
            ),
            "seed_aggregation_order": [
                "compute_action_minus_no_action_objective_delta_per_seed_and_exact_row",
                "require_all_5_seeds_for_action_and_no_action_on_the_exact_row",
                "average_delta_equal_weight_across_seeds_within_row",
                "pool_exact_common_rows_observation_weighted_across_horizons_1_2_3",
                "run_paired_location_clustered_inference",
            ],
            "seeds_are_inference_units": False,
        },
        context="experimental_matrix.e9",
    )
    planning_ids = _scenario_ids(planning, context="experimental_matrix.e9")
    if planning_ids != EXPECTED_E9_SCENARIOS:
        raise ClosureContractError(
            "experimental_matrix.e9 scenarios must equal the locked ordered scenario universe"
        )
    objective_contract = _mapping(
        planning,
        "objective_contract",
        context="experimental_matrix.e9",
    )
    _require_equal(
        objective_contract,
        "objective_id",
        "closure_v1_raw_proxy_net_benefit",
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "all_actions_evaluated_regardless_of_legacy_cost_budget",
        True,
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "legacy_planning_mode_and_budget_reused",
        False,
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "component_definitions",
        {
            "irc_alert_score": "clip_0_1_of_yN_plus_1_minus_yF_plus_yT_divided_by_3",
            "bloom_probability_proxy": (
                "clip_0_1_of_0_5_times_yT_plus_0_5_times_irc_alert_score"
            ),
            "uncertainty": "arithmetic_mean_of_finite_sigma_N_sigma_F_sigma_T",
            "missing_uncertainty_component_policy": "row_model_unavailable_no_zero_imputation",
            "support_violation": (
                "one_if_any_modified_raw_proxy_outside_locked_support_envelope_else_zero"
            ),
        },
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "reductions_against_no_action",
        {
            "delta_irc": "irc_no_action_minus_irc_scenario",
            "delta_bloom": "bloom_probability_no_action_minus_bloom_probability_scenario",
            "delta_uncertainty": "uncertainty_scenario_minus_uncertainty_no_action",
        },
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "primary_weights",
        {"irc_alert_risk_reduction": 0.60, "bloom_probability_reduction": 0.40},
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "base_penalties",
        {"lambda_cost": 0.05, "lambda_uncertainty": 0.10, "lambda_support": 0.05},
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "objective_formula",
        (
            "0.60_delta_irc_plus_0.40_delta_bloom_minus_0.05_cost_multiplier_relative_cost_"
            "minus_0.10_max_0_delta_uncertainty_minus_0.05_support_multiplier_support_violation"
        ),
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "no_action_objective_exactly_zero",
        True,
        context="experimental_matrix.e9.objective",
    )
    _require_equal(
        objective_contract,
        "delta_objective_definition",
        "objective_scenario_minus_objective_no_action",
        context="experimental_matrix.e9.objective",
    )
    support_contract = _mapping(
        planning,
        "support_contract",
        context="experimental_matrix.e9",
    )
    _require_equal(
        support_contract,
        "fit_role",
        "training",
        context="experimental_matrix.e9.support",
    )
    _require_equal(
        support_contract,
        "fit_population",
        "non_holdout_wqp_locations",
        context="experimental_matrix.e9.support",
    )
    _require_equal(
        support_contract,
        "site_envelope",
        {"minimum_finite_months": 24, "lower_quantile": 0.05, "upper_quantile": 0.95},
        context="experimental_matrix.e9.support",
    )
    _require_equal(
        support_contract,
        "source_fallback_envelope",
        {"lower_quantile": 0.01, "upper_quantile": 0.99},
        context="experimental_matrix.e9.support",
    )
    _require_equal(
        support_contract,
        "heldout_locations_use_source_fallback",
        True,
        context="experimental_matrix.e9.support",
    )
    family_d = _mapping(planning, "confirmatory_family_D", context="experimental_matrix.e9")
    _require_equal(family_d, "cost_weight_multiplier", 1.0, context="experimental_matrix.e9.family_D")
    _require_equal(family_d, "support_penalty_multiplier", 1.0, context="experimental_matrix.e9.family_D")
    _require_equal(family_d, "baseline_scenario_id", "no_action", context="experimental_matrix.e9.family_D")
    _require_equal(
        family_d,
        "action_scenario_ids",
        EXPECTED_E9_SCENARIOS[1:],
        context="experimental_matrix.e9.family_D",
    )
    _require_equal(family_d, "p_value_universe_size", 9, context="experimental_matrix.e9.family_D")
    _require_equal(
        family_d,
        "primary_action_estimand",
        "observation_weighted_mean_over_exact_common_origins_and_horizons_1_2_3",
        context="experimental_matrix.e9.family_D",
    )
    _require_equal(
        family_d,
        "paired_cluster_unit",
        "holdout_group_id",
        context="experimental_matrix.e9.family_D",
    )
    sensitivity = _mapping(planning, "descriptive_sensitivity", context="experimental_matrix.e9")
    _require_equal(sensitivity, "role", "descriptive_only", context="experimental_matrix.e9.sensitivity")
    _require_equal(
        sensitivity,
        "cost_weight_multipliers",
        [0.5, 1.0, 2.0],
        context="experimental_matrix.e9.sensitivity",
    )
    _require_equal(
        sensitivity,
        "support_penalty_multipliers",
        [0.5, 1.0, 2.0],
        context="experimental_matrix.e9.sensitivity",
    )
    _require_equal(sensitivity, "cartesian_grid_size", 9, context="experimental_matrix.e9.sensitivity")
    return matrix


def _validate_legacy_planning_catalog(
    path: str | Path,
    experimental_matrix: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify that the locked provenance catalog matches the copied E9 scenarios."""

    catalog = load_yaml_mapping(path)
    _require_equal(catalog, "schema_version", 1, context="legacy_planning_catalog")
    catalog_family = _mapping(catalog, "scenario_family", context="legacy_planning_catalog")
    planning = _mapping(experimental_matrix, "e9_planning_inference", context="experimental_matrix")
    catalog_scenarios = _sequence(catalog_family, "scenarios", context="legacy_planning_catalog")
    matrix_scenarios = _sequence(planning, "scenarios", context="experimental_matrix.e9")
    if catalog_scenarios != matrix_scenarios:
        raise ClosureContractError(
            "experimental_matrix.e9 scenarios must exactly copy the locked legacy planning catalog"
        )
    return catalog


def validate_analysis_plan(
    plan: Mapping[str, Any],
    *,
    require_files: bool = True,
    reject_unresolved: bool | None = None,
) -> dict[str, Any]:
    """Validate all decisions that must precede cohort construction."""
    _require_equal(plan, "schema_version", ANALYSIS_SCHEMA_VERSION, context="analysis_plan")
    _require_equal(plan, "experiment_id", EXPERIMENT_ID, context="analysis_plan")
    _require_equal(plan, "plan_version", PLAN_VERSION, context="analysis_plan")

    protocol = _mapping(plan, "protocol", context="analysis_plan")
    _require_equal(protocol, "registration_class", REGISTRATION_CLASS, context="protocol")
    if protocol.get("status") not in {"ready_to_lock", "locked"}:
        raise ClosureContractError("protocol.status must be 'ready_to_lock' or 'locked'")
    claims = _mapping(protocol, "claim_authorizations", context="protocol")
    _require_equal(claims, "external_validation", False, context="protocol.claim_authorizations")
    _require_equal(claims, "prospective_field_validation", False, context="protocol.claim_authorizations")
    _require_equal(claims, "unseen_waterbody_transfer", False, context="protocol.claim_authorizations")

    provenance = _mapping(plan, "provenance", context="analysis_plan")
    _require_equal(provenance, "legacy_temporal_test_previously_observed", True, context="provenance")
    _require_equal(provenance, "post_2021_outcomes_exist_in_repository", True, context="provenance")
    _require_equal(provenance, "historical_freeze_git_state", "dirty_at_generation", context="provenance")
    _require_equal(provenance, "accepted_waterbody_crosswalk_exists", False, context="provenance")

    _validate_time_roles(_mapping(plan, "time_roles", context="analysis_plan"))
    _validate_holdout(_mapping(plan, "holdout", context="analysis_plan"))

    cohorts = _mapping(plan, "cohorts", context="analysis_plan")
    _require_equal(cohorts, "denominators", EXPECTED_DENOMINATORS, context="cohorts")
    _require_equal(cohorts, "silent_failure_exclusion_allowed", False, context="cohorts")

    seeds = _mapping(plan, "seeds", context="analysis_plan")
    _require_equal(seeds, "values", EXPECTED_SEEDS, context="seeds")
    _require_equal(seeds, "pool_as_independent_replicates", False, context="seeds")

    calibration = _mapping(plan, "calibration", context="analysis_plan")
    _require_equal(calibration, "method_selection_role", "model_selection", context="calibration")
    _require_equal(
        calibration,
        "bloom_method_candidates",
        ["identity", "platt_logistic", "isotonic_regression"],
        context="calibration",
    )
    _require_equal(calibration, "bloom_method_selection_metric", "brier", context="calibration")
    _require_equal(
        calibration,
        "bloom_method_secondary_metric",
        "expected_calibration_error",
        context="calibration",
    )
    _require_equal(calibration, "selected_method_fit_role", "calibration_threshold", context="calibration")
    alert_threshold = _mapping(calibration, "alert_threshold", context="calibration")
    ordinal_cutpoints = _mapping(calibration, "ordinal_cutpoints", context="calibration")
    _require_equal(alert_threshold, "selection_role", "calibration_threshold", context="calibration.alert_threshold")
    _require_equal(ordinal_cutpoints, "selection_role", "calibration_threshold", context="calibration.ordinal_cutpoints")
    _require_equal(calibration, "evaluation_refit", "forbidden", context="calibration")

    hypotheses = _mapping(plan, "hypotheses", context="analysis_plan")
    if not _sequence(hypotheses, "primary", context="hypotheses"):
        raise ClosureContractError("hypotheses.primary must not be empty")
    _require_equal(
        hypotheses,
        "additional_predeclared_families",
        [
            {
                "id": "B_matched_degradation",
                "matrix_reference": "configs/closure_v1/experimental_matrix.yaml",
                "comparison_rule": (
                    "M0_vs_P1_for_exactly_13_matrix_scenarios_3_horizons_2_endpoints"
                ),
            },
            {
                "id": "D_planning",
                "matrix_reference": "configs/closure_v1/experimental_matrix.yaml",
                "comparison_rule": "each_of_9_actions_vs_no_action_at_cost_1_support_1",
            },
            {
                "id": "E_uncertainty",
                "matrix_reference": "configs/closure_v1/experimental_matrix.yaml",
                "comparison_rule": (
                    "one_P1_primary_surface_aggregate_0_90_winkler_after_vs_before_test_"
                    "0_80_0_95_descriptive"
                ),
            },
        ],
        context="hypotheses",
    )
    multiplicity = _mapping(plan, "multiplicity", context="analysis_plan")
    _require_equal(multiplicity, "method", "holm", context="multiplicity")
    _require_equal(multiplicity, "family_wise_alpha", 0.05, context="multiplicity")

    inference = _mapping(plan, "inference", context="analysis_plan")
    _require_equal(inference, "paired_cluster_unit", "holdout_group_id", context="inference")
    bootstrap = _mapping(inference, "bootstrap", context="inference")
    _require_equal(bootstrap, "final_replicates", 5000, context="inference.bootstrap")

    failure_policy = _mapping(plan, "failure_policy", context="analysis_plan")
    expected_terminal_statuses = [
        "success",
        "input_ineligible",
        "target_unavailable",
        "model_unavailable",
        "numerical_failure",
        "infrastructure_failure",
    ]
    _require_equal(failure_policy, "terminal_statuses", expected_terminal_statuses, context="failure_policy")
    _require_equal(failure_policy, "failed_origin_replacement", "forbidden", context="failure_policy")
    _require_equal(failure_policy, "failed_location_replacement", "forbidden", context="failure_policy")

    outcome_access = _mapping(plan, "outcome_access", context="analysis_plan")
    _require_equal(outcome_access, "holdout_outcomes_accessed", False, context="outcome_access")
    _require_equal(
        outcome_access,
        "outcome_access_definition",
        "semantic_decoding_inspection_aggregation_or_use_of_outcome_rows",
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "semantic_access_scope",
        "rows_and_values_materialized_to_closure_application_logic",
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "storage_engine_internal_page_decoding_audited_or_claimed",
        False,
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "selector_requests_pre_cutoff_projection_at_parquet_read_api",
        True,
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "post_cutoff_target_rows_materialized_to_selector_logic",
        False,
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "locker_reads_complete_source_artifact_bytes_for_sha256",
        True,
        context="outcome_access",
    )
    _require_equal(
        outcome_access,
        "locker_decodes_or_inspects_post_2021_outcome_rows",
        False,
        context="outcome_access",
    )
    _require_equal(outcome_access, "evaluation_batches", 1, context="outcome_access")
    _require_equal(outcome_access, "explicit_authorization_required", True, context="outcome_access")

    change_control = _mapping(plan, "change_control", context="analysis_plan")
    _require_equal(change_control, "preserve_original_outputs", True, context="change_control")
    _require_equal(change_control, "post_metric_change_loses_locked_label", True, context="change_control")

    surfaces = _mapping(plan, "surfaces", context="analysis_plan")
    primary_surface = _mapping(surfaces, "primary", context="surfaces")
    secondary_surface = _mapping(surfaces, "secondary", context="surfaces")
    primary_path = primary_surface.get("config")
    secondary_path = secondary_surface.get("config")
    if not isinstance(primary_path, str) or not isinstance(secondary_path, str):
        raise ClosureContractError("surfaces.primary.config and surfaces.secondary.config must be paths")

    experimental_matrix = _mapping(plan, "experimental_matrix", context="analysis_plan")
    matrix_path = experimental_matrix.get("config")
    legacy_planning_path = experimental_matrix.get("legacy_planning_catalog")
    if not isinstance(matrix_path, str) or not isinstance(legacy_planning_path, str):
        raise ClosureContractError(
            "experimental_matrix.config and experimental_matrix.legacy_planning_catalog must be paths"
        )
    _require_equal(
        experimental_matrix,
        "closure_roles_and_estimands_take_precedence",
        True,
        context="experimental_matrix",
    )
    _require_equal(
        experimental_matrix,
        "deterministic_e6_mask_algorithm_locked",
        True,
        context="experimental_matrix",
    )
    _require_equal(
        experimental_matrix,
        "e8_before_after_recalibration_contract_locked",
        True,
        context="experimental_matrix",
    )
    _require_equal(
        experimental_matrix,
        "complete_e9_objective_locked_in_closure_matrix",
        True,
        context="experimental_matrix",
    )

    holdout_path = _mapping(plan, "holdout", context="analysis_plan").get("config")
    model_path = _mapping(plan, "models", context="analysis_plan").get("config")
    if not isinstance(holdout_path, str) or not isinstance(model_path, str):
        raise ClosureContractError("holdout.config and models.config must be paths")

    locking = _mapping(plan, "locking", context="analysis_plan")
    component_paths = _component_paths(locking)
    if component_paths != EXPECTED_PROTOCOL_COMPONENTS:
        raise ClosureContractError(
            "locking.protocol_components must equal the locked ordered component list"
        )
    _require_equal(locking, "require_schema_validation", True, context="locking")
    _require_equal(
        locking,
        "lock_command_reads_complete_source_bytes_for_sha256",
        True,
        context="locking",
    )
    _require_equal(
        locking,
        "lock_command_semantically_decodes_post_2021_outcomes",
        False,
        context="locking",
    )
    source_artifacts = _sequence(locking, "source_artifacts", context="locking")
    source_paths: list[str] = []
    for index, record in enumerate(source_artifacts):
        if not isinstance(record, Mapping) or not isinstance(record.get("path"), str):
            raise ClosureContractError(f"locking.source_artifacts[{index}] must contain a path")
        source_paths.append(str(record["path"]))
    if source_paths != EXPECTED_SOURCE_ARTIFACTS:
        raise ClosureContractError(
            "locking.source_artifacts must equal the locked ordered source-artifact list"
        )

    if reject_unresolved is None:
        reject_unresolved = protocol.get("status") == "locked"
    if reject_unresolved:
        unresolved = _walk_decisions(plan)
        if unresolved:
            raise ClosureContractError(f"Locked plan contains unresolved decisions: {unresolved[:8]}")

    if require_files:
        schema_path = locking.get("schema_path", DEFAULT_ANALYSIS_SCHEMA.as_posix())
        if not isinstance(schema_path, str):
            raise ClosureContractError("locking.schema_path must be a path")
        schema = load_json_mapping(schema_path)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise ClosureContractError("analysis_plan.schema.json must declare JSON Schema draft 2020-12")
        validate_json_schema(plan, schema, instance_path="$.analysis_plan")
        matrix_config = _validate_experimental_matrix(matrix_path)
        referenced_configs = {
            "primary_surface": _validate_surface(primary_path, primary=True),
            "secondary_surface": _validate_surface(secondary_path, primary=False),
            "location_holdout": _validate_location_holdout(holdout_path),
            "model_benchmark": _validate_model_benchmark(model_path),
            "experimental_matrix": matrix_config,
            "legacy_planning_catalog": _validate_legacy_planning_catalog(
                legacy_planning_path,
                matrix_config,
            ),
        }
        if reject_unresolved:
            referenced_unresolved = [
                finding
                for label, payload in referenced_configs.items()
                for finding in _walk_decisions(payload, f"$.{label}")
            ]
            if referenced_unresolved:
                raise ClosureContractError(
                    "Locked referenced config contains unresolved decisions: "
                    f"{referenced_unresolved[:8]}"
                )
        for path in component_paths:
            resolved = resolve_repo_path(path)
            if not resolved.is_file():
                raise ClosureContractError(f"Missing protocol component: {path}")
        for source_path in source_paths:
            if not resolve_repo_path(source_path).is_file():
                raise ClosureContractError(f"Missing source artifact: {source_path}")

    return {
        "experiment_id": EXPERIMENT_ID,
        "plan_version": PLAN_VERSION,
        "protocol_status": protocol["status"],
        "protocol_components": component_paths,
        "source_artifact_count": len(source_artifacts),
    }


def load_and_validate_analysis_plan(
    path: str | Path = DEFAULT_ANALYSIS_PLAN,
    *,
    require_files: bool = True,
    reject_unresolved: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the public plan and return it with a compact validation summary."""
    plan = load_yaml_mapping(path)
    summary = validate_analysis_plan(plan, require_files=require_files, reject_unresolved=reject_unresolved)
    return plan, summary
