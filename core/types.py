from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Type


class ValidationError(ValueError):
    """Error raised when a field value fails validation."""


_FIELD_TYPE_REGISTRY: Dict[str, Type["FieldType"]] = {}


class FieldType(ABC):

    type_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None: 
        super().__init_subclass__(**kwargs)
        type_name = getattr(cls, "type_name", None)
        if type_name:
            _FIELD_TYPE_REGISTRY[type_name] = cls

    @abstractmethod
    def validate(self, value: Any) -> Any:
        """Validate a value, returning the (possibly coerced) value or raising ValidationError."""

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type_name, "config": self._config_dict()}

    def _config_dict(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FieldType":
        type_name = payload["type"]
        config = payload.get("config", {})
        try:
            type_cls = _FIELD_TYPE_REGISTRY[type_name]
        except KeyError as exc:  
            raise ValueError(f"Unknown field type '{type_name}'") from exc
        if issubclass(type_cls, IntervalType):
            return type_cls.from_config(config)
        return type_cls(**config)


class IntegerType(FieldType):
    type_name = "integer"

    def validate(self, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError("Expected integer")
        return value


class RealType(FieldType):
    type_name = "real"

    def validate(self, value: Any) -> float:
        if isinstance(value, bool):
            raise ValidationError("Expected real number")
        if isinstance(value, (int, float)):
            return float(value)
        raise ValidationError("Expected real number")


class CharType(FieldType):
    type_name = "char"

    def validate(self, value: Any) -> str:
        if not isinstance(value, str) or len(value) != 1:
            raise ValidationError("Expected single character string")
        return value


class StringType(FieldType):
    type_name = "string"

    def validate(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError("Expected string")
        return value


class HtmlFileType(StringType):
    type_name = "htmlFile"

    def validate(self, value: Any) -> str:
        if isinstance(value, dict):
            content = value.get("content")
            if isinstance(content, str):
                return content
            raise ValidationError("Expected HTML content string")

        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError("HTML bytes must be UTF-8") from exc

        path_str = super().validate(value)
        file_path = Path(path_str)
        if file_path.is_file() and file_path.suffix.lower() in {".html", ".htm"}:
            try:
                return file_path.read_text(encoding="utf-8")
            except OSError as exc:  # pragma: no cover
                raise ValidationError(f"Failed to read HTML file '{file_path}': {exc}") from exc

        if isinstance(path_str, str) and ("<" in path_str and ">" in path_str):
            return path_str

        raise ValidationError("Expected HTML content or path to .html/.htm file")


@dataclass
class IntervalType(FieldType):
    type_name = "interval"

    base_type: FieldType
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None

    def validate(self, value: Any) -> Any:
        result = self.base_type.validate(value)
        if self.min_value is not None and result < self.min_value:
            raise ValidationError(f"Value {result!r} is less than minimum {self.min_value!r}")
        if self.max_value is not None and result > self.max_value:
            raise ValidationError(f"Value {result!r} exceeds maximum {self.max_value!r}")
        return result

    def _config_dict(self) -> Dict[str, Any]:
        return {
            "base_type": self.base_type.to_dict(),
            "min_value": self.min_value,
            "max_value": self.max_value,
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "IntervalType":
        base_type_payload = config["base_type"]
        base_type = FieldType.from_dict(base_type_payload)
        return cls(
            base_type=base_type,
            min_value=config.get("min_value"),
            max_value=config.get("max_value"),
        )


class StringIntervalType(IntervalType):
    type_name = "stringInvl"

    def __init__(self, min_value: Optional[str] = None, max_value: Optional[str] = None) -> None:
        super().__init__(base_type=StringType(), min_value=min_value, max_value=max_value)

    def _config_dict(self) -> Dict[str, Any]:
        return {"min_value": self.min_value, "max_value": self.max_value}

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "StringIntervalType":
        return cls(min_value=config.get("min_value"), max_value=config.get("max_value"))


def build_field_type(type_descriptor: Any) -> FieldType:
    if isinstance(type_descriptor, FieldType):
        return type_descriptor
    if isinstance(type_descriptor, dict):
        return FieldType.from_dict(type_descriptor)
    if isinstance(type_descriptor, str):
        type_name = type_descriptor
        if type_name not in _FIELD_TYPE_REGISTRY:
            raise ValueError(f"Unknown field type '{type_name}'")
        type_cls = _FIELD_TYPE_REGISTRY[type_name]
        if issubclass(type_cls, IntervalType) and type_cls is IntervalType:
            raise ValueError("Interval type requires configuration dictionary")
        return type_cls()
    raise TypeError(f"Unsupported type descriptor: {type_descriptor!r}")


__all__ = [
    "FieldType",
    "IntegerType",
    "RealType",
    "CharType",
    "StringType",
    "HtmlFileType",
    "IntervalType",
    "StringIntervalType",
    "ValidationError",
    "build_field_type",
]

