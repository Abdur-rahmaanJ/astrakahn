#!/usr/bin/env python3

from components import *
from network import Network
from compiler.sync import parse as sync_parse
from compiler.sync.backend import SyncBuilder
from . import ast

import re
import os.path


class NetBuilder(ast.NodeVisitor):

    def __init__(self, cores, path):
        self.cores = cores
        self.scopes = []

        self.node_id = 0

        self.path = path
        self.network = None

    def generic_visit(self, node, children):
        print(node)

    def scope(self):
        # Stack of scopes mustn't be empty
        assert(self.scopes)

        # Copy the scope at the top of the stack
        scope = self.scopes[-1].copy()

        # Add core entries.
        scope.update(self.cores)

        return scope

    #--------------------------------------------------------------------------

    def visit_Synchroniser(self, node, children):
        return ('sync', node, node.name)

    def visit_Morphism(self, node, children):
        'final'
        return ('morph', node, node.map)

    def visit_Net(self, node, children):
        'final'
        return ('net', node, node.name)

    def visit_DeclList(self, node, children):
        return children['decls']

    #--------------------------------------------------------------------------

    def visit_Vertex(self, node, children):
        scope = self.scope()
        obj = None

        if node.name in scope:
            type, decl, *_ = scope[node.name]

            if type == 'net':
                obj = self.compile_net(decl, node)

            elif type == 'morph':
                raise NotImplementedError('¯\_(ツ)_/¯')

            elif type == 'sync':
                obj = self.compile_sync(decl, node)

            elif type == 'core':
                obj = self.compile_box(decl, node)

            else:
                raise ValueError('Node %s is of unknown type: `%s\''
                                 % (node.name, type))

        elif node.name == '~':
            obj = self.compile_merger(list(node.inputs.values()),
                                      list(node.outputs.values()))

        else:
            raise ValueError('Node %s is undefined.' % node.name)

        assert(obj is not None)
        return set((obj,))

    def visit_BinaryOp(self, node, children):

        left = self._flatten(children['left'])
        right = self._flatten(children['right'])

        if node.op == '||':
            # Parallel connection: no wiring performs.
            pass

        elif node.op == '..':
            # Serial connection: all outputs of the first operand are wired to
            # identically named inputs of the second operand if they exist.

            _, left_outputs = self._global_ports(left)
            right_inputs, _ = self._global_ports(right)

            # Compute identical port names.
            common_ports = left_outputs.keys() & right_inputs.keys()

            for name in common_ports:
                # Channels with the same names must be already merged.
                assert(len(left_outputs[name]) == 1
                       and len(right_inputs[name]) == 1)

                # Make `physical' connection between ports.
                self._add_wire(left_outputs[name][0], right_inputs[name][0])

        else:
            raise ValueError('Wrong wiring operator.')

        operands = left | right
        return operands

    def visit_UnaryOp(self, node, children):

        operand = self._flatten(children['operand'])
        inputs, outputs = self._global_ports(operand)

        if node.op == '*':
            pass

        elif node.op == '\\':

            # Compute identical port names.
            common_ports = inputs.keys() & outputs.keys()

            for name in common_ports:
                # Channels with the same names must be already merged.
                assert(len(inputs[name]) == 1 and len(outputs[name]) == 1)

                # Make `physical' connection between ports.
                self._add_wire(outputs[name][0], inputs[name][0])

        return operand

    #--------------------------------------------------------------------------

    def visit_PortList(self, node, children):
        return children['ports']

    def visit_ID(self, node, _):
        return node.value

    #--------------------------------------------------------------------------

    def compile(self, ast):
        obj = self.compile_net(ast)
        network = Network(obj, self.node_id)

        return network

    def compile_sync(self, decl, vertex):

        # Path of sync source: if it is not provided from net, use path of
        # net source file.
        if not decl.path:
            sync_path = self.path
        else:
            if decl.path[0] == '/':
                sync_path = decl.path
            else:
                sync_path = os.path.join(self.path, decl.path)

        sync_file = os.path.join(sync_path, '%s.sync' % decl.name)

        if not (os.path.isfile(sync_file) and os.access(sync_file, os.R_OK)):
            raise ValueError('File for sync `%s\' is not found or cannot be '
                             'read.' % decl.name)

        with open(sync_file, 'r') as f:
            src_code = f.read()

        sync_ast = sync_parse(src_code, decl.macros)

        sb = SyncBuilder()
        obj = sb.traverse(sync_ast)
        obj.id = self._set_id()

        return obj

    def compile_net(self, net, vertex=None):
        assert(type(net) == ast.Net)

        decls = self.traverse(net.decls)

        scope = {}
        for d in decls:
            scope[d[2]] = d

        # Push current scope to stack
        self.scopes.append(scope)

        nodes = self.traverse(net.wiring)
        nodes = self._flatten(nodes)

        inputs = self.traverse(net.inputs)
        outputs = self.traverse(net.outputs)

        obj = Net(net.name, inputs, outputs, nodes)

        nodes_inputs, nodes_outputs = self._global_ports(nodes)

        # Mount inputs.
        for i, name in enumerate(inputs):
            if name not in nodes_inputs:
                raise ValueError('There is no input port named `%s\' '
                                 'in the net.' % name)
            ports = nodes_inputs[name]
            assert(len(ports) == 1)
            obj.inputs[i] = ports[0][1]

        # Mount outputs.
        for i, name in enumerate(outputs):
            if name not in nodes_outputs:
                raise ValueError('There is no output port named `%s\' '
                                 'in the net.' % name)
            ports = nodes_outputs[name]
            assert(len(ports) == 1)
            obj.outputs[i] = ports[0][1]

        # Pop the scope from stack
        self.scopes.pop()

        obj.id = self._set_id()
        return obj

    def compile_box(self, box, vertex):

        # Match box specification from docstring.
        spec = str(box.__doc__).strip()
        m = re.match('([1-9]\d*)(T|I|DO|DU|H)', spec)

        if m:
            n_out, cat = m.groups()
            n_out = int(n_out)

            if cat[0] == 'H':
                n_in = n_out
                n_out = n_in
            else:
                n_in = 2 if cat[0] == 'D' else 1

            inputs = self._gen_ports(n_in, vertex.inputs)
            outputs = self._gen_ports(n_out, vertex.outputs)

            # Assign box class
            if cat == 'T':
                obj = Transductor(vertex.name, inputs, outputs, box)

            elif cat == 'I':
                obj = Inductor(vertex.name, inputs, outputs, box)

            elif cat[0] == 'D':
                ordered = True if cat[1] != 'U' else False
                segmentable = True if cat[1] == 'S' or cat[1] == 'U' else False

                obj = DyadicReductor(vertex.name, inputs, outputs, box,
                                     ordered, segmentable)

            elif cat == 'H':
                obj = Executor(vertex.name, inputs, outputs, box)

            else:
                raise ValueError('Wrong box category: %s:%s' % (vertex.name,
                                                                cat))
            obj.id = self._set_id()
            return obj

        else:
            raise ValueError('Wrong box specification: %s:%s' % (vertex.name,
                                                                 spec))

    def compile_merger(self, inputs, outputs):

        if len(inputs) == 1:
            merger_name = '%s_1_to_%s' % (inputs[0], '-'.join(set(outputs)))
        elif len(outputs) == 1:
            merger_name = '%s_to_%s_1' % ('-'.join(set(inputs)), outputs[0])
        else:
            merger_name = '%s_to_%s' % ('-'.join(set(inputs)),
                                        '-'.join(set(outputs)))

        obj = Merger(merger_name, inputs, outputs)
        obj.id = self._set_id()

        return obj

    #--------------------------------------------------------------------------

    def _set_id(self):
        t = self.node_id
        self.node_id += 1
        return t

    def _gen_ports(self, n, rename):
        return [(rename.get(i, '_%s' % i)) for i in range(n)]

    def _global_ports(self, vertices):
        inputs = {}
        outputs = {}

        for v in vertices:
            fp = v.free_ports()

            # Free inputs
            for name, ports in fp[0].items():
                inputs[name] = inputs.get(name, []) + ports

            # Free outputs
            for name, ports in fp[1].items():
                outputs[name] = outputs.get(name, []) + ports

        return (inputs, outputs)

    def _flatten(self, vertices):

        mergers = set()

        inputs, outputs = self._global_ports(vertices)

        # Merger for inputs
        for name, ports in inputs.items():
            np = len(ports)

            if np > 1:
                obj = self.compile_merger([name], [name]*np)
                mergers.add(obj)

                for i, port in enumerate(ports):
                    self._add_wire((obj.id, obj.outputs[i]), port)

        # Merger for outputs
        for name, ports in outputs.items():
            np = len(ports)

            if np > 1:
                obj = self.compile_merger([name]*np, [name])
                mergers.add(obj)

                for i, port in enumerate(ports):
                    self._add_wire(port, (obj.id, obj.inputs[i]))

        return mergers | vertices

    def _add_wire(self, pa, pb):

        src_id, src_port = pa
        dst_id, dst_port = pb

        src_port['to'] = dst_port['queue']
        src_port['dst'] = (dst_id, dst_port['id'])
        dst_port['src'] = (src_id, src_port['id'])

    #--------------------------------------------------------------------------