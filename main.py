from tim import * 


def run_scenario():
    # 1. Setup Config
    config = SimulationConfig()
    # Enable debug mode to see queue states
    config.debug_mode = True  # Set to False to disable debug output
    config.debug_interval = 30.0  # Print every 30 minutes
    
    # 2. Init Simulation
    sim = TimHortonsSim(config)
    
    # 3. Seed initial arrivals
    sim.schedule(0, EventType.ARRIVAL, Customer(1, Channel.MOBILE, 0, 0, 2, 0))  # 2 espressos
    sim.schedule(0, EventType.ARRIVAL, Customer(2, Channel.WALK_IN, 0, 2, 0, 1))  # 2 coffees, 1 hot food
    sim.schedule(0, EventType.ARRIVAL, Customer(3, Channel.DRIVE_THRU, 0, 1, 0, 1))  # 1 coffee, 1 hot food
    
    
    # 4. Run
    print("Starting Simulation...")
    sim.run(480) # 8 Hours
    
    # 5. Report
    report = sim.stats.generate_report(480)
    sim.stats.print_table_report(report)

if __name__ == "__main__":
    run_scenario()