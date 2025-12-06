from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List

class Channel(Enum):
    WALK_IN = auto()
    DRIVE_THRU = auto()
    MOBILE = auto()

@dataclass
class Customer:
    id: int
    channel: Channel
    arrival_time: float
    items_needed: List[str]  # e.g., ['COFFEE', 'BAGEL']
    
    # Tracking State
    order_start_time: float = 0.0
    kitchen_start_time: float = 0.0
    ready_time: float = 0.0
    
    # Flags
    balked: bool = False
    reneged: bool = False
    is_ready: bool = False

@dataclass
class Config:
    # Staffing
    NUM_CASHIERS: int = 1
    NUM_COOKS: int = 2
    NUM_PACKERS: int = 1
    
    # Capacities
    MAX_DRIVE_THRU_QUEUE: int = 10
    SHELF_CAPACITY: int = 15
    COFFEE_URN_CAPACITY: int = 50  # servings
    
    # Costs/Prices
    PRICE_AVG: float = 8.00
    COST_LABOR_HR: float = 15.00
    PENALTY_RENEGE: float = 10.00
    PENALTY_BALK: float = 5.00