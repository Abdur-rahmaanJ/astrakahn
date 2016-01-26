#!/usr/bin/env python3

from . import ast

import re
import copy

import networkx as nx
from functools import reduce


class DiGraph(nx.DiGraph):
    merge_nonce = 1
    entry = []
    exit = []

    def add_vertex(self, vtx):
        # NOTE: O(N) !!!
        nonce = sum(1 for n in self.nodes() if n.startswith(vtx.name))
        node_name = '%s:%d' % (vtx.name, nonce)
        self.add_node(node_name)
        self.node[node_name]['vtx'] = vtx
        return node_name

    def add_wire(self, lnode, rnode, port):
        self.add_edge(lnode, rnode)
        edge = self.edge[lnode][rnode]
        edge['chn'] = edge.get('chn', set()) | set((port, ))

    def add_merger(self, inputs, outputs):
        name = '%s%d' % ('merger', self.merge_nonce)
        self.merge_nonce += 1

        merger = Sync(name, inputs, outputs, None, None)
        return self.add_vertex(merger)

    def connect(self, lnbunch, rnbunch):

        mergers_left = self._flatten(lnbunch)
        mergers_right = self._flatten(rnbunch)

        lports = self._port_to_nodes_map('out', lnbunch)
        rports = self._port_to_nodes_map('in', rnbunch)

        common_ports = lports.keys() & rports.keys()

        for port in common_ports:
            assert len(lports[port]) == len(rports[port]) == 1
            self.add_wire(lports[port][0], rports[port][0], port)

        return (mergers_left, mergers_right)

    def _node_free_ports(self, side, node):
        assert side in ('in', 'out')
        get_edges = getattr(self, side + '_edges')

        edges = (e[2]['chn'] for e in get_edges((node,), True))
        channels = reduce(set.union, edges, set())

        ports = getattr(self.node[node]['vtx'], side + 'puts')

        return list(set(ports) - channels)

    def _port_to_nodes_map(self, side, nbunch):
        ports = {}

        for node in nbunch:
            fp = self._node_free_ports(side, node)
            for port in fp:
                ports[port] = ports.get(port, []) + [node]

        return ports

    def _disambiguate_port(self, side, nbunch, port):
        ports = []

        for i, node in enumerate(nbunch):
            vtx = self.node[node]['vtx']
            new_port = vtx.disambiguate_port(side, port, i)
            ports.append((node, new_port))

        return ports

    def _get_merger_name(self):
        name = '%s%d' % ('merger', self.merge_nonce)
        self.merge_nonce += 1
        return name

    def _flatten_side(self, side, nbunch):

        mergers = set()
        port_nodes = self._port_to_nodes_map(side, nbunch)

        for port, nodes in port_nodes.items():
            np = len(nodes)

            if np > 1:
                dports = self._disambiguate_port(side, nodes, port)

                new_names = [p[1] for p in dports]

                mrg = self.add_merger(new_names if side == 'out' else [port],
                                      new_names if side == 'in' else [port])
                mergers.add(mrg)

                for node, port in dports:
                    if side == 'in':
                        self.add_wire(mrg, node, port)
                    else:
                        self.add_wire(node, mrg, port)

        return mergers

    def _flatten(self, nbunch):

        mergers_left = self._flatten_side('in', nbunch)
        mergers_right = self._flatten_side('out', nbunch)

        return mergers_left | mergers_right

    def _set_in_out(self):
        inputs = self._port_to_nodes_map('in', self.nodes())
        self.entry = {port: nodes[0] for port, nodes in inputs.items()}

        outputs = self._port_to_nodes_map('out', self.nodes())
        self.exit = {port: nodes[0] for port, nodes in outputs.items()}

    def _bb_rename(self):

        # Add `stmts' attribute to nodes.
        nodes_stmt = ((n, {'stmts': [(attrs['vtx'].name, attrs['vtx'])]})
                      for n,attrs in self.nodes(data=True))
        self.add_nodes_from(nodes_stmt)

        # Remove `vtx'
        for n in self.nodes():
            del self.node[n]['vtx']

        # Rename vertices to BBs.
        bb_map = {n: 'bb_%d' % i for i,n in enumerate(self.nodes())}
        nx.relabel_nodes(self, bb_map, copy=False)

        self.entry = {port: bb_map[node] for port,node in self.entry.items()}
        self.exit = {port: bb_map[node] for port,node in self.exit.items()}

    def _bb_squash(self):

        # Add entry nodes.
        stack = list(self.entry.values())
        visited = set()

        while stack:
            n = stack.pop()
            visited.add(n)

            out_nodes = [d for s,d in self.out_edges(n)]

            # Single destination having single source: combine BBs.
            if len(out_nodes) == 1 and len(self.in_edges(out_nodes[0])) == 1:

                dest_node = out_nodes.pop()

                # Add new statement.
                self.node[n]['stmts'] += self.node[dest_node]['stmts']

                # Attach vertex's out edges to the BB.
                out_edges = ((n, d, self.edge[s][d])
                             for s,d in self.out_edges(dest_node))
                self.add_edges_from(out_edges)

                # Remove the squashed vertex.
                self.remove_node(dest_node)

                # Schedule the for further statement squashing.
                stack.append(n)
                visited.remove(n)

            else:
                # Add all destinations for traveral.
                stack += filter(lambda x: x not in visited, out_nodes)

    def convert_to_ir(self):
        self._bb_rename()
        self._bb_squash()


