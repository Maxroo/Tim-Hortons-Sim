import numpy as np # Optional, for percentiles. Or use statistics module.
from simulationConfig import *
from collections import defaultdict
from tabulate import tabulate

class Statistics:
    def __init__(self, config):
        self.cfg = config
        self.time = 0.0
        # --- Financial Counters ---
        self.waste_count = 0  # Food made but not eaten
        self.total_revenue = 0.0
        self.balk_count = 0
        self.renege_count = 0

        # --- 1. Throughput (Count by Channel) ---
        self.throughput = {
            Channel.WALK_IN: 0, 
            Channel.DRIVE_THRU: 0, 
            Channel.MOBILE: 0
        }
        
        # --- Time Tracking (Lists for distributions) ---
        # We need lists to calculate 90th percentile later
        self.wait_times = {
            Channel.WALK_IN: [],
            Channel.DRIVE_THRU: [],
            Channel.MOBILE: []
        }

        self.usage = {
            'CASHIER': 0.0,
            'DRIVE_THRU': 0.0,
            'COOK': 0.0,
            'PACKER': 0.0,
            'ESPRESSO': 0.0
        }

        # --- Resource Usage (Accumulators) ---
        # We track total minutes resources were active
        self.busy_minutes_cooks = 0.0
        self.busy_minutes_espresso = 0.0

    def record_waste(self):
        self.waste_count += 1

    def record_success(self, channel, wait_time, revenue):
        self.throughput[channel] += 1
        self.wait_times[channel].append(wait_time)
        self.total_revenue += revenue

    def record_balk(self):
        self.balk_count += 1

    def record_renege(self):
        self.renege_count += 1

    def record_usage(self, resource, duration):
        self.usage[resource] += duration

    def record_time(self, time):
        self.time = time

    def generate_report(self, sim_duration):
        report = {}
        
        # A. Throughput
        report['throughput_total'] = sum(self.throughput.values())
        report['throughput_breakdown'] = self.throughput
        
        # B. Wait Times (Avg + Tail)
        for channel, times in self.wait_times.items():
            if not times:
                report[f'wait_{channel.name}_avg'] = 0
                report[f'wait_{channel.name}_p95'] = 0
            else:
                report[f'wait_{channel.name}_avg'] = np.mean(times)
                report[f'wait_{channel.name}_p95'] = np.percentile(times, 95) # Tail
        
        # C. Utilization (Busy Time / (Duration * Capacity))
        # Note: You pass capacity in from Config
        caps = {
            'CASHIER': self.cfg.num_cashiers,
            'COOK': self.cfg.num_cooks,
            'PACKER': self.cfg.num_packers,
            'ESPRESSO': self.cfg.num_espresso_machines,
            'DRIVE_THRU': self.cfg.num_dt_stations
        }
        
        for res, minutes in self.usage.items():
            total_available_minutes = sim_duration * caps[res]
            util = minutes / total_available_minutes if total_available_minutes > 0 else 0
            report[f'util_{res}'] = util
            
        # D. Waste & Profit
        # Waste Cost = Material Cost of the food thrown away
        cost_waste = self.waste_count * (self.cfg.avg_revenue * self.cfg.cost_material_pct)
        
        report['waste_items'] = self.waste_count
        report['cost_waste'] = cost_waste
        report['total_revenue'] = self.total_revenue
        report['balk_count'] = self.balk_count
        report['renege_count'] = self.renege_count
        report['time_simulated'] = self.time
        return report

    def print_table_report(self, report):
        # 1. Prepare the data container
        table_data = []
        
        # 2. Loop through every item in the dictionary
        # We sort keys alphabetically so the table is easier to scan
        for key, value in sorted(report.items()):
            
            # 3. Format the Value based on its Type
            if isinstance(value, float):
                # If it's a float, round it to 4 decimal places
                formatted_value = f"{value:.4f}"
                
            elif isinstance(value, dict):
                # If it's a nested dictionary (like breakdown), make it a string
                # e.g., {'WALK_IN': 10, ...} -> "WALK_IN: 10, ..."
                formatted_value = ", ".join([f"{k.name}: {v}" for k, v in value.items()])
                
            else:
                # Integers or Strings
                formatted_value = str(value)
                
            # 4. Add row to table data
            table_data.append([key, formatted_value])

            # 5. Print using Tabulate
        print("\n" + "="*40)
        print("      FULL SIMULATION REPORT")
        print("="*40)
        print(tabulate(table_data, headers=["Metric Key", "Value"], tablefmt="fancy_grid"))