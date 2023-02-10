# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018-2020 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
from collections import OrderedDict
from typing import Dict, List

from snapcraft import formatting_utils
from snapcraft.internal.errors import SnapcraftError

_VALIDATION_ERROR_CAUSES = {
    "maxLength": "maximum length is {validator_value}",
    "minLength": "minimum length is {validator_value}",
}


class YamlValidationError(SnapcraftError):

    fmt = "Issues while validating {source}: {message}"

    @classmethod
    def from_validation_error(cls, error, *, source="snapcraft.yaml"):
        """Take a jsonschema.ValidationError and create a SnapcraftSchemaError.

        The validation errors coming from jsonschema are a nightmare. This
        class tries to make them a bit more understandable.
        """

        messages = []

        preamble = _determine_preamble(error)
        cause = _determine_cause(error)
        supplement = _determine_supplemental_info(error)

        if preamble:
            messages.append(preamble)

        # If we have a preamble we are not at the root
        if supplement and preamble:
            messages.extend((error.message, f"({supplement})"))
        elif supplement:
            messages.append(supplement)
        elif cause:
            messages.append(cause)
        else:
            messages.append(error.message)

        return cls(" ".join(messages), source)

    def __init__(self, message, source="snapcraft.yaml"):
        super().__init__(message=message, source=source)


def _determine_preamble(error):
    messages = []
    if path := _determine_property_path(error):
        messages.append(
            f"""The '{"/".join(path)}' property does not match the required schema:"""
        )
    return " ".join(messages)


def _determine_cause(error):
    messages = []

    # error.validator_value may contain a custom validation error message.
    # If so, use it instead of the garbage message jsonschema gives us.
    with contextlib.suppress(TypeError, KeyError):
        messages.append(error.validator_value["validation-failure"].format(error))

    # The schema itself may have a custom validation error message. If so,
    # use it as well.
    with contextlib.suppress(AttributeError, TypeError, KeyError):
        key = error
        if (
            error.schema.get("type") == "object"
            and error.validator == "additionalProperties"
        ):
            key = list(error.instance.keys())[0]

        messages.append(error.schema["validation-failure"].format(key))

    # anyOf failures might have usable context... try to improve them a bit
    if error.validator == "anyOf":
        contextual_messages: Dict[str, str] = OrderedDict()
        for contextual_error in error.context:
            key = contextual_error.schema_path.popleft()
            if key not in contextual_messages:
                contextual_messages[key] = []
            if message := contextual_error.message:
                # Sure it starts lower-case (not all messages do)
                contextual_messages[key].append(message[0].lower() + message[1:])

        oneOf_messages: List[str] = [
            formatting_utils.humanize_list(value, "and", "{}")
            for value in contextual_messages.values()
        ]
        messages.append(formatting_utils.humanize_list(oneOf_messages, "or", "{}"))

    return " ".join(messages)


def _determine_supplemental_info(error):
    message = _VALIDATION_ERROR_CAUSES.get(error.validator, "").format(
        validator_value=error.validator_value
    )

    if not message and error.validator == "anyOf":
        message = _interpret_anyOf(error)

    if not message and error.cause:
        message = error.cause

    return message


def _determine_property_path(error):
    path = []
    while error.absolute_path:
        element = error.absolute_path.popleft()
        # assume numbers are indices and use 'xxx[123]' notation.
        if isinstance(element, int):
            path[-1] = f"{path[-1]}[{element}]"
        else:
            path.append(str(element))

    return path


def _interpret_anyOf(error):
    """Interpret a validation error caused by the anyOf validator.

    Returns:
        A string containing a (hopefully) helpful validation error message. It
        may be empty.
    """

    usages = []
    try:
        usages.extend(validator["usage"] for validator in error.validator_value)
    except (TypeError, KeyError):
        return ""

    return "must be one of {}".format(
        formatting_utils.humanize_list(usages, "or", "{}")
    )
