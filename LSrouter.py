####################################################
# LSrouter.py
# Name:Hoàng Việt Anh Đức
# HUID:24020077
#####################################################

from router import Router
from packet import Packet
import json
import heapq


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding
    table data structures). See the `Router` base class for docstrings of the
    methods to override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # Link-state routing data structures
        self.adjacency = {}           # neighbor endpoint -> (port, cost)
        self.link_states = {}         # router addr -> {neighbor: cost}
        self.sequence_numbers = {}    # router addr -> latest seq num received
        self.forwarding_table = {}    # destination addr -> output port
        self.own_sequence = 0         # local sequence number for link-state updates

        self._update_own_state()

    def _update_own_state(self):
        """Update this router's own link-state and recompute routes."""
        self.own_sequence += 1
        self.link_states[self.addr] = {
            neighbor: cost for neighbor, (_, cost) in self.adjacency.items()
        }
        self.sequence_numbers[self.addr] = self.own_sequence
        self._recompute_forwarding_table()

    def _build_ls_packet(self):
        """Build a routing packet containing this router's current link state."""
        content = json.dumps({
            "origin": self.addr,
            "seq": self.own_sequence,
            "links": self.link_states.get(self.addr, {}),
        })
        return Packet(Packet.ROUTING, self.addr, None, content=content)

    def _broadcast_link_state(self, exclude_port=None):
        """Flood the current link state packet to all neighbors except exclude_port."""
        pkt = self._build_ls_packet()
        for port in self.links:
            if port == exclude_port:
                continue
            self.send(port, pkt)

    def _recompute_forwarding_table(self):
        """Use Dijkstra's algorithm on the collected link-state database."""
        graph = {}
        for node, neighbors in self.link_states.items():
            graph.setdefault(node, {})
            for neighbor, cost in neighbors.items():
                graph[node][neighbor] = cost
                graph.setdefault(neighbor, {})
                if node not in graph[neighbor] or cost < graph[neighbor][node]:
                    graph[neighbor][node] = cost

        dist = {self.addr: 0}
        prev = {}
        heap = [(0, self.addr)]
        visited = set()

        while heap:
            current_dist, node = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)

            for neighbor, cost in graph.get(node, {}).items():
                new_dist = current_dist + cost
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

        new_forwarding = {}
        for destination in dist:
            if destination == self.addr:
                continue

            next_hop = destination
            while prev.get(next_hop) is not None and prev[next_hop] != self.addr:
                next_hop = prev[next_hop]

            if prev.get(next_hop) == self.addr and next_hop in self.adjacency:
                new_forwarding[destination] = self.adjacency[next_hop][0]

        self.forwarding_table = new_forwarding

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                self.send(self.forwarding_table[dst], packet)
        else:
            try:
                data = json.loads(packet.content)
            except Exception:
                return

            origin = data.get("origin")
            seq = data.get("seq")
            links = data.get("links")

            if origin is None or seq is None or links is None:
                return

            prev_seq = self.sequence_numbers.get(origin, -1)
            if seq > prev_seq:
                self.sequence_numbers[origin] = seq
                self.link_states[origin] = links
                self._recompute_forwarding_table()

                for out_port in self.links:
                    if out_port != port:
                        forward_pkt = Packet(Packet.ROUTING, self.addr, None, content=packet.content)
                        self.send(out_port, forward_pkt)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.adjacency[endpoint] = (port, cost)
        self._update_own_state()
        self._broadcast_link_state()

    def handle_remove_link(self, port):
        """Handle removed link."""
        remove_neighbor = None
        for neighbor, (neighbor_port, _) in list(self.adjacency.items()):
            if neighbor_port == port:
                remove_neighbor = neighbor
                break

        if remove_neighbor is not None:
            del self.adjacency[remove_neighbor]

        self._update_own_state()
        self._broadcast_link_state()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._update_own_state()
            self._broadcast_link_state()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return (
            f"LSrouter(addr={self.addr})\n"
            f"LS={self.link_states}\n"
            f"FWD={self.forwarding_table}"
        )