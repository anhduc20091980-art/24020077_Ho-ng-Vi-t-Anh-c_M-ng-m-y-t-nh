####################################################
# DVrouter.py
# Name:Hoàng Việt Anh Đức
# HUID:24020077
#####################################################

from router import Router
from packet import Packet
import json


class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        # Distance vector: destination -> cost
        self.distance_vector = {addr: 0}
        # Neighbors: port -> (neighbor_addr, link_cost)
        self.neighbors = {}
        # Store last advertised distance vectors from neighbors: neighbor_addr -> dv(dict)
        self.neighbor_dvs = {}
        # Forwarding table: destination -> port
        self.forwarding_table = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        # If this is a data/traceroute packet, forward according to forwarding table
        if packet.is_traceroute:
            if packet.dst_addr in self.forwarding_table:
                out_port = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
            return

        # Routing packet: content is a JSON-encoded distance vector
        if packet.is_routing:
            # ignore if we don't know this port as neighbor
            if port not in self.neighbors:
                return
            neighbor_addr, link_cost = self.neighbors[port]
            try:
                received_dv = json.loads(packet.content) if packet.content else {}
            except Exception:
                received_dv = {}

            # store neighbor's advertised DV
            self.neighbor_dvs[neighbor_addr] = received_dv

            # recompute our distance vector from scratch using neighbors' adverts
            updated = self.recalculate_distance_vector()
            self.update_forwarding_table()
            if updated:
                self.broadcast_distance_vector()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        # record neighbor and cost
        self.neighbors[port] = (endpoint, cost)
        # initialize neighbor advertised DV to empty until we hear from them
        self.neighbor_dvs[endpoint] = {}
        # recompute DV and broadcast
        self.recalculate_distance_vector()
        self.update_forwarding_table()
        self.broadcast_distance_vector()

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.neighbors:
            nbr, _ = self.neighbors[port]
            del self.neighbors[port]
            # remove stored neighbor dv
            if nbr in self.neighbor_dvs:
                del self.neighbor_dvs[nbr]
            # recompute and broadcast
            changed = self.recalculate_distance_vector()
            self.update_forwarding_table()
            if changed:
                self.broadcast_distance_vector()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            # periodic broadcast
            self.broadcast_distance_vector()

    def recalculate_distance_vector(self):
        """Recompute shortest distances using neighbors' advertised vectors."""
        INF = 16
        old_dv = dict(self.distance_vector)

        new_dv = {self.addr: 0}

        for port, (neighbor_addr, cost) in self.neighbors.items():
            if cost < INF:
                new_dv[neighbor_addr] = min(new_dv.get(neighbor_addr, INF), cost)

        for port, (neighbor_addr, cost) in self.neighbors.items():
            neighbor_dv = self.neighbor_dvs.get(neighbor_addr, {}) or {}
            for dest, dv_cost in neighbor_dv.items():
                if dv_cost < INF and cost + dv_cost < INF:
                    candidate = cost + dv_cost
                    new_dv[dest] = min(new_dv.get(dest, INF), candidate)

        self.distance_vector = new_dv
        return old_dv != new_dv

    def update_forwarding_table(self):
        """Build the forwarding table using the shortest distances we computed."""
        INF = 16
        self.forwarding_table = {}

        for dest, dist in self.distance_vector.items():
            if dest == self.addr or dist >= INF:
                continue

            best_port = None

            for port, (neighbor_addr, link_cost) in self.neighbors.items():
                neighbor_dv = self.neighbor_dvs.get(neighbor_addr, {}) or {}
                if dest == neighbor_addr:
                    candidate_cost = link_cost
                else:
                    candidate_cost = link_cost + neighbor_dv.get(dest, INF)

                if candidate_cost == dist and candidate_cost < INF:
                    best_port = port
                    break

            if best_port is not None:
                self.forwarding_table[dest] = best_port

    def broadcast_distance_vector(self):
        """Advertise our current distance vector to every neighbor."""
        for port, (neighbor_addr, _) in self.neighbors.items():
            packet = Packet(Packet.ROUTING, self.addr, neighbor_addr, json.dumps(self.distance_vector))
            self.send(port, packet)

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return (
            f"DVrouter(addr={self.addr})\n"
            f"DV={self.distance_vector}\n"
            f"FWD={self.forwarding_table}"
        )
