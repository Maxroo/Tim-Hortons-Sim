from dataclasses import dataclass, field
from typing import Dict

@dataclass
class SimulationConfig:
    """
    Central configuration object for the Tim Hortons Digital Twin.
    All time units are in MINUTES.
    """
    # ==========================================
    # M/M/1 as required 
    num_cashiers: int = 1
    num_packers: int = 1
    num_cashiers_drive_thru: int = 1
    # ==========================================
    # 1. RESOURCE ALLOCATION (Decision Variables)
    # ==========================================
    
    num_cooks: int = 3
    num_bussers: int = 1  # For dining area cleaning
    
    # Equipment constraints
    num_coffee_urns: int = 2
    num_espresso_machines: int = 1

    # ==========================================
    # 2. CAPACITY & CONSTRAINTS
    # ==========================================
    # Max cars in line before new arrivals turn away (Balking)
    max_drive_thru_queue: int = 12 
    
    # Max bags/trays capable of sitting on the pass-through shelf (Blocking)
    pickup_shelf_capacity: int = 20 
    
    # Servings per urn before a refill cycle is triggered
    coffee_urn_size_portions: int = 40 

    # ==========================================
    # 3. STOCHASTIC TIMING (Distributions)
    # ==========================================
    # Arrivals (Lambda): Expected customers per hour
    # We convert these to inter-arrival minutes in the property methods below
    arrival_rate_walkin_per_hr: float = 30.0 
    arrival_rate_drivethru_per_hr: float = 20.0
    arrival_rate_mobile_per_hr: float = 20.0

    # Service Means (Mu) in Minutes
    mean_cashier_time: float = 1.5
    mean_kitchen_prep_time: float = 3.5
    mean_packing_time: float = 1.0
    mean_drive_thru_pickup_time: float = 1.0
    
    # Fixed Operational Times
    coffee_brew_time: float = 5.0 # Time to brew a new batch
    
    # Customer Patience (for Reneging/Balking)
    mobile_max_wait_tolerance: float = 15.0 # Mins before mobile user complains

    # ==========================================
    # 4. FINANCIALS (For Profit Function)
    # ==========================================
    # Revenue
    avg_order_value: float = 9.50 # CAD
    
    # Costs
    hourly_wage_staff: float = 16.50 # CAD
    cost_material_pct: float = 0.30 # 30% of revenue is food cost
    
    # Penalties (Operational definitions of "Lost Profit")
    penalty_balk: float = 5.00  # Opportunity cost of lost drive-thru car
    penalty_renege: float = 12.00 # Cost of refund + bad will for mobile user
    penalty_waste: float = 2.00 # Cost per wasted food item

    # ==========================================
    # 5. SIMULATION CONTROLS
    # ==========================================
    random_seed: int = 42
    warm_up_period: float = 60.0 # Minutes to run before recording stats
    sim_duration: float = 480.0  # 8 hours shift

    # ==========================================
    # HELPER METHODS (Computed Properties)
    # ==========================================
    @property
    def inter_arrival_walkin(self) -> float:
        """Returns avg minutes between walk-in arrivals (1/lambda)"""
        if self.arrival_rate_walkin_per_hr == 0: return float('inf')
        return 60.0 / self.arrival_rate_walkin_per_hr

    @property
    def inter_arrival_drivethru(self) -> float:
        """Returns avg minutes between drive-thru arrivals"""
        if self.arrival_rate_drivethru_per_hr == 0: return float('inf')
        return 60.0 / self.arrival_rate_drivethru_per_hr

    @property
    def inter_arrival_mobile(self) -> float:
        """Returns avg minutes between mobile arrivals"""
        if self.arrival_rate_mobile_per_hr == 0: return float('inf')
        return 60.0 / self.arrival_rate_mobile_per_hr

    def total_labor_cost(self) -> float:
        """Calculates total labor cost for the shift duration"""
        total_staff = (self.num_cashiers + self.num_cooks + 
                       self.num_packers + self.num_bussers)
        hours = self.sim_duration / 60.0
        return total_staff * self.hourly_wage_staff * hours