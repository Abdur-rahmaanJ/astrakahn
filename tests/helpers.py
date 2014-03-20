#!/usr/bin/env python3

import sys
import os

# SLOPPY HACK
sys.path.insert(0, os.path.dirname(__file__) + '/..')

import components
import communication as comm
import helpers
from copy import copy
from time import sleep
import itertools
from multiprocessing import Process, Queue


class Agent:

    def __init__(self, channel, delay, limit):
        self.channel = channel
        self.delay = delay if delay > 0 else 0
        self.counter = itertools.count() if not limit else range(limit)
        self.thread = None

    def protocol(self):
        raise NotImplementedError("Behaviour of the agent is not implemented.")

    def run(self):
        self.thread = Process(target=self.protocol, args=())
        self.thread.start()
        return self.thread


class Producer(Agent):
    def __init__(self, channel, msg_iterator, delay=0, limit=None):
        super(Producer, self).__init__(channel, delay, limit)
        self.msg_iterator = msg_iterator

    def protocol(self):
        for i in self.counter:
            self.channel.ready.wait()

            try:
                message = next(self.msg_iterator)
                message = comm.DataMessage(message) \
                    if not isinstance(message, comm.Message) else message

            except StopIteration:
                # Send end of scream mark
                self.channel.put(comm.SegmentationMark(0))
                break

            self.channel.put(message)

            if message.end_of_stream():
                return

            sleep(self.delay)


class Consumer(Agent):
    def __init__(self, channel, output_queue=None, delay=0, limit=None):
        super(Consumer, self).__init__(channel, delay, limit)
        self.output_queue = output_queue if output_queue is not None else None

    def protocol(self):
        for i in self.counter:
            message = self.channel.get()

            if self.output_queue:
                self.output_queue.put(message)

            if message.end_of_stream():
                return

            # Configurable delay
            sleep(self.delay)


def run_box(box_type, function, passport, input_list):

    if not (box_type == components.Transductor
            or box_type == components.Inductor
            or box_type == components.Reductor):
        raise ValueError("Wrong box type")

    try:
        # Infer the number of inputs and outputs from the passport
        box_inputs = (len(passport['input']),
                      {i: '' for i in range(len(passport['input']))})
        box_outputs = (len(passport['output']),
                       {i: '' for i in range(len(passport['output']))})

        # Create a box
        box = box_type(inputs=(1, {0: 'a'}), outputs=(1, {0: 'a'}),
                       box_function=components.BoxFunction(function, passport))
        box.start()

        producer = Producer(box.input_channels[0], iter(input_list))
        producer.run()

        main_output = Queue()

        consumer = Consumer(box.output_channels[0], main_output)
        consumer.run()

        # Collect the output
        result = []
        while True:
            msg = main_output.get()
            if msg.end_of_stream():
                break
            result += [msg.content]

        box.thread.join()
        producer.thread.join()
        consumer.thread.join()

        return result

    except KeyboardInterrupt:
        box.stop()
        producer.thread.terminate()
        consumer.thread.terminate()
        print("Network has been stopped by user.")


class Testable:

    def test(self):
        box_name = self.__class__.__name__
        print(box_name + ": ", end="")

        try:
            result = run_box(self.type, self.function, self.passport,
                             self.test_input)

            if result == self.reference_output:
                print("Test passed")
            else:
                print("Test FAILED")

        except AttributeError as e:
            print("Testing attributes must be provided: " + str(e))