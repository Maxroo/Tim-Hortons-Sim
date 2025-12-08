from simulationEngine import *
from statsRecorder import *

class TimHortonsSim(SimEngine):
    def __init__(self, config: SimulationConfig):
        super().__init__()
        self.cfg = config
        random.seed(self.cfg.random_seed)

        # --- Customer Counter ---
        self.customer_counter = 3 # take into account with initial arrivals
        # --- Queues (FIFO) ---
        self.q_walkin = deque()      # People inside
        self.q_drivethru = deque()   # Cars outside
        self.q_kitchen = deque()     # Orders (Shared)
        self.q_packing = deque()     # Food waiting to be packed
        
        # --- Resources (Counters) ---
        self.busy_cashiers = 0
        self.busy_dt_stations = 0
        self.busy_cooks = 0
        self.busy_packers = 0
        self.busy_espresso_machines = 0
        self.busy_bussers = 0
        
        # --- Complex Resources ---
        self.coffee_level = config.coffee_urn_size
        self.is_brewing = False
        self.shelf_occupancy = 0
        self.seating_occupancy = 0  # Number of occupied seats
        self.dirty_tables = deque()  # Queue of tables waiting to be cleaned
        
        # --- Stats ---
        self.stats = Statistics(config)
        
        # --- Debug ---
        self.last_debug_time = 0.0  # Track last debug output time

    # ==========================
    # DEBUG FUNCTION 
    # ==========================
    def debug_print_state(self):
        """Print current queue and resource state for debugging."""
        if not self.cfg.debug_mode:
            return
        
        # Only print at intervals
        if self.clock - self.last_debug_time < self.cfg.debug_interval:
            return
        
        self.last_debug_time = self.clock
        
        print(f"\n{'='*60}")
        print(f"DEBUG: Time = {self.clock:.2f} minutes ({self.clock/60:.2f} hours)")
        print(f"{'='*60}")
        print(f"QUEUE LENGTHS:")
        print(f"  Walk-in:     {len(self.q_walkin)}")
        print(f"  Drive-thru:  {len(self.q_drivethru)}")
        print(f"  Kitchen:     {len(self.q_kitchen)}")
        print(f"  Packing:     {len(self.q_packing)}")
        print(f"\nRESOURCE USAGE:")
        print(f"  Cashiers:    {self.busy_cashiers}/{self.cfg.num_cashiers}")
        print(f"  DT Stations: {self.busy_dt_stations}/{self.cfg.num_dt_stations}")
        print(f"  Cooks:       {self.busy_cooks}/{self.cfg.num_cooks}")
        print(f"  Packers:     {self.busy_packers}/{self.cfg.num_packers}")
        print(f"  Espresso:    {self.busy_espresso_machines}/{self.cfg.num_espresso_machines}")
        print(f"\nOTHER RESOURCES:")
        print(f"  Coffee Level: {self.coffee_level}/{self.cfg.coffee_urn_size} (Brewing: {self.is_brewing})")
        print(f"  Shelf Space:  {self.shelf_occupancy}/{self.cfg.pickup_shelf_capacity}")
        print(f"  Seating:      {self.seating_occupancy}/{self.cfg.seating_capacity} (Dirty tables: {len(self.dirty_tables)})")
        print(f"  Bussers:      {self.busy_bussers}/{self.cfg.num_bussers}")
        
        # Show oldest customer in each queue
        if self.q_kitchen:
            oldest_kitchen = min(self.q_kitchen, key=lambda c: c.arrival_time)
            wait_time = self.clock - oldest_kitchen.arrival_time
            print(f"\nOLDEST IN KITCHEN QUEUE:")
            print(f"  Customer ID: {oldest_kitchen.id}, Channel: {oldest_kitchen.channel.name}")
            print(f"  Arrived at: {oldest_kitchen.arrival_time:.2f}, Wait time: {wait_time:.2f} min")
        
        if self.q_packing:
            oldest_packing = min(self.q_packing, key=lambda c: c.arrival_time)
            wait_time = self.clock - oldest_packing.arrival_time
            print(f"\nOLDEST IN PACKING QUEUE:")
            print(f"  Customer ID: {oldest_packing.id}, Channel: {oldest_packing.channel.name}")
            print(f"  Arrived at: {oldest_packing.arrival_time:.2f}, Wait time: {wait_time:.2f} min")
        
        print(f"{'='*60}\n")

    def handle_event(self, evt):
        # DEBUG: Print state periodically
        self.debug_print_state()
        
        if evt.type == EventType.ARRIVAL:
            self.process_arrival(evt.customer)
        elif evt.type == EventType.PAYMENT_DONE:
            if evt.customer.channel == Channel.WALK_IN:
                self.process_walkin_done(evt.customer)
            elif evt.customer.channel == Channel.DRIVE_THRU:
                self.process_drivethru_done(evt.customer)
        elif evt.type == EventType.BREW_COMPLETE:
            self.process_brew_complete()
        elif evt.type == EventType.RENEGE_CHECK:
            self.process_renege_check(evt.customer)
        elif evt.type == EventType.KITCHEN_DONE:
            self.process_kitchen_done(evt.customer)
        elif evt.type == EventType.PACKING_DONE:
            self.process_packing_done(evt.customer)
        elif evt.type == EventType.PICKUP:
            self.process_pickup(evt.customer)
        elif evt.type == EventType.DINING_DONE:
            self.process_dining_done(evt.customer)
        elif evt.type == EventType.CLEANING_DONE:
            self.process_cleaning_done()

    # ==========================
    # 1. ARRIVAL LOGIC
    # ==========================
    def process_arrival(self, customer):
        self.schedule_next_arrival(customer.channel)

        # --- A. DRIVE-THRU LOGIC ---
        if customer.channel == Channel.DRIVE_THRU:
            # STRICT BALKING: Only check the vehicle queue
            # Cars waiting to order + Cars currently ordering
            cars_in_lane = len(self.q_drivethru) + self.busy_dt_stations
            
            if cars_in_lane >= self.cfg.max_drive_thru_queue:
                customer.has_balked = True
                self.stats.record_balk()
                return 
            
            # Enter the Lane
            self.q_drivethru.append(customer)
            self.schedule(self.cfg.drive_thru_patience, EventType.RENEGE_CHECK, customer)
            self.try_start_drivethru()
            self.stats.record_arrival(Channel.DRIVE_THRU)

        # --- B. MOBILE LOGIC ---
        elif customer.channel == Channel.MOBILE:
            # Goes straight to Kitchen
            self.q_kitchen.append(customer)
            self.schedule(self.cfg.mobile_patience, EventType.RENEGE_CHECK, customer)
            self.try_start_kitchen()
            self.stats.record_arrival(Channel.MOBILE)

        # --- C. WALK-IN LOGIC ---
        elif customer.channel == Channel.WALK_IN:
            # Enter the store line
            self.q_walkin.append(customer)
            self.try_start_walkin()
            self.stats.record_arrival(Channel.WALK_IN)


    # ==========================
    # 2. SERVICE LOGIC (Split)
    # ==========================
    
    # --- Walk-In Cashiers ---
    def try_start_walkin(self):
        # Only use Cashier Resources
        if self.busy_cashiers < self.cfg.num_cashiers and self.q_walkin:
            cust = self.q_walkin.popleft()
            self.busy_cashiers += 1
            
            duration = random.expovariate(1.0 / self.cfg.mean_cashier_time)
            self.stats.record_usage('CASHIER', duration)
            self.schedule(duration, EventType.PAYMENT_DONE, cust)
            

    def process_walkin_done(self, customer):
        self.busy_cashiers -= 1
        self.try_start_walkin() # Call "Next!"
        
        # Merge into Kitchen
        self.q_kitchen.append(customer)
        self.try_start_kitchen()

    # --- Drive-Thru Stations ---
    def try_start_drivethru(self):
        # Only use DT Station Resources
        if self.busy_dt_stations < self.cfg.num_dt_stations and self.q_drivethru:
            cust = self.q_drivethru.popleft()
            self.busy_dt_stations += 1
            duration = random.expovariate(1.0 / self.cfg.mean_dt_order_time)
            self.stats.record_usage('DRIVE_THRU', duration)
            self.schedule(duration, EventType.PAYMENT_DONE, cust)
            self.stats.record_arrival(Channel.DRIVE_THRU)

    def process_drivethru_done(self, customer):
        self.busy_dt_stations -= 1
        self.try_start_drivethru() # Next car pulls up to speaker
        
        # Merge into Kitchen
        self.q_kitchen.append(customer)
        self.try_start_kitchen()

    # ==========================
    # 3. KITCHEN LOGIC (The Hard Part)
    # ==========================
    def try_start_kitchen(self):
        """
        Attempts to start the next order.
        Requires handling multiple resource dependencies.
        """
        if not self.q_kitchen: return
        
        # 1. PRIMARY RESOURCE CHECK: We always need a human
        if self.busy_cooks >= self.cfg.num_cooks: 
            return

        # Peek at the next customer (don't remove yet)
        cust = self.q_kitchen[0]
        if cust.has_reneged:
            # Customer already left, remove order
            # Has not started making yet, so don't record waste or success
            self.q_kitchen.popleft()
            possible_revenue = self.calculate_order_revenue(cust)
            self.stats.record_penalties(possible_revenue * self.cfg.penalty_percentage)
            self.try_start_kitchen() # Check next order
            return
        
        # 2. SECONDARY RESOURCE CHECKS (Equipment/Ingredients)
        
        # Case A: Espresso Order (Needs Machine)
        if cust.needs_espresso > 0:
            if self.busy_espresso_machines >= self.cfg.num_espresso_machines:
                return # BLOCKED: Cook is free, but Machine is busy
        
        # Case B: Brewed Coffee Order (Needs Liquid)
        elif cust.needs_coffee > 0:
            if self.coffee_level < cust.needs_coffee:
                if not self.is_brewing:
                    self.start_brewing()
                return # BLOCKED: Cook is free, but Coffee is insufficient

        # 3. SEIZE RESOURCES (If we survived the checks)
        self.q_kitchen.popleft() # Now we commit
        
        self.busy_cooks += 1
        
        duration = 0.0

        if cust.needs_espresso > 0:
            self.busy_espresso_machines += 1
            # Espresso time scales with quantity (each takes mean_espresso_time)
            espressoDuration = sum([random.expovariate(1.0 / self.cfg.mean_espresso_time) 
                                     for _ in range(cust.needs_espresso)])
            duration += espressoDuration
            self.stats.record_usage('ESPRESSO', espressoDuration)

        if cust.needs_coffee > 0:
            self.coffee_level -= cust.needs_coffee
            # Pouring time scales with quantity (0.5 min per coffee)
            brewedDuration = 0.5 * cust.needs_coffee
            duration += brewedDuration

        if cust.needs_hot_food > 0:
            # Food time scales with quantity (each takes mean_kitchen_time)
            hotFoodDuration = sum([random.expovariate(1.0 / self.cfg.mean_kitchen_time) 
                                   for _ in range(cust.needs_hot_food)])
            self.stats.record_usage('COOK', hotFoodDuration)
            duration += hotFoodDuration

        if duration == 0:
            raise ValueError("Order has no items to prepare!")
        
        self.schedule(duration, EventType.KITCHEN_DONE, cust)

    def process_kitchen_done(self, customer):
        # 1. Free the Human
        self.busy_cooks -= 1
        
        # 2. Free the Machine (if used)
        if customer.needs_espresso > 0:
            self.busy_espresso_machines -= 1
            
        # 3. Pull next order
        self.try_start_kitchen()

        # 4. Move to Packing
        self.q_packing.append(customer)
        self.try_start_packing()

    def start_brewing(self):
        self.is_brewing = True
        # Schedule the "Refill" event in the future
        self.schedule(self.cfg.brew_time, EventType.BREW_COMPLETE)

    def process_brew_complete(self):
        self.coffee_level = self.cfg.coffee_urn_size
        self.is_brewing = False
        # Unblock kitchen
        self.try_start_kitchen()

    # ==========================
    # 4. PACKING LOGIC (Blocking)
    # ==========================
    def try_start_packing(self):
        # Constraint: Shelf Space
        if self.shelf_occupancy >= self.cfg.pickup_shelf_capacity:
            return # Blocked
            
        if self.busy_packers < self.cfg.num_packers and self.q_packing:
            cust = self.q_packing.popleft()
            
            if cust.has_reneged:
                # Customer reneged while in packing queue (before packing started)
                # Food is already made, so record waste
                waste_cost = self.calculate_order_cost(cust)
                self.stats.record_waste(cust, waste_cost)
                # Don't pack it, just free the shelf space (food was made but not packed)
                self.try_start_packing()
                return

            # Check again if customer reneged (might have reneged during wait)
            if cust.has_reneged:
                waste_cost = self.calculate_order_cost(cust)
                self.stats.record_waste(cust, waste_cost)
                self.try_start_packing()
                return
            
            self.busy_packers += 1
            duration = random.expovariate(1.0 / self.cfg.mean_pack_time)
            self.stats.record_usage('PACKER', duration)
            self.schedule(duration, EventType.PACKING_DONE, cust)

    def process_packing_done(self, customer):
        self.busy_packers -= 1
        
        # Put on shelf
        self.shelf_occupancy += 1
        customer.is_ready = True
        
        # Schedule Pickup
        # Walk-in: Immediate. Drive-thru: Immediate. Mobile: Random 1 -3 lag.
        lag = 0
        
        if customer.channel == Channel.MOBILE: lag = random.uniform(1, 3)
        
        self.schedule(lag, EventType.PICKUP, customer)
        self.try_start_packing() # Packer takes next

    # ==========================
    # 5. EXIT LOGIC
    # ==========================
    def process_pickup(self, customer):
        # 1. Always free the shelf space
        self.shelf_occupancy -= 1
        self.try_start_packing() # Unblock packer
        
        # 2. Check if this is a valid transaction
        if customer.has_reneged:
            # The customer left long ago. The food is cold.
            waste_cost = self.calculate_order_cost(customer)
            self.stats.record_waste(customer, waste_cost)
        else:
            # Successful transaction
            wait_time = self.clock - customer.arrival_time
            sales_price = self.calculate_order_price(customer)
            self.stats.record_success(
                customer.channel, 
                wait_time, 
                sales_price
            )
            
            # 3. For WALK_IN customers, they need a seat in the dining area
            if customer.channel == Channel.WALK_IN:
                if self.seating_occupancy < self.cfg.seating_capacity:
                    self.seating_occupancy += 1            
                    dining_duration = random.expovariate(1.0 / self.cfg.mean_dining_time)
                    self.schedule(dining_duration, EventType.DINING_DONE, customer)
                else:
                    # No seats available - customer leaves
                    self.stats.record_no_seat()

    def process_renege_check(self, customer):
        # If time is up and food isn't ready, and customer hasn't already reneged
        if not customer.is_ready and not customer.has_reneged:
            customer.has_reneged = True
            self.stats.record_renege()
    
    # ==========================
    # 6. DINING AREA LOGIC
    # ==========================
    def process_dining_done(self, customer):
        """Customer finished eating, leaves the table."""
        # Free the seat
        self.seating_occupancy -= 1
        
        # Table needs to be cleaned before reuse
        self.dirty_tables.append(customer)  # Track which table needs cleaning
        self.try_start_cleaning()
    
    def try_start_cleaning(self):
        """Start cleaning a dirty table if busser is available."""
        if self.busy_bussers >= self.cfg.num_bussers:
            return  # All bussers busy
        
        if not self.dirty_tables:
            return  # No dirty tables
        
        # Start cleaning
        table = self.dirty_tables.popleft()
        self.busy_bussers += 1
        
        cleaning_duration = random.expovariate(1.0 / self.cfg.mean_cleaning_time)
        self.stats.record_usage('BUSSER', cleaning_duration)
        self.schedule(cleaning_duration, EventType.CLEANING_DONE)
    
    def process_cleaning_done(self):
        """Table cleaning completed, table is now available."""
        self.busy_bussers -= 1
        # Table is now clean and available (seating_occupancy already decremented)
        # Try to clean next dirty table
        self.try_start_cleaning()
    
    def calculate_order_price(self, customer):
        """Calculate selling price (what customer pays) based on actual order items."""
        price = 0.0
        price += customer.needs_coffee * self.cfg.price_coffee
        price += customer.needs_espresso * self.cfg.price_espresso
        price += customer.needs_hot_food * self.cfg.price_hot_food
        return price
    
    def calculate_order_revenue(self, customer):
        """Calculate revenue (profit) based on actual order items. Revenue = Price - Cost."""
        revenue = 0.0
        revenue += customer.needs_coffee * (self.cfg.price_coffee - self.cfg.cost_coffee)
        revenue += customer.needs_espresso * (self.cfg.price_espresso - self.cfg.cost_espresso)
        revenue += customer.needs_hot_food * (self.cfg.price_hot_food - self.cfg.cost_hot_food)
        return revenue
    
    def calculate_order_cost(self, customer):
        """Calculate material cost based on actual order items."""
        cost = 0.0
        cost += customer.needs_coffee * self.cfg.cost_coffee
        cost += customer.needs_espresso * self.cfg.cost_espresso
        cost += customer.needs_hot_food * self.cfg.cost_hot_food
        return cost

    # --- Utility ---
    def schedule_next_arrival(self, channel):
        rate = 0
        # determine peak or normal rate
        current_hour = int(self.clock // 60) + self.cfg.opening_time
        if current_hour > self.cfg.last_order_time:
            return  # No more arrivals after last order time
        if any(start <= current_hour < end for start, end in self.cfg.peak_hours):
            if channel == Channel.WALK_IN: rate = self.cfg.peak_lambda_walkin
            elif channel == Channel.DRIVE_THRU: rate = self.cfg.peak_lambda_drivethru
            elif channel == Channel.MOBILE: rate = self.cfg.peak_lambda_mobile
        else:
            if channel == Channel.WALK_IN: rate = self.cfg.lambda_walkin
            elif channel == Channel.DRIVE_THRU: rate = self.cfg.lambda_drivethru
            elif channel == Channel.MOBILE: rate = self.cfg.lambda_mobile
        delay = self.cfg.get_inter_arrival(rate)
    
        # Create new customer
        new_id = self.customer_counter + 1
        self.customer_counter = new_id
        
        # Generate quantities (0-5) for each item type with weighted distribution
        # Coffee and espresso are mutually exclusive (either coffee or espresso, not both)
        if random.random() < self.cfg.prob_order_coffee:
            needs_coffee = random.choices(self.cfg.order_quantities, weights=self.cfg.quantity_weights)[0]
            needs_espresso = 0
        else:
            needs_coffee = 0
            needs_espresso = random.choices(self.cfg.order_quantities, weights=self.cfg.quantity_weights)[0]
        
        needs_hot_food = random.choices(self.cfg.order_quantities, weights=self.cfg.quantity_weights)[0] if random.random() < self.cfg.prob_order_hot_food else 0

        new_cust = Customer(new_id, channel, self.clock + delay, needs_coffee, needs_espresso, needs_hot_food)
        self.schedule(delay, EventType.ARRIVAL, new_cust)
    
    def calcualte_labour_costs(self):
        """Calculate total labour costs based on resource usage and wage rates."""
        total_minutes = self.clock
        labour_cost = total_minutes / 60.0 * self.cfg.labour_cost_per_hour * (
            self.cfg.num_cashiers +
            self.cfg.num_dt_stations +
            self.cfg.num_cooks +
            self.cfg.num_packers +
            self.cfg.num_bussers
        )
        return labour_cost
    

    def end(self):
        self.stats.record_time(self.clock)
        # record customer still in queue 
        self.stats.record_queue_length('Walkin queue', len(self.q_walkin))
        self.stats.record_queue_length('Drive-thru queue', len(self.q_drivethru))
        self.stats.record_queue_length('Kitchen queue', len(self.q_kitchen))
        self.stats.record_queue_length('Packing queue', len(self.q_packing))
        self.stats.record_labour_costs(self.calcualte_labour_costs())
