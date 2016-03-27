from collections import deque
from itertools import chain

from multiprocessing import Process, Queue, Manager, Lock
from queue import Empty as Empty
from .stream import Stream, Message
from . import utils

import networkx as nx

__all__ = ['DiGraph', 'Worker', 'Runner']


class DiGraph(nx.DiGraph):

    def next_pc(self, old_pc, channel):
        bb_name, index = old_pc
        bb_stmts = self.node[bb_name]['stmts']

        assert index < len(bb_stmts)

        next_index = (index + 1) % len(bb_stmts)

        if next_index:
            # Next vertex on the same basic block.
            return (bb_name, next_index)

        else:
            # Go to the next basic block according to the channel.
            try:
                _, next_bb, _ = next(filter(lambda x: channel in x[2]['chn'],
                                            self.out_edges((bb_name, ),
                                                           data=True)))

            except StopIteration as si:
                raise AssertionError(
                    'Cannot find appropriate basic block'
                ) from si

            return (next_bb, next_index)


class Worker:

    def __init__(self, wid, cfg, tasks, queues):

        self.wid = wid
        self.nonce = 0
        self.cfg = cfg
        self.queues = queues
        self.n_workers = len(queues)

        self.tasks = deque(tasks)
        self.tasks_suspended = deque(tasks)

    @property
    def is_ready(self):
        return bool(self.tasks)

    def event_loop(self):

        while True:
            try:
                is_blocked = not self.is_ready
                r = self.queues[self.wid].get(is_blocked)
            except Empty:
                break

            if r[0] == 'msg':
                m = Message(*r[1:4])

                channel, pc = r[4:]
                m.set_loc(channel, pc)

                self.tasks.append(m)

            # print('New req at worker %d: %s' % (self.wid, r))

        return True

    def send(self, wid, data):
        self.queues[wid].put(data)

    def run(self, sessions, session_lock):

        while self.event_loop():

            task = self.tasks.popleft()

            assert not (len(task.id) % 2)

            bb_name, index = task.pc
            bb_stmts = self.cfg.node[bb_name]['stmts']
            func, inputs, outputs = bb_stmts[index]

            if len(inputs) == 1:
                # Execute vertex
                assert inputs[0] == task.channel

                #  print(func.__closure__[0].cell_contents.__name__, self.wid, task.content)

                if func.cat == 'transductor':

                    output = func(task.channel, task.content)

                    # For now expect transductors eager to have easier bracket
                    # handling.
                    assert len(outputs) == len(output)

                    for port, (channel, msg) in enumerate(zip(outputs, output)):

                        next_pc = self.cfg.next_pc(task.pc, channel)

                        m = Message(msg, task.id_eye(port))
                        m.set_loc(channel, next_pc)

                        self.tasks.append(m)

                elif func.cat == 'inductor':

                    output = func(task.channel, task.content)

                    # Lists corresponding to outputs of each port.
                    seqs = ([item] for item in output)

                    # Iterate inductor until continuation is not issues.
                    # NOTE: in current implementation the whole sequence is
                    # generated in one execution step while originally it was
                    # supposed to output it `lazyly'.
                    while func.cont:
                        output = func(None, func.cont)
                        seqs = map(lambda a, b: a + [b], seqs, output)

                    # --

                    task_seqs = tuple([] for i in outputs)

                    for port, (channel, seq, ts) in enumerate(zip(outputs, seqs, task_seqs)):

                        next_pc = self.cfg.next_pc(task.pc, channel)

                        for index, msg in enumerate(seq):

                            m = Message(msg, task.id_up(port, index))
                            m.set_loc(channel, next_pc)

                            ts.append(m)

                        ts[-1].sm_inc(task.bracket)

                    # TODO: proper task distribution. Critical part of
                    # performance, implement something more sophisticated.
                    tasks_parted = utils.partition(chain(*task_seqs),
                                                   self.n_workers)

                    self.tasks.extend(tasks_parted[self.wid])

                    for wid, tasks in enumerate(tasks_parted):
                        if wid != self.wid:
                            for t in tasks:
                                self.send(wid, t.dump())

                elif func.cat == 'reductor':
                    raise NotImplementedError('reductor')

                elif func.cat == 'output':
                    func(task.channel, (task.content, task.id))

            else:
                # Synchronisation point for inputs
                pass

            del task

#------------------------------------------------------------------------------

class Runner:

    def __init__(self, cfg, __input__, n_workers=2):

        self.tasks = []
        self.workers = []
        self.processes = None

        stream_factory = Stream()

        for channel, msgs in __input__.items():

            stream = stream_factory.read(msgs)

            init_pc = (cfg.entry[channel], 0)

            for msg in stream:
                msg.channel = channel
                msg.pc = init_pc
                self.tasks.append(msg)

            tasks_parted = utils.partition(self.tasks, n_workers)

            queues = [Queue() for i in range(n_workers)]

            self.workers = [Worker(wid, cfg, tasks, queues)
                            for wid, tasks in enumerate(tasks_parted)]

    def run(self):
        manager = Manager()

        sessions = manager.dict()
        session_lock = Lock()

        self.processes = [Process(target=w.run, args=(sessions, session_lock))
                          for w in self.workers]

        for p in self.processes:
            p.start()

        for p in self.processes:
            p.join()
