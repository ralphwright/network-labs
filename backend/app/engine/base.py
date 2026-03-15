from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, field


@dataclass
class ObjectiveResult:
    objective_id: str
    description: str
    passed: bool
    message: str


@dataclass
class SimulationResult:
    success: bool
    packet_traces: list = field(default_factory=list)
    events: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


class BaseSimulator(ABC):
    @abstractmethod
    def validate_topology(self, topology_data: dict) -> list[str]: ...

    @abstractmethod
    def simulate(self, topology_data: dict, configuration: dict) -> SimulationResult: ...

    @abstractmethod
    def verify_objectives(self, topology_data: dict, results: SimulationResult, rules: dict) -> list[ObjectiveResult]: ...
