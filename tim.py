class TimHortonsModel(SimulationEngine):
    def __init__(self, config: Config):
        super().__init__()
        self.cfg = config
        
        # --- RESOURCES & QUEUES ---
        # Queues (FIFO)
        self.q_cashier = deque()
        self.q_kitchen = deque() # Shared by all orders
        self.q_packing = deque()
        self.q_drive_pickup = deque() # Waiting for window
        
        # Resource States (Counters)
        self.busy_cashiers = 0
        self.busy_cooks = 0
        self.busy_packers = 0
        
        # Complex Resources
        self.coffee_level = config.COFFEE_URN_CAPACITY
        self.is_brewing = False
        self.shelf_occupancy = 0
        
        # Statistics
        self.stats = {
            'revenue': 0, 'balks': 0, 'reneges': 0, 
            'served': 0, 'wasted_food': 0
        }

    # ==========================
    # EVENT DISPATCHER
    # ==========================
    def handle_event(self, event: Event):
        if event.event_type == EventType.ARRIVAL:
            self.process_arrival(event.customer)
            
        elif event.event_type == EventType.ORDER_COMPLETED:
            self.process_order_complete(event.customer)
            
        elif event.event_type == EventType.KITCHEN_PREP_DONE:
            self.process_prep_done(event.customer)
            
        elif event.event_type == EventType.PACKING_DONE:
            self.process_pack_done(event.customer)
            
        elif event.event_type == EventType.BREW_FINISH:
            self.process_brew_finish()
            
        elif event.event_type == EventType.MOBILE_RENEGE_CHECK:
            self.process_renege_check(event.customer)

    # ==========================
    # LOGIC HANDLERS
    # ==========================
    
    def process_arrival(self, customer):
        # 1. Schedule next arrival (Bootstrap)
        self.schedule_next_arrival()

        # 2. Logic based on channel
        if customer.channel == Channel.DRIVE_THRU:
            # BALKING LOGIC
            # Note: We approximate DT queue size as orders in system not yet paid
            dt_queue_len = len(self.q_cashier) + len(self.q_kitchen) 
            if dt_queue_len > self.cfg.MAX_DRIVE_THRU_QUEUE:
                customer.balked = True
                self.stats['balks'] += 1
                return # Exit system
        
        elif customer.channel == Channel.MOBILE:
            # RENEGING LOGIC
            # Schedule a future check: "In 15 mins, check if I'm still waiting"
            self.schedule(15.0, EventType.MOBILE_RENEGE_CHECK, customer)
            # Skip cashier, go straight to kitchen queue
            self.q_kitchen.append(customer)
            self.try_start_kitchen()
            return

        # 3. Add to Cashier Queue (Walk-in & DT)
        self.q_cashier.append(customer)
        self.try_start_cashier()

    def try_start_cashier(self):
        # If staff free AND customers waiting
        if self.busy_cashiers < self.cfg.NUM_CASHIERS and self.q_cashier:
            customer = self.q_cashier.popleft()
            self.busy_cashiers += 1
            
            # Service Time (Random)
            duration = random.expovariate(1.0 / 2.0) # Avg 2 mins
            self.schedule(duration, EventType.ORDER_COMPLETED, customer)

    def process_order_complete(self, customer):
        self.busy_cashiers -= 1
        self.try_start_cashier() # Pull next person
        
        # Move customer to Kitchen Queue
        self.q_kitchen.append(customer)
        self.try_start_kitchen()

    def try_start_kitchen(self):
        """
        The Brain: Matches Cooks + Coffee + Orders
        """
        if not self.q_kitchen:
            return

        # Check Resources
        if self.busy_cooks < self.cfg.NUM_COOKS:
            # Peek at next customer (don't pop yet)
            next_cust = self.q_kitchen[0]
            
            # COFFEE CONSTRAINT
            needs_coffee = 'COFFEE' in next_cust.items_needed
            if needs_coffee and self.coffee_level <= 0:
                if not self.is_brewing:
                    self.start_brewing()
                return # BLOCKED: Cannot start this order

            # If we get here, we can cook
            customer = self.q_kitchen.popleft()
            self.busy_cooks += 1
            if needs_coffee:
                self.coffee_level -= 1
            
            # Service Time
            duration = random.normalvariate(3.0, 1.0) # Avg 3 mins
            duration = max(0.5, duration) 
            self.schedule(duration, EventType.KITCHEN_PREP_DONE, customer)

    def start_brewing(self):
        self.is_brewing = True
        # Takes 5 minutes to brew
        self.schedule(5.0, EventType.BREW_FINISH)

    def process_brew_finish(self):
        self.coffee_level = self.cfg.COFFEE_URN_CAPACITY
        self.is_brewing = False
        # Coffee is ready, try to unblock kitchen
        self.try_start_kitchen()

    def process_prep_done(self, customer):
        self.busy_cooks -= 1
        self.try_start_kitchen() # Cook takes next order
        
        self.q_packing.append(customer)
        self.try_start_packing()

    def try_start_packing(self):
        # BLOCKING CONSTRAINT: Shelf Capacity
        if self.shelf_occupancy >= self.cfg.SHELF_CAPACITY:
            return # Packer is blocked, cannot start new pack

        if self.busy_packers < self.cfg.NUM_PACKERS and self.q_packing:
            customer = self.q_packing.popleft()
            self.busy_packers += 1
            
            duration = 1.0 # 1 min to pack
            self.schedule(duration, EventType.PACKING_DONE, customer)

    def process_pack_done(self, customer):
        self.busy_packers -= 1
        
        # Put on shelf
        self.shelf_occupancy += 1
        customer.is_ready = True
        
        # Simulate Customer Pickup Lag
        # (Mobile users might come later, Walk-ins are immediate)
        pickup_lag = 0 if customer.channel == Channel.WALK_IN else random.uniform(0, 10)
        
        # We define a custom inline event logic for pickup to clear shelf
        # For simplicity, we just count revenue now, but decrement shelf later
        self.stats['revenue'] += self.cfg.PRICE_AVG
        self.stats['served'] += 1
        
        # Schedule the "Shelf Clearing" event
        self.schedule(pickup_lag, EventType.CUSTOMER_PICKUP, customer)
        
        self.try_start_packing()

    def handle_customer_pickup(self, customer):
        # (This would need to be added to the main dispatch)
        # Only when they pick up does the shelf clear
        self.shelf_occupancy -= 1
        self.try_start_packing() # Unblock packer if they were stuck

    def process_renege_check(self, customer):
        if not customer.is_ready and not customer.balked:
            # They waited too long and food isn't ready
            customer.reneged = True
            self.stats['reneges'] += 1
            # Note: Removing them from the specific queue (kitchen/pack) 
            # is computationally expensive in a list. 
            # In a real sim, we'd mark them 'dead' and when the cook 
            # pops them, they discard the order.

    def schedule_next_arrival(self):
        # Helper to keep the simulation running
        inter_arrival = random.expovariate(1.0/2.0)
        new_cust = Customer(
            id=random.randint(1000,9999),
            channel=random.choice(list(Channel)),
            arrival_time=self.clock + inter_arrival,
            items_needed=['COFFEE'] # Simplified
        )
        self.schedule(inter_arrival, EventType.ARRIVAL, new_cust)

# --- 4. Running the Experiment ---
config = Config(NUM_CASHIERS=2, NUM_COOKS=3)
sim = TimHortonsModel(config)

# Seed first arrival
first_cust = Customer(1, Channel.WALK_IN, 0.0, ['COFFEE'])
sim.schedule(0, EventType.ARRIVAL, first_cust)

sim.run(max_time=480) # Run for 8 hours (480 mins)
print("Simulation Ended. Stats:", sim.stats)