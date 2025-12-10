"""
Experiment Runner for Tim Hortons Simulation
Runs multiple scenarios with different variable combinations and random seeds.
Collects statistics for cross-replication analysis.
"""

import json
import csv
from itertools import product
from tim import *
from datetime import datetime


class ExperimentRunner:
    def __init__(self):
        self.results = []
        self.experiment_config = None
        
    def define_experiment(self, variables_dict, num_replications=5, sim_duration=480):
        """
        Define experiment variables and their values.
        
        Args:
            variables_dict: Dictionary of variable names and their possible values
                Example: {
                    'num_cooks': [3, 4, 5],
                    'num_packers': [1, 2],
                    'lambda_walkin': [20, 30, 40]
                }
            num_replications: Number of random seeds per scenario (default: 5)
            sim_duration: Simulation duration in minutes (default: 480 = 8 hours)
        """
        self.experiment_config = {
            'variables': variables_dict,
            'num_replications': num_replications,
            'sim_duration': sim_duration
        }
        
    def generate_scenarios(self):
        """Generate all combinations of variable values."""
        if not self.experiment_config:
            raise ValueError("Must define experiment first using define_experiment()")
        
        variables = self.experiment_config['variables']
        var_names = list(variables.keys())
        var_values = list(variables.values())
        
        scenarios = []
        for combination in product(*var_values):
            scenario = dict(zip(var_names, combination))
            scenarios.append(scenario)
        
        return scenarios
    
    def run_single_scenario(self, scenario, seed, sim_duration):
        """Run a single simulation with given scenario and random seed."""
        # Create base config
        config = SimulationConfig()
        
        # Apply scenario variables to config
        for var_name, var_value in scenario.items():
            if hasattr(config, var_name):
                setattr(config, var_name, var_value)
            else:
                print(f"Warning: Variable '{var_name}' not found in SimulationConfig")
        
        # Set random seed
        config.random_seed = seed
        
        # Initialize simulation
        sim = TimHortonsSim(config)
        
        # Seed initial arrivals
        sim.schedule(0, EventType.ARRIVAL, Customer(1, Channel.MOBILE, 0, 0, 2, 0))
        sim.schedule(0, EventType.ARRIVAL, Customer(2, Channel.WALK_IN, 0, 2, 0, 1))
        sim.schedule(0, EventType.ARRIVAL, Customer(3, Channel.DRIVE_THRU, 0, 1, 0, 1))
        
        # Run simulation
        sim.run(sim_duration)
        
        # Collect statistics
        report = sim.stats.generate_report(sim_duration)
        
        return report
    
    def run_experiment(self, output_file, verbose=True):
        """
        Run all scenarios with multiple replications.
        
        Args:
            output_file: Output CSV file path
            verbose: Print progress if True
        """
        if not self.experiment_config:
            raise ValueError("Must define experiment first using define_experiment()")
        
        scenarios = self.generate_scenarios()
        num_replications = self.experiment_config['num_replications']
        sim_duration = self.experiment_config['sim_duration']
        
        total_runs = len(scenarios) * num_replications
        current_run = 0
        
        print(f"Starting Experiment")
        print(f"  Total scenarios: {len(scenarios)}")
        print(f"  Replications per scenario: {num_replications}")
        print(f"  Total runs: {total_runs}")
        print(f"  Simulation duration: {sim_duration} minutes ({sim_duration/60:.1f} hours)")
        print("-" * 60)
        
        for scenario_idx, scenario in enumerate(scenarios, 1):
            if verbose:
                print(f"\nScenario {scenario_idx}/{len(scenarios)}: {scenario}")
            
            for rep in range(1, num_replications + 1):
                current_run += 1
                seed = rep  # Use replication number as seed (1, 2, 3, ...)
                
                if verbose:
                    print(f"  Run {rep}/{num_replications} (Seed: {seed}) [{current_run}/{total_runs}]", end=" ... ")
                
                try:
                    report = self.run_single_scenario(scenario, seed, sim_duration)
                    
                    # Convert report to JSON-serializable format
                    serializable_report = self.convert_to_json_serializable(report)
                    
                    # Add scenario and replication info to report
                    result = {
                        'scenario_id': scenario_idx,
                        'replication': rep,
                        'random_seed': seed,
                        **scenario,  # Include all scenario variables
                        **serializable_report     # Include all statistics
                    }
                    
                    self.results.append(result)
                    
                    if verbose:
                        print("✓")
                        
                except Exception as e:
                    if verbose:
                        print(f"✗ Error: {e}")
                    result = {
                        'scenario_id': scenario_idx,
                        'replication': rep,
                        'random_seed': seed,
                        **scenario,
                        'error': str(e)
                    }
                    self.results.append(result)
        
        # Save results
        self.save_results(output_file)
        
        print(f"\n{'='*60}")
        print(f"Experiment completed!")
        print(f"  Results saved to: {output_file}")
        print(f"  Total successful runs: {len([r for r in self.results if 'error' not in r])}")
        print(f"  Total failed runs: {len([r for r in self.results if 'error' in r])}")
        print(f"{'='*60}")
        
        return self.results
    
    def save_results(self, output_file):
        """Save results to CSV file."""
        if not self.results:
            print("No results to save")
            return
        
        # Get all unique keys from all results
        all_keys = set()
        for result in self.results:
            all_keys.update(result.keys())
        
        # Sort keys: scenario info first, then variables, then statistics
        scenario_keys = ['scenario_id', 'replication', 'random_seed']
        variable_keys = sorted([k for k in all_keys if k in self.experiment_config['variables']])
        stat_keys = sorted([k for k in all_keys if k not in scenario_keys and k not in variable_keys and k != 'error'])
        
        fieldnames = scenario_keys + variable_keys + stat_keys
        if 'error' in all_keys:
            fieldnames.append('error')
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                row = {key: result.get(key, '') for key in fieldnames}
                writer.writerow(row)
    
    def convert_to_json_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, dict):
            # Convert dict keys if they are enums
            result = {}
            for key, value in obj.items():
                # Convert enum keys to strings
                if hasattr(key, 'name'):  # Enum type
                    new_key = key.name
                else:
                    new_key = str(key)
                # Recursively convert values
                result[new_key] = self.convert_to_json_serializable(value)
            return result
        elif isinstance(obj, list):
            return [self.convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, 'name'):  # Enum type
            return obj.name
        elif isinstance(obj, (int, float, str, bool)) or obj is None:
            return obj
        else:
            # Try to convert to string for other types
            return str(obj)
    
    def save_results_json(self, output_file='experiment_results.json'):
        """Save results to JSON file (alternative format)."""
        # Convert results to JSON-serializable format
        serializable_results = [self.convert_to_json_serializable(result) for result in self.results]
        
        output = {
            'experiment_config': self.experiment_config,
            'timestamp': datetime.now().isoformat(),
            'results': serializable_results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Results also saved to JSON: {output_file}")


def example_experiment():
    """Example experiment configuration."""
    runner = ExperimentRunner()
    
    # Define variables to test
    variables = {
        'num_cooks': [3],
        'num_packers': [1, 2],
        'lambda_walkin': [20]  # Reduced for faster testing
    }
    
    # Define experiment
    runner.define_experiment(
        variables_dict=variables,
        num_replications=5,  # 5 different random seeds per scenario
        sim_duration=480    # 8 hours
    )
    
    # Run experiment
    runner.run_experiment(
        output_file='example_experiment_results.csv',
        verbose=True
    )
    
    # Also save as JSON
    runner.save_results_json('example_experiment_results.json')
    
    return runner


if __name__ == "__main__":
    
    runner = ExperimentRunner()
    
    runner.define_experiment(
        variables_dict={
            # ===== STAFFING VARIABLES =====
            'num_cashiers': [2, 4, 6, 8],              # Front counter staff
            'num_packers': [2, 4, 6],               # Staff putting food in bags
            'num_cooks': [3, 5, 7],           # Kitchen staff
            'num_bussers': [1, 3],               # Staff for cleaning tables

            # 'num_dt_stations': [1, 2, 3, 4, 5],           # Drive-thru order stations
            
            # ===== CAPACITY CONSTRAINTS =====
            'pickup_shelf_capacity': [5,10,20], # Bags on shelf
            'coffee_urn_size': [30, 60],     # Coffee portions
            'num_espresso_machines': [1, 3],  # Espresso machines

            # 'max_drive_thru_queue': [8, 10, 12], # Max cars in drive-thru
            # 'seating_capacity': [25, 30, 35],    # Dining area seats
            
            # # ===== ARRIVAL RATES (customers per hour) =====
            # 'lambda_walkin': [20, 30, 40],       # Walk-in arrival rate (normal)
            # 'lambda_drivethru': [20, 30, 40, 50], # Drive-thru arrival rate (normal)
            # 'lambda_mobile': [10, 20, 30],        # Mobile order arrival rate (normal)
            # 'peak_lambda_walkin': [60, 70, 80],  # Walk-in arrival rate (peak hours)
            # 'peak_lambda_drivethru': [40, 50, 60], # Drive-thru arrival rate (peak hours)
            # 'peak_lambda_mobile': [15, 20, 25],  # Mobile order arrival rate (peak hours)
            
            # ===== TIMING (Average service times in minutes) =====
            'brew_time': [5.0, 10.0],              # Coffee brewing time
           
            # 'num_coffee_urns': [1, 3],          # Number of coffee urns
            # 'mean_cashier_time': [1.0, 1.5, 2.0],      # Cashier service time
            # 'mean_dt_order_time': [0.8, 1.0, 1.2],     # Drive-thru order time
            # 'mean_kitchen_time': [3.0, 3.5, 4.0],      # Kitchen preparation time
            # 'mean_pack_time': [0.8, 1.0, 1.2],         # Packing time
            # 'mean_espresso_time': [0.3, 0.5],     # Espresso making time
            # 'mean_dining_time': [12.0, 15.0, 18.0],    # Customer dining time
            # 'mean_cleaning_time': [1.5, 2.0, 2.5],     # Table cleaning time
            
            # # ===== PATIENCE =====
            # 'mobile_patience': [12.0, 15.0, 18.0],     # Mobile order patience (minutes)
            # 'drive_thru_patience': [8.0, 10.0, 12.0],  # Drive-thru patience (minutes)
            
            # # ===== ORDER PROBABILITIES =====
            # 'prob_order_coffee': [0.70, 0.80, 0.90],   # Probability of ordering coffee
            # 'prob_order_hot_food': [0.10, 0.15, 0.20], # Probability of ordering hot food
            
            # ===== PACKING PRIORITY POLICY =====
            'priority_packing': [None, "MOBILE", 'DRIVE_THRU'],         # Priority packing: True=Walk-in/DT immediate, Mobile lag; False=Normal FIFO
            
            # ===== FINANCIAL (pricing and costs) =====
            # 'price_coffee': [2.00, 2.50, 3.00],      # Selling price per coffee
            # 'price_espresso': [3.50, 4.00, 4.50],    # Selling price per espresso
            # 'price_hot_food': [4.50, 5.00, 5.50],    # Selling price per hot food
            # 'cost_coffee': [0.60, 0.75, 0.90],       # Material cost per coffee
            # 'cost_espresso': [1.00, 1.20, 1.40],     # Material cost per espresso
            # 'cost_hot_food': [1.20, 1.50, 1.80],     # Material cost per hot food
            # 'labour_cost_per_hour': [16.00, 18.00, 20.00], # Average labour cost
            # 'penalty_balk': [4.00, 5.00, 6.00],       # Penalty for balking
            # 'penalty_renege': [8.00, 10.00, 12.00],   # Penalty for reneging
            # 'penalty_percentage': [0.08, 0.10, 0.12], # Penalty % for abandoned orders
            
            # ===== STORE HOURS (if implementing dynamic hours) =====
            # 'opening_time': [5.5, 6.0, 6.5],         # Store opening time (hours)
            # 'closing_time': [20.5, 21.0, 21.5],     # Store closing time (hours)
        },
        num_replications=5,  # More replications for better statistics
        sim_duration=960
    )
    runner.run_experiment('experiment_results_v7.csv')

