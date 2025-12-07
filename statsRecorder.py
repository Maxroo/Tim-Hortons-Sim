import numpy as np # Optional, for percentiles. Or use statistics module.
from SimulationConfig import *
from collections import defaultdict
from tabulate import tabulate

class Statistics:
    def __init__(self, config):
        self.cfg = config
        self.time = 0.0
        # --- Financial Counters ---
        self.waste_count = 0  # Food made but not eaten
        self.total_waste_cost = 0.0  # Total material cost of wasted items
        self.total_sales_price = 0.0  # Total selling price (revenue from sales)
        # self.total_revenue = 0.0  # Deprecated: use total_sales_price instead
        self.balk_count = 0
        self.renege_count = 0
        self.no_seat_count = 0  # Walk-in customers who couldn't find a seat

        # count of total arrivals
        self.total_arrivals = { 
            Channel.WALK_IN: 0, 
            Channel.DRIVE_THRU: 0,
            Channel.MOBILE: 0
        }

        # count Throughput (Count by Channel), how many order completed. 
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
            'ESPRESSO': 0.0,
            'BUSSER': 0.0
        }

        self.queue_lengths = {
            'CASHIER': 0, 
            'DRIVE_THRU': 0,
            'KITCHEN': 0,
            'PACKING': 0    
        }

        # --- Resource Usage (Accumulators) ---
        # We track total minutes resources were active
        self.busy_minutes_cooks = 0.0
        self.busy_minutes_espresso = 0.0
    
    def record_queue_length(self, queue_name, length):
        self.queue_lengths[queue_name] = length

    def record_arrival(self, channel):
        self.total_arrivals[channel] += 1

    def record_waste(self, customer=None, waste_cost=0.0):
        """Record wasted items. Records the material cost of wasted items."""
        self.waste_count += 1
        if waste_cost > 0:
            self.total_waste_cost += waste_cost
        elif customer:
            # Calculate waste cost from customer order if not provided
            waste_cost = (customer.needs_coffee * self.cfg.cost_coffee +
                         customer.needs_espresso * self.cfg.cost_espresso +
                         customer.needs_hot_food * self.cfg.cost_hot_food)
            self.total_waste_cost += waste_cost

    def record_success(self, channel, wait_time, sales_price):
        self.throughput[channel] += 1
        self.wait_times[channel].append(wait_time)
        self.total_sales_price += sales_price
        # self.total_revenue += sales_price  # Keep for backward compatibility

    def record_balk(self):
        self.balk_count += 1

    def record_renege(self):
        self.renege_count += 1
    
    def record_no_seat(self):
        """Record walk-in customer who couldn't find a seat."""
        self.no_seat_count += 1

    def record_usage(self, resource, duration):
        self.usage[resource] += duration

    def record_time(self, time):
        self.time = time

    def generate_report(self, sim_duration):
        report = {}
        
        # A. Throughput
        report['arrival_total'] = sum(self.total_arrivals.values())
        report['arrival_breakdown'] = self.total_arrivals

        report['throughput_total'] = sum(self.throughput.values())
        report['throughput_breakdown'] = self.throughput

        report['queue_lengths'] = sum(self.queue_lengths.values())
        report['queue_breakdown'] = self.queue_lengths
        
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
            'DRIVE_THRU': self.cfg.num_dt_stations,
            'BUSSER': self.cfg.num_bussers
        }
        
        for res, minutes in self.usage.items():
            total_available_minutes = sim_duration * caps[res]
            util = minutes / total_available_minutes if total_available_minutes > 0 else 0
            report[f'util_{res}'] = util
            
        # D. Waste & Profit
        # Waste Cost = Material Cost of the food thrown away (direct cost, not revenue-based)
        report['waste_items'] = self.waste_count
        report['cost_waste'] = self.total_waste_cost
        report['total_sales_price'] = self.total_sales_price  # Total selling price
        report['total_profit'] = self.total_sales_price - self.total_waste_cost  # Profit = Sales Price - Waste Cost
        # report['total_revenue'] = self.total_revenue  # Deprecated: kept for backward compatibility
        report['balk_count'] = self.balk_count
        report['renege_count'] = self.renege_count
        report['no_seat_count'] = self.no_seat_count  # Walk-in customers who couldn't find a seat
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
                formatted_value = ", ".join([f"{k}: {v}" for k, v in value.items()])
                
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