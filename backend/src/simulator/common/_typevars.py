from typing import TypeVar
from ._agent import Agent


TInput = TypeVar("TInput", contravariant=True)
TOutput = TypeVar("TOutput", covariant=True)
TAgent = TypeVar("TAgent", bound=Agent, covariant=True)
