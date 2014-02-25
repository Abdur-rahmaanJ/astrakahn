#!/usr/bin/env python3

from multiprocessing import Process
from time import sleep
import os
import itertools
import communication as comm


def emit_agent(agent_type, channel, msg_generator=None, limit=None, delay=0,
               data=None):

    counter = itertools.count() if not limit else range(limit)

    if delay < 0:
        delay = 0

    agent_process = Process(target=agent, args=(agent_type, channel,
                                                msg_generator, counter,
                                                delay, data,))
    agent_process.start()

    return agent_process


def agent(agent_type, channel, msg_generator, counter, delay, data):

    print(agent_type, os.getpid())

    if agent_type == 'producer':
        assert(msg_generator is not None)
        gen_instance = msg_generator()

        for i in counter:
            channel.ready.wait()
            message = next(gen_instance)
            channel.put(message)

            print(message, "P =", channel.pressure())

            # Configurable delaY
            sleep(delay)

        # Send end of scream mark
        channel.put(comm.SegmentationMark(0))

    elif agent_type == 'consumer':
        assert(data is not None)

        ind = 0
        for i in counter:
            message = channel.get()
            data.put(message)

            if message.end_of_stream():
                print("End of stream: stopping")
                return

            print("\t\t\t\t\t", message, "P =", channel.pressure())

            # Configurable delay
            sleep(delay)

    else:
        assert(False)