class NetBuilder(ast.NodeVisitor):

    def __init__(self, boxes):

        self.boxes = {}

        for name, func in boxes.items():
            # Match box specification from docstring.
            spec = str(func.__doc__).strip()
            m = re.match('^([1-9]\d*)(T|T\*|I|DO|DU|MO|MU|MS|H)$', spec)
            assert m

            n_out, cat = m.groups()
            n_out = int(n_out)
            n_in = 2 if cat[0] == 'D' else 1

            self.boxes[name] = Box(name, n_in, n_out, func)

        self.scope_stack = []
        self.net_stack = []

    # -------------------------------------------------------------------------

    def generic_visit(self, node, children):
        raise NotImplementedError('Handler missed: %s' % type(node))

    def get_net(self):
        assert self.net_stack
        return self.net_stack[-1]

    def scope(self):
        # Stack of scopes mustn't be empty
        assert self.scope_stack
        return self.scope_stack[-1]

    # -------------------------------------------------------------------------

    def visit_SynchTab(self, node, _):
        'final'
        inputs = [p.name.value for p in node.sync.ast.inputs.ports]
        outputs = [p.name.value for p in node.sync.ast.outputs.ports]

        return SyncTab(node.sync.name, inputs, outputs,
                       node.sync.ast, node.sync.macros, node.labels)

    def visit_Synchroniser(self, node, _):
        'final'
        inputs = [p.name.value for p in node.ast.inputs.ports]
        outputs = [p.name.value for p in node.ast.outputs.ports]
        return Sync(node.name, inputs, outputs, node.ast, node.macros)

    def visit_Net(self, node, _):
        'final'
        inputs = self.traverse(node.inputs)
        outputs = self.traverse(node.outputs)
        return Net(node.name, inputs, outputs, node)

    def visit_DeclList(self, node, children):
        return {d.name: d for d in children['decls']}

    # -------------------------------------------------------------------------

    def visit_Vertex(self, node, children):
        scope = self.scope()
        net = self.get_net()

        name_id = None

        if node.name == '~':
            assert type(node.inputs) is type(node.outputs) is list
            name_id = net.add_merger(node.inputs, node.outputs)

        elif node.name in scope:
            vertex = copy.copy(scope[node.name])

            # Apply renaming brackets (if any)
            vertex.rename('in', node.inputs)
            vertex.rename('out', node.outputs)

            # Add vertex to network.
            name_id = net.add_vertex(vertex)

            if isinstance(vertex, Net):
                subnet = self.compile_net(vertex)
                net.node[name_id]['net'] = subnet

        else:
            raise ValueError('Node %s is undefined.' % node.name)

        return set((name_id,))

    def visit_BinaryOp(self, node, children):

        left, right = children['left'], children['right']

        net = self.get_net()

        if node.op == '||':
            # Do nothing
            pass

        elif node.op == '..':
            lmrg, rmrg = net.connect(left, right)

            left |= lmrg
            right |= rmrg

        else:
            raise ValueError('Wrong wiring operator.')

        operands = left | right
        return operands

    def visit_UnaryOp(self, node, children):

        operand = children['operand']

        net = self.get_net()

        if node.op == '*':
            pass

        elif node.op == '\\':
            mrgs = net.connect(operand, operand)
            operand |= mrgs[0] | mrgs[1]

        return operand

    # -------------------------------------------------------------------------

    def visit_PortList(self, node, children):
        return children['ports']

    def visit_ID(self, node, _):
        return node.value

    # -------------------------------------------------------------------------

    def compile(self, ast):
        inputs = self.traverse(ast.inputs)
        outputs = self.traverse(ast.outputs)

        return self.compile_net(
            Net(ast.name, inputs, outputs, ast.decls, ast.wiring)
        )

    def compile_net(self, net):

        scope = self.traverse(net.decls)
        # Declaration corresponding to some box overrides the it.
        non_redefined = {k: v for k, v in self.boxes.items() if k not in scope}
        # Add non-overriden boxes.
        scope.update(non_redefined)

        # Push current scope to stack
        self.scope_stack.append(scope)

        graph = DiGraph()
        self.net_stack.append(graph)

        self.traverse(net.wiring)

        graph.graph['net'] = net
        graph._set_in_out()

        self.scope_stack.pop()
        self.net_stack.pop()

        return graph


