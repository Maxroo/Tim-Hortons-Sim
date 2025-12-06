# Tim Hortons Operations Simulator
A Discrete Event Simulation (DES) that models the daily operations of a Tim Hortons franchise. This project simulates customer flow, kitchen bottlenecks, and resource constraints to determine the most profit-maximizing staffing configuration.

# Project Overview
This simulation tracks customers through three distinct channels:

Walk-In: Standard counter service.

Drive-Thru: Subject to "balking" (cars leaving if the line is too long).

Mobile Orders: Subject to "reneging" (customers cancelling if wait time exceeds patience).

The goal is to optimize Daily Profit by balancing labor costs against revenue lost due to long wait times and wasted food.

# Project Structure
main.py: Execution loop.

simulationConfig.py: Contains the SimulationConfig class and parameters.

simulationEngine.py: Contains base of the Simulation Engine

tim.py: Logic of tims simulation engine. 

stats.py: Handles data collection and report generation.

README.md: This file.

# Configuration & Experiments
All simulation parameters are located in the SimulationConfig class. You can modify these values to test different scenarios.

Decision Variables:
num_cashiers = 1          # Front counter staff
num_cooks = 3             # Kitchen staff
num_espresso_machines = 1 # Latte/Cappuccino machines
num_packers = 1           # Staff putting food in bags
...
