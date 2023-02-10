# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018 Canonical Ltd
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

import re
from typing import TYPE_CHECKING, Iterable, List, Optional

from . import typing
from .errors import UnsatisfiedStatementError

# Don't use circular imports unless type checking
if TYPE_CHECKING:
    from ._processor import GrammarProcessor  # noqa: F401

_SELECTOR_PATTERN = re.compile(r"\Aon\s+([^,\s](?:,?[^,]+)*)\Z")
_WHITESPACE_PATTERN = re.compile(r"\A.*\s.*\Z")


class Statement:
    """Base class for all grammar statements"""

    def __init__(
        self,
        *,
        body: Optional[typing.Grammar],
        processor: "GrammarProcessor",
        call_stack: Optional[typing.CallStack],
        check_primitives: bool = False
    ) -> None:
        """Create an Statement instance.

        :param list body: The body of the clause.
        :param GrammarProcessor process: GrammarProcessor to use for processing
                                         this statement.
        :param list call_stack: Call stack leading to this statement.
        :param bool check_primitives: Whether or not the primitives should be
                                      checked for validity as part of
                                      evaluating the elses.
        """
        self.__call_stack = call_stack or []
        self._body = body
        self._processor = processor
        self._check_primitives = check_primitives
        self._else_bodies: List[Optional[typing.Grammar]] = []

        self.__processed_body: Optional[List[str]] = None
        self.__processed_else: Optional[List[str]] = None

    def add_else(self, else_body: Optional[typing.Grammar]) -> None:
        """Add an 'else' clause to the statement.

        :param list else_body: The body of an 'else' clause.

        The 'else' clauses will be processed in the order they are added.
        """
        self._else_bodies.append(else_body)

    def process(self) -> List[str]:
        """Process this statement.

        :return: Primitives as determined by evaluating the statement or its
                 else clauses.
        """
        return self._process_body() if self._check() else self._process_else()

    def _process_body(self) -> List[str]:
        """Process the main body of this statement.

        :return: Primitives as determined by processing the main body.
        """
        if self.__processed_body is None:
            self.__processed_body = self._processor.process(
                grammar=self._body, call_stack=self._call_stack(include_self=True)
            )

        return self.__processed_body

    def _process_else(self) -> List[str]:
        """Process the else clauses of this statement in order.

        :return: Primitives as determined by processing the else clauses.
        """
        if self.__processed_else is not None:
            return self.__processed_else

        self.__processed_else = []
        for else_body in self._else_bodies:
            if not else_body:
                # Handle the 'else fail' case.
                raise UnsatisfiedStatementError(self)

            if processed_else := self._processor.process(
                grammar=else_body, call_stack=self._call_stack()
            ):
                self.__processed_else = processed_else
                if not self._check_primitives or self._validate_primitives(
                    processed_else
                ):
                    break

        return self.__processed_else

    def _validate_primitives(self, primitives: Iterable[str]) -> bool:
        """Ensure that all primitives are valid.

        :param primitives: Iterable container of primitives.

        :return: Whether or not all primitives are valid.
        :rtype: bool
        """
        return all(self._processor.checker(primitive) for primitive in primitives)

    def _call_stack(self, *, include_self=False) -> List["Statement"]:
        """The call stack when processing this statement.

        :param bool include_self: Whether or not this statement should be
                                  included in the stack.

        :return: The call stack
        :rtype: list
        """
        return self.__call_stack + [self] if include_self else self.__call_stack

    def __repr__(self):
        return "{!r}".format(self.__str__())

    def _check(self) -> bool:
        """Check if a statement main body should be processed.

        :return: True if main body should be processed, False if elses should
                 be processed.
        :rtype: bool
        """
        raise NotImplementedError("this must be implemented by child classes")

    def __eq__(self, other) -> bool:
        raise NotImplementedError("this must be implemented by child classes")

    def __str__(self) -> str:
        raise NotImplementedError("this must be implemented by child classes")
