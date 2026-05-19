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

    INFINITY = 16

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # port -> (neighbor_addr, cost)
        self.neighbors = {}

        # neighbor_addr -> received DV
        self.neighbor_vectors = {}

        # destination -> cost
        self.distance_vector = {self.addr: 0}

        # destination -> output port
        self.forwarding_table = {}

    def broadcast_vector(self):
        msg = json.dumps(self.distance_vector)

        for port in self.neighbors:
            pkt = Packet(Packet.ROUTING, self.addr, None)
            pkt.content = msg
            self.send(port, pkt)

    def recompute_routes(self):
        old_vector = dict(self.distance_vector)

        new_vector = {self.addr: 0}
        new_forward = {}

        # direct neighbors are reachable
        for port, (nbr, cost) in self.neighbors.items():
            if nbr not in new_vector or cost < new_vector[nbr]:
                new_vector[nbr] = cost
                new_forward[nbr] = port

        # routes learned from neighbors
        for port, (nbr, link_cost) in self.neighbors.items():
            nbr_dv = self.neighbor_vectors.get(nbr, {})

            for dest, nbr_cost in nbr_dv.items():
                if dest == self.addr:
                    continue

                total = link_cost + nbr_cost
                if total > self.INFINITY:
                    total = self.INFINITY

                if dest not in new_vector or total < new_vector[dest]:
                    new_vector[dest] = total
                    new_forward[dest] = port

        self.distance_vector = new_vector
        self.forwarding_table = new_forward

        return old_vector != self.distance_vector

    def handle_packet(self, port, packet):
        """Process incoming packet."""

        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                self.send(self.forwarding_table[dst], packet)

        else:
            try:
                recv_vector = json.loads(packet.content)
            except Exception:
                return

            neighbor = packet.src_addr
            old = self.neighbor_vectors.get(neighbor, {})
            if old != recv_vector:
                self.neighbor_vectors[neighbor] = recv_vector

                changed = self.recompute_routes()
                if changed:
                    self.broadcast_vector()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""

        self.neighbors[port] = (endpoint, cost)

        if endpoint not in self.neighbor_vectors:
            self.neighbor_vectors[endpoint] = {}

        changed = self.recompute_routes()
        if changed:
            self.broadcast_vector()
        else:
            self.broadcast_vector()

    def handle_remove_link(self, port):
        """Handle removed link."""

        if port in self.neighbors:
            endpoint = self.neighbors[port][0]
            del self.neighbors[port]

            if endpoint in self.neighbor_vectors:
                del self.neighbor_vectors[endpoint]

        changed = self.recompute_routes()
        if changed:
            self.broadcast_vector()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.broadcast_vector()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return (
            f"DVrouter(addr={self.addr})\n"
            f"DV={self.distance_vector}\n"
            f"FWD={self.forwarding_table}"
        )