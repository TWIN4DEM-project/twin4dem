import csv
import io
from typing import Any, Iterable, List, Optional

from django.core import checks
from django.core.exceptions import ValidationError
from django.db import models


class SeparatedValuesField(models.TextField):
    """Store a Python list in the DB as a separated string."""

    description = "List stored as a separated string"

    def __init__(
        self,
        *args: Any,
        base_field: models.Field,
        separator: str = ",",
        **kwargs: Any,
    ) -> None:
        """Initialise base field to use for reading/writing individual values.

        :param args: passed to `models.TextField`
        :param base_field: type of `models.Field` to use for interpreting individual values
        :param separator: a single character `str` used for separating individual values
        :param kwargs: passed to `models.TextField`
        """
        if not isinstance(separator, str) or len(separator) != 1:
            raise ValueError("separator must be a single character string")
        self.__base_field = base_field
        self.__separator = separator

        super().__init__(*args, **kwargs)

    # --- Django checks (system check framework) ---
    def check(self, **kwargs: Any):
        errors = super().check(**kwargs)
        errors.extend(self._check_separator())
        return errors

    def _check_separator(self):
        if not isinstance(self.__separator, str) or len(self.__separator) != 1:
            return [
                checks.Error(
                    "separator must be a single character string",
                    obj=self,
                    id="fields.E900",
                )
            ]
        return []

    # --- (De)serialization helpers ---
    def _coerce_iterable(self, value: Any) -> Optional[List[Any]]:
        if value is None:
            return None
        if value == "":
            return []

        val_type = list
        if isinstance(value, (list, tuple, set, frozenset)):
            val_type = type(value)
        elif isinstance(value, str):
            value = self._deserialize(value)
        else:
            raise ValidationError(
                "Value must be a list, tuple, set, frozenset, str or None."
            )

        return val_type(map(self.__base_field.to_python, value))

    def _get_prep_value(self, v):
        return "" if v is None else str(self.__base_field.get_prep_value(v))

    def _serialize(self, values: Iterable[Any]) -> str:
        prepped = list(map(self._get_prep_value, values))
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=self.__separator)
        writer.writerow(prepped)
        return buf.getvalue().rstrip("\r\n")

    def _deserialize(self, s: str) -> List[str]:
        if s == "":
            return []

        reader = csv.reader([s], delimiter=self.__separator)
        return next(reader, [])

    # --- Django Field API ---
    def to_python(self, value: Any) -> Optional[List[Any]]:
        return self._coerce_iterable(value)

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        return self.to_python(value)

    def get_prep_value(self, value: Any) -> Any:
        value_list = self._coerce_iterable(value)
        if value_list is None:
            return None
        return self._serialize(value_list)

    def value_to_string(self, obj: Any) -> str:
        value = self.value_from_object(obj)
        prepped = self.get_prep_value(value)
        return "" if prepped is None else str(prepped)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if not isinstance(self.__base_field, models.CharField):
            kwargs["base_field"] = self.__base_field
        if self.__separator != ",":
            kwargs["separator"] = self.__separator
        return name, path, args, kwargs

    def formfield(self, **kwargs: Any):
        # Keep default as a string input; model field handles coercion.
        defaults = {"help_text": kwargs.pop("help_text", None)}
        defaults.update(kwargs)
        return super().formfield(**defaults)
