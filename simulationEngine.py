import heapq
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict


# --- 1. Event Definitions ---
class EventType(Enum):
    ARRIVAL = auto()
    ORDER_COMPLETED = auto()      # Finished paying/ordering at counter/DT
    KITCHEN_PREP_DONE = auto()    # Cook/Barista finished making item
    PACKING_DONE = auto()         # Item put in bag/tray
    CUSTOMER_PICKUP = auto()      # Customer leaves with food
    BREW_FINISH = auto()          # Coffee urn refill complete
    MOBILE_RENEGE_CHECK = auto()  # Check if mobile user gave up

@dataclass(order=True)
class Event:
    time: float
    event_type: EventType = field(compare=False)
    customer: Optional['Customer'] = field(default=None, compare=False)
    # Priority tie-breaker (to process simultaneous events deterministically)
    id: int = field(default=0, compare=False) 

# --- 2. The Base Engine ---
class SimulationEngine:
    def __init__(self):
        self.clock = 0.0
        self.event_list = []  # The Min-Heap
        self.event_count = 0  # Unique ID generator

    def schedule(self, delay: float, event_type: EventType, customer=None):
        """Add an event to the future."""
        timestamp = self.clock + delay
        self.event_count += 1
        event = Event(timestamp, event_type, customer, self.event_count)
        heapq.heappush(self.event_list, event)

    def run(self, max_time: float):
        while self.event_list and self.clock < max_time:
            # 1. Pop earliest event
            current_event = heapq.heappop(self.event_list)
            
            # 2. Advance Time
            self.clock = current_event.time
            
            # 3. Process
            self.handle_event(current_event)

    def handle_event(self, event):
        raise NotImplementedError("Subclasses must implement handle_event")