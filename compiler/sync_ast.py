#-----------------------------------------------------------------
# ** ATTENTION **
# This code was automatically generated from the file:
# _sync_ast.cfg
#
# Do not modify it directly. Modify the configuration file and
# run the generator again.
# ** ** *** ** **
#
# AST Node classes.
#
# Copyright (C) 2008-2013, Eli Bendersky
# License: BSD
#-----------------------------------------------------------------


import sys


class Node(object):
    """ Abstract base class for AST nodes.
    """
    def children(self):
        """ A sequence of all children that are Nodes
        """
        pass

    def show(self, buf=sys.stdout, offset=0, attrnames=False, nodenames=False, showcoord=False, _my_node_name=None):
        """ Pretty print the Node and all its attributes and
            children (recursively) to a buffer.

            buf:
                Open IO buffer into which the Node is printed.

            offset:
                Initial offset (amount of leading spaces)

            attrnames:
                True if you want to see the attribute names in
                name=value pairs. False to only see the values.

            nodenames:
                True if you want to see the actual node names
                within their parents.

            showcoord:
                Do you want the coordinates of each Node to be
                displayed.
        """
        lead = ' ' * offset
        if nodenames and _my_node_name is not None:
            buf.write(lead + self.__class__.__name__+ ' <' + _my_node_name + '>: ')
        else:
            buf.write(lead + self.__class__.__name__+ ': ')

        if self.attr_names:
            if attrnames:
                nvlist = [(n, getattr(self,n)) for n in self.attr_names]
                attrstr = ', '.join('%s=%s' % nv for nv in nvlist)
            else:
                vlist = [getattr(self, n) for n in self.attr_names]
                attrstr = ', '.join('%s' % v for v in vlist)
            buf.write(attrstr)

        if showcoord:
            buf.write(' (at %s)' % self.coord)
        buf.write('\n')

        for (child_name, child) in self.children():
            child.show(
                buf,
                offset=offset + 2,
                attrnames=attrnames,
                nodenames=nodenames,
                showcoord=showcoord,
                _my_node_name=child_name)


class NodeVisitor(object):

    def generic_visit(self, node):
        raise NotImplementedError('generic_visit is not implemented')

    def traverse(self, node):
        """ Called if no explicit visitor function exists for a
            node. Implements preorder visiting of the node.
        """

        children = {}

        for c_name, c in node.children():
            if type(c) == list:
                outcome = [self.traverse(i) for i in c]
            else:
                outcome = self.traverse(c)

            children[c_name] = outcome

        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node, children) if visitor else None


class Sync(Node):
    def __init__(self, name, inputs, outputs, decls, states, coord=None):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        self.decls = decls
        self.states = states
        self.coord = coord

    def children(self):
        nodelist = []
        if self.inputs is not None: nodelist.append(("inputs", self.inputs))
        if self.outputs is not None: nodelist.append(("outputs", self.outputs))
        if self.decls is not None: nodelist.append(("decls", self.decls))
        if self.states is not None: nodelist.append(("states", self.states))
        return tuple(nodelist)

    attr_names = ('name',)

class PortList(Node):
    def __init__(self, ports, coord=None):
        self.ports = ports
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("ports", list(self.ports) or []))
        return tuple(nodelist)

    attr_names = ()

class Port(Node):
    def __init__(self, name, depth_exp, coord=None):
        self.name = name
        self.depth_exp = depth_exp
        self.coord = coord

    def children(self):
        nodelist = []
        if self.depth_exp is not None: nodelist.append(("depth_exp", self.depth_exp))
        return tuple(nodelist)

    attr_names = ('name',)

class DepthExp(Node):
    def __init__(self, depth, shift, coord=None):
        self.depth = depth
        self.shift = shift
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('depth','shift',)

class DepthNone(Node):
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class DeclList(Node):
    def __init__(self, decls, coord=None):
        self.decls = decls
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("decls", list(self.decls) or []))
        return tuple(nodelist)

    attr_names = ()

class StoreVar(Node):
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name',)

class StateVar(Node):
    def __init__(self, name, type, coord=None):
        self.name = name
        self.type = type
        self.coord = coord

    def children(self):
        nodelist = []
        if self.type is not None: nodelist.append(("type", self.type))
        return tuple(nodelist)

    attr_names = ('name',)

class IntType(Node):
    def __init__(self, size, coord=None):
        self.size = size
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('size',)

