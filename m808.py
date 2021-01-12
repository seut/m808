#!/usr/bin/env python3

import asyncio
import logging

import mido
import monome

notes = [56, 50, 47, 45, 42, 38, 35]


class M808(monome.GridApp):

    def __init__(self, midi_out, speed=0.2, speed_step=0.02, midi_channel=9, pages=4):
        super().__init__()
        self.alive = True
        self.midi_out = mido.open_output(midi_out)
        self.midi_channel = midi_channel
        self.task = asyncio.ensure_future(asyncio.sleep(0))
        self.speed = speed
        self.speed_step = speed_step
        self.data_beat = []
        self.data_state = []
        self.pages = pages
        self.current_page = 0

    def on_grid_ready(self):
        # initialize beat + state structures based on the detected grid
        self.data_beat = [[1 for row in range(self.grid.width)] for col in range(self.grid.height)]
        self.init_state()
        self.task = asyncio.ensure_future(self.run())

    def on_grid_disconnect(self):
        self.grid.led_all(0)
        self.task.cancel()

    def init_state(self):
        self.data_state = []
        for p in range(self.pages):
            self.data_state.append(self.get_clear_page(p))
        self.apply_state()

    def get_clear_page(self, page) -> list:
        state = [[0 for row in range(self.grid.width)] for col in range(self.grid.height)]
        # page button
        state[page][0] = 1
        # start stop button
        state[self.grid.width - 1][0] = int(self.alive)
        return state

    def apply_state(self):
        for i, col in enumerate(self.data_beat[self.current_page]):
            self.grid.led_col(i, 0, self.data_state[self.current_page][i])

    def on_grid_key(self, x, y, s):
        logging.debug("button pressed: %s, %s" % (x, y))
        # top control button row
        if y == 0:
            if s == 1:
                # start/stop button
                if x == self.grid.width - 1:
                    self.alive = not self.alive
                    self.grid.led_set(self.grid.width - 1, 0, int(self.alive))
                    for p in range(self.pages):
                        self.data_state[p][self.grid.width - 1][0] = int(self.alive)
                # +tempo button
                elif x == self.grid.width - 2 and self.speed - 0.05 > 0.001:
                    self.grid.led_set(self.grid.width - 2, 0, 1)
                    self.speed -= self.speed_step
                    logging.debug("Current speed: %s" % self.speed)
                    self.grid.led_set(self.grid.width - 2, 0, 0)
                # -tempo button
                elif x == self.grid.width - 3:
                    self.grid.led_set(self.grid.width - 3, 0, 1)
                    self.speed += self.speed_step
                    logging.debug("Current speed: %s" % self.speed)
                    self.grid.led_set(self.grid.width - 3, 0, 0)
                # clear page button
                elif x == 4:
                    self.grid.led_set(4, 0, 1)
                    self.data_state[self.current_page] = self.get_clear_page(self.current_page)
                    self.apply_state()
                    self.grid.led_set(4, 0, 0)
                # page buttons
                elif x < 4:
                    self.current_page = x
                    self.apply_state()
            return
        # 7 tracks
        if s == 1:
            row, col = y, x
            self.data_state[self.current_page][col][row] ^= 1
            self.grid.led_set(x, y, self.data_state[self.current_page][col][row])

    async def run(self):
        try:
            while True:
                if self.alive:
                    await self.beat()
                else:
                    await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass

    async def beat(self):
        for i, col in enumerate(self.data_beat):
            col[0] = self.data_state[self.current_page][i][0]
            self.grid.led_col(i, 0, col)
            self.send_notes(i)
            await asyncio.sleep(self.speed)
            self.grid.led_col(i, 0, self.data_state[self.current_page][i])

    def send_notes(self, col_idx):
        for i, r in enumerate(self.data_state[self.current_page][col_idx]):
            if i > 0 and r == 1:
                logging.debug("sending note %s for row %s" % (notes[i-1], i))
                msg = mido.Message('note_on', note=notes[i-1], channel=self.midi_channel)
                self.midi_out.send(msg)

    def quit(self):
        self.grid.led_all(0)
        self.task.cancel()


def print_ports(heading, port_names):
    print(heading)
    for name in port_names:
        print("    '{}'".format(name))
    print()


def print_midi_info():
    print()
    print_ports('Input MIDI Ports:', mido.get_input_names())
    print_ports('Output MIDI Ports:', mido.get_output_names())


if __name__ == '__main__':
    print_midi_info()

    loop = asyncio.get_event_loop()
    app = M808('fluid:fluid 128:0')

    def serialosc_device_added(id, type, port):
        logging.info('connecting to {} ({})'.format(id, type))
        asyncio.ensure_future(app.grid.connect('127.0.0.1', port))

    serialosc = monome.SerialOsc()
    serialosc.device_added_event.add_handler(serialosc_device_added)

    loop.run_until_complete(serialosc.connect())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        app.quit()
