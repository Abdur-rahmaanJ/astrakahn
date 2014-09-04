#!/usr/bin/env python3

from queue import Empty as Empty
import pool

import networkx as nx
import network as net


def n_enqueued(nodes):
    '''
    Count the number of messages waiting for processing in inputs queues of the
    given nodes.
    It's temporary and expensive alternative to network schedule.
    '''
    n_msgs = 0

    for node_id in nodes:
        node = n.node(node_id)
        if node['type'] != 'vertex':
            continue
        vertex = node['obj']

        for q in vertex.inputs:
            n_msgs += q['queue'].size()

    return n_msgs


if __name__ == '__main__':

    n = net.load(input_file='compiler/a.out')

    # Processing pool
    pm = pool.PoolManager(2)
    pm.start()

    # Network execution

    while True:
        # Traversal
        nodes = list(nx.dfs_postorder_nodes(n.network, n.root))

        for node_id in nodes:
            node = n.node(node_id)

            if node['type'] == 'net':
                # Skip: we are interested in boxes only.
                continue

            elif node['type'] == 'vertex':
                vertex = node['obj']

                # 1. Test if the box is already running. If it is, skip it.
                if vertex.busy:
                    continue

                # 2. Test if the conditions on channels are sufficient for the
                #    box execution. Is they're not, skip the box.
                if not vertex.is_ready():
                    continue

                # 3. Get input message and form a list of arguments for the
                #    box function to apply.
                args = vertex.fetch()

                if args is None:
                    # 3.1 Input message were handled in fetch(), box execution
                    #     is not required.
                    continue

                # 4. Assemble all the data needed for the task to send in
                #    the processing pool.
                task_data = {'vertex_id': vertex.id, 'args': args}

                # 5. Send box function and task data to processing pool.
                #    NOTE: this call MUST always be non-blocking.
                pm.enqueue(vertex.core, task_data)
                vertex.busy = True

        # Check for responses from processing pool.

        while True:
            try:
                # Wait responses from the pool if there're no other messages in
                # queues to process.
                need_block = (n_enqueued(nodes) == 0)

                #if need_block:
                #    print("NOTE: waiting result")

                # Vertex response.
                response = pm.out_queue.get(need_block)

                if not n.has_node(response.vertex_id):
                    raise ValueError('Vertex corresponsing to the response '
                                     'does not exist.')

                vertex = n.node(response.vertex_id)['obj']

                # Commit the result of computation, e.g. send it to destination
                # vertices.
                vertex.commit(response)
                vertex.busy = False

            except Empty:
                break

    # Cleanup.
    pm.finish()
