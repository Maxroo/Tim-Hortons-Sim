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
    # Debug flag - set to True to enable debug output
    debug_mode: bool = False
    debug_interval: float = 60.0  # Print debug info every N minutes
    
    # Packing Priority Policy
    priority_packing: str = None  # If True: Walk-in and Drive-thru immediate pickup, Mobile has lag
                                   # If False: Normal FIFO order (all channels same)
    
    
    # Simulation Control
    warm_up_period: float = 30.0  # Warm-up period in minutes (data not recorded)
    
    # 1. Staffing (Decision Variables)
    num_cashiers: int = 2 # required M/M/1
    num_packers: int = 2 # required M/M/1
    num_cooks: int = 3
    num_bussers: int = 1               # Staff for cleaning tables
    
    num_dt_stations: int = 1 # required M/M/1


    num_default_cashiers: int = 2
    num_default_packers: int = 2
    num_default_cooks: int = 3
    num_default_bussers: int = 1
    # 2. Capacity Constraints
    max_drive_thru_queue: int = 10     # Cars
    pickup_shelf_capacity: int = 10    # Bags
    coffee_urn_size: int = 30          # Portions per urn
    num_coffee_urns: int = 2           # Number of coffee urns
    num_espresso_machines: int = 3     # Espresso Shots
    seating_capacity: int = 30         # Number of seats in dining area
    no_seat_penalty: float = 1.0        # Penalty cost per customer dissatisfied due to no seating available
    # Probabilities for order types
    prob_order_coffee: float = 0.80
    prob_order_espresso: float = 1 - prob_order_coffee 
    prob_order_hot_food: float = 0.15
    
    # Quantity distribution (weighted random selection)
    order_quantities: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])  # Possible quantities
    quantity_weights: List[float] = field(default_factory=lambda: [0.4, 0.3, 0.15, 0.1, 0.05])  # Weights for 1-5 (1 and 2 are most common)

    # 3. Timing (Minutes)
    # Average 1rvice times
    mean_cashier_time: float = 1.5 # 90 seconds
    mean_dt_order_time: float = 0.5 # 30 seconds
    mean_kitchen_time: float = 3.5
    mean_pack_time: float = 1
    mean_espresso_time: float = 0.5 
    brew_time: float = 5.0
    mean_dining_time: float = 15.0     # Average time customers spend eating
    mean_cleaning_time: float = 2.0   # Average time to clean a table
    
    other_pickup_delay_mean: float = 2.0  # Mean pickup delay for Walk-in and Drive-thru
    other_pickup_delay_std: float = 1.0   # Stddev of pickup delay for Walk-in and Drive-thru
    mobile_pickup_delay_mean: float = 5.0  # Mean pickup delay for Mobile orders
    mobile_pickup_delay_std: float = 2.0   # Stddev of pickup delay for Mobile orders
    
    # Arrivals (Customers per Hour -> Converted to Inter-arrival mins)
    # store hours
    opening_time: float = 5.0   # Store opening time (5 AM)
    closing_time: float = 21.0  # Store closing time (9 PM) 
    last_order_time: float = closing_time - 0.5  # Last order accepted at 8:30 PM
    # arrival rates
    peak_hours = [(6,9), (11,14)] # 6-9am, 11am-2pm
    # peak should be 140 per hour
    # Normal 80 per hour
    lambda_walkin: float = 40#40.0
    lambda_drivethru: float =20# 50.0
    lambda_mobile: float = 20.0
    
    peak_lambda_walkin: float = 60.0
    peak_lambda_drivethru: float = 50.0
    peak_lambda_mobile: float = 30.0
    
    # Patience
    mobile_patience: float = 30.0      # Mins before reneging
    drive_thru_patience: float = 10.0  # goal 90th percentile <= 10 mins
    walkin_patience: float = 30.0      # Mins before reneging
    # 4. Financials
    
    # staff wages
    labour_cost_per_hour: float = 18.00  # Average labour cost per hour
    
    # Item prices (per unit) - selling price
    price_coffee: float = 2.50      # Selling price per coffee
    price_espresso: float = 4.00    # Selling price per espresso drink
    price_hot_food: float = 5.00    # Selling price per hot food item
    
    # Item costs (per unit) - material cost
    cost_coffee: float = 0.75       # Material cost per coffee
    cost_espresso: float = 1.20     # Material cost per espresso drink
    cost_hot_food: float = 1.50     # Material cost per hot food item
    
    # Revenue (profit) = price - cost (calculated, not stored)
    
    penalty_balk: float = 5.00
    penalty_renege: float = 10.00
    penalty_percentage: float = 0.1  # Penalty for abandoned orders (% of order revenue)
    cost_material_pct: float = 0.30    # Deprecated: use item costs instead
    
    def get_inter_arrival(self, rate_per_hr):
        if rate_per_hr <= 0: return float('inf')
        return random.expovariate(rate_per_hr / 60.0)

    # --- Staffing helpers ---
    def is_peak_hour(self, hour_float: float) -> bool:
        """
        Returns True if the given hour (in store-local hours) falls inside any peak window.
        peak_hours should be a list of (start_hour, end_hour) tuples. If peak_hours is None, returns False.
        """
        if not self.peak_hours:
            return False
        return any(start <= hour_float < end for start, end in self.peak_hours)

    def staffing_for_hour(self, hour_float: float) -> dict:
        """
        Returns a staffing dict for the given hour using peak values during peak windows,
        and default staffing otherwise.
        """
        if self.is_peak_hour(hour_float):
            return {
                'num_cashiers': self.num_cashiers,
                'num_packers': self.num_packers,
                'num_cooks': self.num_cooks,
                'num_bussers': self.num_bussers,
            }
        return {
            'num_cashiers': self.num_default_cashiers,
            'num_packers': self.num_default_packers,
            'num_cooks': self.num_default_cooks,
            'num_bussers': self.num_default_bussers,
        }

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
    DINING_DONE = auto()      # Customer finished eating
    CLEANING_DONE = auto()    # Table cleaned and ready

@dataclass
class Customer:
    id: int
    channel: Channel
    arrival_time: float

    needs_coffee: int = 0      # Number of coffee items (0-5)
    needs_espresso: int = 0    # Number of espresso items (0-5)
    needs_hot_food: int = 0    # Number of hot food items (0-5)
    # State Tracking
    is_ready: bool = False     # Food is on shelf
    has_reneged: bool = False  # Gave up waiting
    has_balked: bool = False   # Never entered
    # Timing checkpoints
    t_enter_kitchen: Optional[float] = None
    t_kitchen_start: Optional[float] = None
    t_kitchen_done: Optional[float] = None
    t_enter_packing: Optional[float] = None
    t_packing_start: Optional[float] = None
    t_packing_done: Optional[float] = None
    t_pickup: Optional[float] = None