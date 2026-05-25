####################################################
# LSrouter.py
# Name:Hoàng Việt Anh Đức
# HUID:24020077
#####################################################

from router import Router
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

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"LSrouter(addr={self.addr}, seq={self.seq}, links={self.adj.get(self.addr,{})})"

    # Helper methods for LSrouter
    def rebuild_adjacency(self):
        """Build global adjacency map from lsdb entries."""
        # adjacency: node -> {neighbor: cost}
        self.global_adj = {}
        # include entries from lsdb
        for node, (seq, links) in self.lsdb.items():
            self.global_adj[node] = dict(links)
        # ensure our own entry exists
        self.global_adj.setdefault(self.addr, dict(self.adj.get(self.addr, {})))

    def compute_forwarding_table(self):
        """Run Dijkstra on global_adj and set self.forwarding_table (dest -> port).

        For destinations that are directly our neighbor, forward to that port.
        """
        # Dijkstra
        dist = {n: float('inf') for n in self.global_adj}
        prev = {}
        dist[self.addr] = 0
        pq = [(0, self.addr)]
        while pq:
            d, u = heapq.heappop(pq)
            if d != dist.get(u, float('inf')):
                continue
            for v, w in self.global_adj.get(u, {}).items():
                nd = d + w
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        # Build forwarding table: for each dest, find next hop neighbor
        ft = {}
        for dest in dist:
            if dest == self.addr or dist[dest] == float('inf'):
                continue
            # walk back from dest to find neighbor next to self.addr
            cur = dest
            prev_node = prev.get(cur)
            if prev_node is None:
                # direct neighbor?
                if cur in self.adj.get(self.addr, {}):
                    next_hop = cur
                else:
                    continue
            else:
                while prev.get(cur) is not None and prev[cur] != self.addr:
                    cur = prev[cur]
                # now prev[cur] == self.addr or prev[cur] is None
                if prev.get(cur) == self.addr:
                    next_hop = cur
                else:
                    # cur is direct neighbor
                    next_hop = cur

            # find port for next_hop
            port = None
            for p, nbr in self.ports.items():
                if nbr == next_hop:
                    port = p
                    break
            if port is not None:
                ft[dest] = port

        self.forwarding_table = ft
        if getattr(self, 'debug', False):
            try:
                print(f"LSrouter {self.addr} global_adj={self.global_adj}")
                print(f"LSrouter {self.addr} forwarding_table={self.forwarding_table}")
            except Exception:
                pass

    def broadcast_lsp(self):
        """Broadcast our current link-state (with seq) to all neighbors."""
        from packet import Packet
        # ensure our lsdb entry is up to date
        self.lsdb[self.addr] = (self.seq, dict(self.adj.get(self.addr, {})))
        content = json.dumps({"origin": self.addr, "seq": self.seq, "links": self.adj.get(self.addr, {})})
        for port in list(self.ports.keys()):
            pkt = Packet(Packet.ROUTING, self.addr, None, content=content)
            try:
                self.send(port, pkt)
            except Exception:
                pass
