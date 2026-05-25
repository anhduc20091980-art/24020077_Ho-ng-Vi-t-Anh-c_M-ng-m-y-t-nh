####################################################
# DVrouter.py
# Name:Hoàng Việt Anh Đức
# HUID:24020077
#####################################################

from router import Router
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
            if updated:
                self.update_forwarding_table()
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
            if changed:
                self.update_forwarding_table()
                self.broadcast_distance_vector()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            # periodic broadcast
            self.broadcast_distance_vector()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"DVrouter(addr={self.addr}, dv={self.distance_vector})"

    # Helper methods
    def update_forwarding_table(self):
        """Compute forwarding table from current distance vector and neighbors."""
        self.forwarding_table = {}
        for dest, _ in self.distance_vector.items():
            if dest == self.addr:
                continue
            best_port = None
            best_cost = float('inf')
            for port, (nbr, link_cost) in self.neighbors.items():
                # If we know neighbor's advertised distance to dest, use it
                nbr_adv = self.neighbor_dvs.get(nbr, {})
                adv_cost = nbr_adv.get(dest, float('inf'))
                # if dest is the neighbor itself, cost is direct link_cost
                if dest == nbr:
                    total = link_cost
                else:
                    total = link_cost + adv_cost
                if total < best_cost:
                    best_cost = total
                    best_port = port
            if best_port is not None:
                self.forwarding_table[dest] = best_port

    def recalculate_distance_vector(self):
        """Recompute distance vector from neighbor adverts and direct links.

        Returns True if the distance_vector changed.
        """
        new_dv = {self.addr: 0}
        INF = float('inf')

        # consider direct neighbors
        for port, (nbr, link_cost) in self.neighbors.items():
            new_dv[nbr] = min(new_dv.get(nbr, INF), link_cost)

        # consider paths through neighbors using their advertised vectors
        for nbr, adv in self.neighbor_dvs.items():
            # find link cost to this neighbor
            link_cost = None
            for p, (n, c) in self.neighbors.items():
                if n == nbr:
                    link_cost = c
                    break
            if link_cost is None:
                continue
            for dest, advertised_cost in adv.items():
                try:
                    adv_cost = float(advertised_cost)
                except Exception:
                    continue
                total = link_cost + adv_cost
                if dest not in new_dv or total < new_dv[dest]:
                    new_dv[dest] = total

        # detect change (use strict equality on keys and values)
        if new_dv != self.distance_vector:
            self.distance_vector = new_dv
            return True
        return False

    def broadcast_distance_vector(self):
        """Send our distance vector to all neighbors as a routing packet."""
        from packet import Packet
        INF = 16
        # For each neighbor, apply poison reverse: advertise INF for destinations
        # whose next hop is that neighbor.
        for port, (nbr, link_cost) in list(self.neighbors.items()):
            advertised = {}
            for dest, dist in self.distance_vector.items():
                # if our forwarding table sends dest via this port, poison it
                if self.forwarding_table.get(dest) == port:
                    advertised[dest] = INF
                else:
                    advertised[dest] = dist
            content = json.dumps(advertised)
            pkt = Packet(Packet.ROUTING, self.addr, None, content=content)
            try:
                self.send(port, pkt)
            except Exception:
                pass
