#!/usr/bin/env python3

import asyncio
import logging
import time

import monome
import mido

notes = [0, 56, 50, 47, 45, 42, 38, 35]
channel = 9


class MoStepApp(monome.GridApp):

    def __init__(self):
        super().__init__()
        self.alive = True
        self.port = mido.open_output('fluid:fluid 128:0')
        self.task = asyncio.ensure_future(asyncio.sleep(0))

    def on_grid_ready(self):
        self.data_beat = [[1 for row in range(self.grid.width)] for col in range(self.grid.height)]
        self.data_state = [[0 for row in range(self.grid.width)] for col in range(self.grid.height)]
        self.task = asyncio.ensure_future(self.run())

    def on_grid_key(self, x, y, s):
        logging.debug("button pressed: %s, %s" % (x, y))
        if y == 0:
            if x == self.grid.width - 1 and s == 1:
                self.alive = not self.alive
                self.grid.led_set(self.grid.width - 1, 0, int(not self.alive))
            return
        if s == 1:
            row, col = y, x
            self.data_state[col][row] ^= 1
            self.grid.led_set(x, y, self.data_state[col][row])

    async def run(self):
        try:
            while True:
                if self.alive:
                    self.beat()
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass

    def beat(self):
        for i, col in enumerate(self.data_beat):
            self.grid.led_col(i, 0, col)
            self.send_notes(i)
            time.sleep(0.2)
            self.grid.led_col(i, 0, self.data_state[i])

    def send_notes(self, col_idx):
        print("col_idx: %s, data: %s" % (col_idx, self.data_state[col_idx]))
        for i, r in enumerate(self.data_state[col_idx]):
            print("row idx %s, value %s" % (i, r))
            if r == 1:
                print("sending note %s for row %s" % (notes[i], i))
                msg = mido.Message('note_on', note=notes[i], channel=channel)
                self.port.send(msg)


    def quit(self):
        self.grid.led_all(0)
        self.task.cancel()


def print_ports(heading, port_names):
    print(heading)
    for name in port_names:
        print("    '{}'".format(name))
    print()


if __name__ == '__main__':
    print()
    print_ports('Input Ports:', mido.get_input_names())
    print_ports('Output Ports:', mido.get_output_names())

    loop = asyncio.get_event_loop()
    app = MoStepApp()

    def serialosc_device_added(id, type, port):
        print('connecting to {} ({})'.format(id, type))
        asyncio.ensure_future(app.grid.connect('127.0.0.1', port))

    serialosc = monome.SerialOsc()
    serialosc.device_added_event.add_handler(serialosc_device_added)

    loop.run_until_complete(serialosc.connect())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        app.quit()
