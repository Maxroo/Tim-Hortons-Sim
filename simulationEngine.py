from simulationConfig import *

@dataclass(order=True)
class Event:
    time: float
    type: EventType = field(compare=False)
    customer: Optional[Customer] = field(default=None, compare=False)
    id: int = field(default=0, compare=False)

class SimEngine:
    def __init__(self):
        self.clock = 0.0
        self.events = []
        self.event_id_counter = 0

    def schedule(self, delay, event_type, customer=None):
        timestamp = self.clock + delay
        self.event_id_counter += 1
        evt = Event(timestamp, event_type, customer, self.event_id_counter)
        heapq.heappush(self.events, evt) # auto-sorted by time

    def run(self, duration):
        while self.events and self.clock < duration:
            evt = heapq.heappop(self.events)
            self.clock = evt.time
            self.handle_event(evt)
        self.end()

    def end(self):
        raise NotImplementedError
            
    def handle_event(self, evt):
        raise NotImplementedError