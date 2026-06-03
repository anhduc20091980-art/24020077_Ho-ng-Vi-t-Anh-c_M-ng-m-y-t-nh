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

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        # Mapping: port -> neighbor address
        self.ports = {}
        # Adjacency for this router (its direct links): node -> cost
        self.adj = {self.addr: {}}
        # Link-state database: node -> (seq, links(dict))
        self.lsdb = {}
        # Sequence number for our own link-state advertisements
        self.seq = 0
        # Forwarding table: destination -> port
        self.forwarding_table = {}
        # Debug flag to print adjacency and forwarding table
        self.debug = True

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        # Data packet: forward using forwarding table
        if packet.is_traceroute:
            if packet.dst_addr in self.forwarding_table:
                out_port = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
            return

        # Routing packet: link-state advertisement (JSON)
        if packet.is_routing:
            try:
                content = json.loads(packet.content) if packet.content else {}
            except Exception:
                return

            origin = content.get("origin")
            seq = content.get("seq", 0)
            links = content.get("links", {})

            # If new or higher sequence number, update LSDB and recompute
            stored = self.lsdb.get(origin)
            if stored is None or seq > stored[0]:
                self.lsdb[origin] = (seq, links)
                # rebuild global adjacency from LSDB and our own adj
                self.rebuild_adjacency()
                self.compute_forwarding_table()
                # flood to neighbors (except incoming port)
                for p in list(self.ports.keys()):
                    if p == port:
                        continue
                    try:
                        self.send(p, packet)
                    except Exception:
                        pass

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        # record port->neighbor and update our adj
        self.ports[port] = endpoint
        self.adj.setdefault(self.addr, {})[endpoint] = cost
        # increment sequence number and install our own link-state into lsdb
        self.seq += 1
        self.lsdb[self.addr] = (self.seq, dict(self.adj[self.addr]))
        # recompute and broadcast
        self.rebuild_adjacency()
        self.compute_forwarding_table()
        self.broadcast_lsp()

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.ports:
            endpoint = self.ports[port]
            del self.ports[port]
            # remove from our adjacency
            if endpoint in self.adj.get(self.addr, {}):
                del self.adj[self.addr][endpoint]
            # increment seq and update lsdb
            self.seq += 1
            self.lsdb[self.addr] = (self.seq, dict(self.adj[self.addr]))
            self.rebuild_adjacency()
            self.compute_forwarding_table()
            self.broadcast_lsp()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            # periodic broadcast of our link-state
            self.broadcast_lsp()

    def rebuild_adjacency(self):
        """Rebuild the global adjacency map from the link-state database."""
        self.adj = {self.addr: dict(self.lsdb.get(self.addr, (0, {}))[1])}
        for node, (seq, links) in self.lsdb.items():
            if node not in self.adj:
                self.adj[node] = {}
            for nbr, cost in links.items():
                self.adj[node][nbr] = cost

    def compute_forwarding_table(self):
        """Compute shortest paths with Dijkstra and build the forwarding table."""
        self.forwarding_table = {}
        graph = {node: dict(neighbors) for node, neighbors in self.adj.items()}

        if self.addr not in graph:
            graph[self.addr] = {}

        dist = {node: float('inf') for node in graph}
        prev = {node: None for node in graph}
        dist[self.addr] = 0
        pq = [(0, self.addr)]

        while pq:
            cur_dist, node = heapq.heappop(pq)
            if cur_dist != dist[node]:
                continue
            for nbr, cost in graph.get(node, {}).items():
                nd = cur_dist + cost
                if nd < dist.get(nbr, float('inf')):
                    dist[nbr] = nd
                    prev[nbr] = node
                    heapq.heappush(pq, (nd, nbr))

        for dest, d in dist.items():
            if dest == self.addr or d == float('inf'):
                continue
            if dest in self.ports.values():
                for port, nbr in self.ports.items():
                    if nbr == dest:
                        self.forwarding_table[dest] = port
                        break
                continue

            nxt = dest
            while prev.get(nxt) is not None and prev[nxt] != self.addr:
                nxt = prev[nxt]
            if prev.get(dest) is None:
                continue
            next_hop = prev[dest]
            if next_hop == self.addr:
                # direct link from this router to dest
                for port, nbr in self.ports.items():
                    if nbr == dest:
                        self.forwarding_table[dest] = port
                        break
            else:
                # For a multi-hop path, choose the first port on the edge from us.
                for port, nbr in self.ports.items():
                    if nbr == next_hop:
                        self.forwarding_table[dest] = port
                        break

    def broadcast_lsp(self):
        """Flood our link-state advertisement to all direct neighbors."""
        content = json.dumps({"origin": self.addr, "seq": self.seq, "links": dict(self.adj.get(self.addr, {}))})
        for port in list(self.ports.keys()):
            packet = Packet(Packet.ROUTING, self.addr, self.ports[port], content)
            self.send(port, packet)

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return (
            f"LSrouter(addr={self.addr})\n"
            f"LS={self.lsdb}\n"
            f"FWD={self.forwarding_table}"
        )
