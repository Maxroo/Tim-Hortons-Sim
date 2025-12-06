from tim import * 


def run_scenario():
    # 1. Setup Config
    config = SimulationConfig()
    
    # 2. Init Simulation
    sim = TimHortonsSim(config)
    
    # 3. Seed initial arrivals
    sim.schedule(0, EventType.ARRIVAL, Customer(1, Channel.WALK_IN, 0, True, False, True))
    sim.schedule(0, EventType.ARRIVAL, Customer(2, Channel.DRIVE_THRU, 0, True, False, True))
    sim.schedule(0, EventType.ARRIVAL, Customer(3, Channel.MOBILE, 0, False, True, False))
    
    # 4. Run
    print("Starting Simulation...")
    sim.run(480) # 8 Hours
    
    # 5. Report
    report = sim.stats.generate_report(480)
    sim.stats.print_table_report(report)

if __name__ == "__main__":
    run_scenario()