class Decl(object):
    name = None
    inputs = None
    outputs = None

    def __init__(self, name, n_in, n_out):
        assert type(name) is str
        assert n_in > 0 and n_out > 0

        self.name = name

        name_ports = lambda n: ['_%s' % (i+1) for i in range(n)]
        self.inputs = name_ports(n_in)
        self.outputs = name_ports(n_out)

    def disambiguate_port(self, side, port, nonce):
        assert side in ('in', 'out')
        attr = side + 'puts'
        ports = getattr(self, attr)

        i = ports.index(port)
        ports[i] = '%s|%d' % (ports[i], nonce)

        return ports[i]

    def rename(self, side, new_names):

        assert side in ('in', 'out')
        attr = side + 'puts'
        current = getattr(self, attr)

        if type(new_names) is list:
            assert len(new_names) == len(current)
            setattr(self, attr, list(new_names))

        elif type(new_names) is dict:
            setattr(self, attr, [new_names.get(n, n) for n in current])

        else:
            raise ValueError('Wrong ports in renaming bracket.')


class Box(Decl):
    func = None

    def __init__(self, name, n_in, n_out, func):
        super().__init__(name, n_in, n_out)
        self.func = func


class Net(Decl):
    decls = None
    wiring = None

    def __init__(self, name, inputs, outputs, decls, wiring):
        super().__init__(name, len(inputs), len(outputs))
        self.rename('in', inputs)
        self.rename('out', outputs)
        self.decls = decls
        self.wiring = wiring


class Sync(Decl):
    ast = None
    macros = None

    def __init__(self, name, inputs, outputs, ast, macros):
        super().__init__(name, len(inputs), len(outputs))
        self.rename('in', inputs)
        self.rename('out', outputs)
        self.ast = ast
        self.macros = macros


class SyncTab(Sync):
    labels = None

    def __init__(self, name, inputs, outputs, ast, macros, labels):
        super().__init__(name, inputs, outputs, ast, macros)
        self.labels = labels