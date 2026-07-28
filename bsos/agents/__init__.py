from bsos.agents.base import Agent
from bsos.agents.analyst import ANALYST
from bsos.agents.custodian import CUSTODIAN
from bsos.agents.designer import DESIGNER
from bsos.agents.producer import PRODUCER
from bsos.agents.publisher import PUBLISHER

ALL_AGENTS: tuple[Agent, ...] = (CUSTODIAN, ANALYST, DESIGNER, PRODUCER, PUBLISHER)

__all__ = ["Agent", "ALL_AGENTS", "CUSTODIAN", "ANALYST", "DESIGNER", "PRODUCER", "PUBLISHER"]
