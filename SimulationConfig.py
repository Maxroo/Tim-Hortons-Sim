import heapq
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict

# --- A. Configuration Class ---
@dataclass
class SimulationConfig:
    """Central configuration for Tim Hortons Operations."""
    random_seed: int = 42
    # 1. Staffing (Decision Variables)
    num_cashiers: int = 1 # required M/M/1
    num_packers: int = 1 # required M/M/1
    num_dt_stations: int = 1 # required M/M/1

    num_cooks: int = 3
    # 2. Capacity Constraints
    max_drive_thru_queue: int = 10     # Cars
    pickup_shelf_capacity: int = 15    # Bags
    coffee_urn_size: int = 40          # Portions
    num_espresso_machines: int = 3     # Espresso Shots
    
    # Probabilities for order types
    prob_order_coffee: float = 0.80
    prob_order_espresso: float = 1 - prob_order_coffee 
    prob_order_hot_food: float = 0.15

    # 3. Timing (Minutes)
    # Average 1rvice times
    mean_cashier_time: float = 1.5
    mean_dt_order_time: float = 1.0
    mean_kitchen_time: float = 3.5
    mean_pack_time: float = 1.0
    mean_espresso_time: float = 2.0
    brew_time: float = 5.0
    
    # Arrivals (Customers per Hour -> Converted to Inter-arrival mins)
    lambda_walkin: float = 40.0
    lambda_drivethru: float = 50.0
    lambda_mobile: float = 20.0
    
    # Patience
    mobile_patience: float = 15.0      # Mins before reneging

    # 4. Financials
    avg_revenue: float = 9.50
    wage_per_min: float = 16.50 / 60.0 # $16.50/hr
    penalty_balk: float = 5.00
    penalty_renege: float = 10.00
    cost_material_pct: float = 0.30    # 30% of revenue
    
    def get_inter_arrival(self, rate_per_hr):
        if rate_per_hr <= 0: return float('inf')
        return random.expovariate(rate_per_hr / 60.0)

# --- B. Enums & Domain Objects ---
class Channel(Enum):
    WALK_IN = auto()
    DRIVE_THRU = auto()
    MOBILE = auto()

class EventType(Enum):
    ARRIVAL = auto()
    PAYMENT_DONE = auto()
    KITCHEN_DONE = auto()
    PACKING_DONE = auto()
    PICKUP = auto()
    BREW_COMPLETE = auto()
    RENEGE_CHECK = auto()

@dataclass
class Customer:
    id: int
    channel: Channel
    arrival_time: float

    needs_coffee: bool
    needs_espresso: bool
    needs_hot_food: bool
    # State Tracking
    is_ready: bool = False     # Food is on shelf
    has_reneged: bool = False  # Gave up waiting
    has_balked: bool = False   # Never entered