class EnumType(Node):
    def __init__(self, labels, coord=None):
        self.labels = labels
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("labels", list(self.labels) or []))
        return tuple(nodelist)

    attr_names = ()

class StateList(Node):
    def __init__(self, states, coord=None):
        self.states = states
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("states", list(self.states) or []))
        return tuple(nodelist)

    attr_names = ()

class State(Node):
    def __init__(self, name, trans_scopes, coord=None):
        self.name = name
        self.trans_scopes = trans_scopes
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("trans_scopes", list(self.trans_scopes) or []))
        return tuple(nodelist)

    attr_names = ('name',)

class TransScope(Node):
    def __init__(self, trans_stmt, coord=None):
        self.trans_stmt = trans_stmt
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("trans_stmt", list(self.trans_stmt) or []))
        return tuple(nodelist)

    attr_names = ()

class Trans(Node):
    def __init__(self, port, condition, guard, actions, coord=None):
        self.port = port
        self.condition = condition
        self.guard = guard
        self.actions = actions
        self.coord = coord

    def children(self):
        nodelist = []
        if self.condition is not None: nodelist.append(("condition", self.condition))
        if self.guard is not None: nodelist.append(("guard", self.guard))
        nodelist.append(("actions", list(self.actions) or []))
        return tuple(nodelist)

    attr_names = ('port',)

class CondSegmark(Node):
    def __init__(self, depth, coord=None):
        self.depth = depth
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('depth',)

class CondDataMsg(Node):
    def __init__(self, choice, labels, tail, coord=None):
        self.choice = choice
        self.labels = labels
        self.tail = tail
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("labels", list(self.labels) or []))
        return tuple(nodelist)

    attr_names = ('choice','tail',)

class CondEmpty(Node):
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class CondElse(Node):
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class Assign(Node):
    def __init__(self, lhs, rhs, coord=None):
        self.lhs = lhs
        self.rhs = rhs
        self.coord = coord

    def children(self):
        nodelist = []
        if self.rhs is not None: nodelist.append(("rhs", self.rhs))
        return tuple(nodelist)

    attr_names = ('lhs',)

class IntExp(Node):
    def __init__(self, exp, coord=None):
        self.exp = exp
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('exp',)

class DataExp(Node):
    def __init__(self, items, coord=None):
        self.items = items
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("items", list(self.items) or []))
        return tuple(nodelist)

    attr_names = ()

class ItemThis(Node):
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class ItemVar(Node):
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name',)

class ItemExpand(Node):
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name',)

class ItemPair(Node):
    def __init__(self, label, value, coord=None):
        self.label = label
        self.value = value
        self.coord = coord

    def children(self):
        nodelist = []
        if self.value is not None: nodelist.append(("value", self.value))
        return tuple(nodelist)

    attr_names = ('label',)

class Send(Node):
    def __init__(self, msg, port, coord=None):
        self.msg = msg
        self.port = port
        self.coord = coord

    def children(self):
        nodelist = []
        if self.msg is not None: nodelist.append(("msg", self.msg))
        return tuple(nodelist)

    attr_names = ('port',)

class MsgSegmark(Node):
    def __init__(self, depth, coord=None):
        self.depth = depth
        self.coord = coord

    def children(self):
        nodelist = []
        if self.depth is not None: nodelist.append(("depth", self.depth))
        return tuple(nodelist)

    attr_names = ()

class MsgData(Node):
    def __init__(self, choice, data_exp, coord=None):
        self.choice = choice
        self.data_exp = data_exp
        self.coord = coord

    def children(self):
        nodelist = []
        if self.data_exp is not None: nodelist.append(("data_exp", self.data_exp))
        return tuple(nodelist)

    attr_names = ('choice',)

class MsgNil(Node):
    def __init__(self, coord=None):
        self.coord = coord

    def children(self):
        return ()

    attr_names = ()

class Goto(Node):
    def __init__(self, states, coord=None):
        self.states = states
        self.coord = coord

    def children(self):
        nodelist = []
        nodelist.append(("states", list(self.states) or []))
        return tuple(nodelist)

    attr_names = ()

class ID(Node):
    def __init__(self, name, coord=None):
        self.name = name
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name',)

class NUMBER(Node):
    def __init__(self, value, coord=None):
        self.value = value
        self.coord = coord

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('value',)

