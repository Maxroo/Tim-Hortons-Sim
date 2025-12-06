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
        
        # --- Complex Resources ---
        self.coffee_level = config.coffee_urn_size
        self.is_brewing = False
        self.shelf_occupancy = 0
        
        # --- Stats ---
        self.stats = Statistics(config)

    def handle_event(self, evt):
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
            self.stats.record_arrival(Channel.WALK_IN)

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
            self.q_kitchen.popleft()

            #  has not start making yet. so don't record waste 
            self.stats.record_success(cust.channel, self.clock - cust.arrival_time, 0) # customer left, no revenue,

            self.try_start_kitchen() # Check next order
            return
        
        # 2. SECONDARY RESOURCE CHECKS (Equipment/Ingredients)
        
        # Case A: Espresso Order (Needs Machine)
        if cust.needs_espresso:
            if self.busy_espresso_machines >= self.cfg.num_espresso_machines:
                return # BLOCKED: Cook is free, but Machine is busy
        
        # Case B: Brewed Coffee Order (Needs Liquid)
        elif cust.needs_coffee:
            if self.coffee_level <= 0:
                if not self.is_brewing:
                    self.start_brewing()
                return # BLOCKED: Cook is free, but Coffee is empty

        # 3. SEIZE RESOURCES (If we survived the checks)
        self.q_kitchen.popleft() # Now we commit
        
        self.busy_cooks += 1
        
        duration = 0.0

        if cust.needs_espresso:
            self.busy_espresso_machines += 1
            espressoDuration = random.expovariate(1.0 / self.cfg.mean_espresso_time)
            duration += espressoDuration
            self.stats.record_usage('ESPRESSO', espressoDuration)

        if cust.needs_coffee:
            self.coffee_level -= 1
            brewedDuration = 0.5 # Pouring is fast
            duration += brewedDuration

        if cust.needs_hot_food:
            # Just food
            hotFoodDuration = random.expovariate(1.0 / self.cfg.mean_kitchen_time)
            self.stats.record_usage('COOK', hotFoodDuration)
            duration += hotFoodDuration

        if duration == 0:
            raise ValueError("Order has no items to prepare!")
        
        self.schedule(duration, EventType.KITCHEN_DONE, cust)

    def process_kitchen_done(self, customer):
        # 1. Free the Human
        self.busy_cooks -= 1
        
        # 2. Free the Machine (if used)
        if customer.needs_espresso:
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
                self.stats.record_waste()
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
            self.stats.record_waste()
        else:
            # Successful transaction
            wait_time = self.clock - customer.arrival_time
            self.stats.record_success(
                customer.channel, 
                wait_time, 
                self.cfg.avg_revenue
            )

    def process_renege_check(self, customer):
        # If time is up and food isn't ready
        if not customer.is_ready:
            customer.has_reneged = True
            self.stats.record_renege()

    # --- Utility ---
    def schedule_next_arrival(self, channel):
        rate = 0
        if channel == Channel.WALK_IN: rate = self.cfg.lambda_walkin
        elif channel == Channel.DRIVE_THRU: rate = self.cfg.lambda_drivethru
        elif channel == Channel.MOBILE: rate = self.cfg.lambda_mobile
        
        delay = self.cfg.get_inter_arrival(rate)
        
        # Create new customer
        new_id = self.customer_counter + 1
        self.customer_counter = new_id
        
        needs_coffee = random.random() < self.cfg.prob_order_coffee
        needs_espresso = not needs_coffee # if not coffee, then espresso
        needs_hot_food = random.random() < self.cfg.prob_order_hot_food

        new_cust = Customer(new_id, channel, self.clock + delay, needs_coffee, needs_espresso, needs_hot_food)
        self.schedule(delay, EventType.ARRIVAL, new_cust)

    def end(self):
        self.stats.record_time(self.clock)
        # record customer still in queue 
        self.stats.record_queue_length('CASHIER', len(self.q_walkin))
        self.stats.record_queue_length('DRIVE_THRU', len(self.q_drivethru))
        self.stats.record_queue_length('KITCHEN', len(self.q_kitchen))
        self.stats.record_queue_length('PACKING', len(self.q_packing))
