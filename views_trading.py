import functools
import logging
import tkinter as tk
from catan.board import PortType, Terrain, Port
from catan.trading import CatanTrade

can_do = {
    True: tk.NORMAL,
    False: tk.DISABLED,
    None: tk.DISABLED
}


class TradeFrame(tk.Frame):
    """
    class TradeFrame is a tkinter Frame containing a dynamic trading interface

    TradeFrame contains a swappable frame. The contents of the frame are responsible for
    swapping themselves out when user input dictates it (eg click button -> swap frame)

    TradeFrame is used inside the larger GameToolbarFrame.

    TradeFrame observes the game object. On notify, it:
    - calls the swappable frame's notify() method
    - sets the state of its buttons
    """
    def __init__(self, master, game):
        super(TradeFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.trade = CatanTrade(giver=self.game.get_cur_player())

        self.title = tk.Label(self, text="Trade")
        self.frame = WithWhoFrame(self)
        self.cancel = tk.Button(self, text='Cancel', state=tk.DISABLED, command=self.on_cancel)
        self.make_trade = tk.Button(self, text='Make Trade', state=tk.DISABLED, command=self.on_make_trade)

        self.title.grid(sticky=tk.W)
        self.frame.grid()
        self.cancel.grid(row=2, column=0, sticky=tk.EW)
        self.make_trade.grid(row=2, column=1, sticky=tk.EW)

        self.set_states()

    def notify(self, observable):
        self.frame.notify(self)
        self.set_states()

    def set_states(self):
        self.make_trade.configure(state=can_do[self.can_make_trade()])
        self.cancel.configure(state=can_do[self.can_cancel()])

    def set_frame(self, frame):
        self.frame.grid_remove()
        self.frame = frame
        self.frame.grid(row=1)
        self.notify(None)

    def can_make_trade(self):
        return self.frame.can_make_trade()

    def can_cancel(self):
        return self.frame.can_cancel()

    def on_make_trade(self):
        self.trade.set_giver(self.game.get_cur_player())
        logging.debug('trade MAKE: {} {} {} {}'.format(self.trade.giver(),
                                                       self.trade.giving(),
                                                       self.trade.getter(),
                                                       self.trade.getting()))
        self.game.trade(self.trade)

        self.on_cancel()
        self.game.notify(None)

    def on_cancel(self):
        self.trade = CatanTrade(giver=self.game.get_cur_player())
        self.set_frame(WithWhoFrame(self))


class WithWhoFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WithWhoFrame, self).__init__(*args, **kwargs)
        self.master.game.observers.add(self)

        self.player = tk.Button(self, text='Player', command=self.on_player)
        self.port = tk.Button(self, text='Port', command=self.on_port)

        self.player.pack(side=tk.LEFT)
        self.port.pack(side=tk.RIGHT)

        self.set_states()

    def notify(self, observable):
        self.set_states()

    def set_states(self):
        self.player.configure(state=can_do[self.master.game.state.can_trade()])
        self.port.configure(state=can_do[self.master.game.state.can_trade()])

    def on_player(self):
        self.master.set_frame(WithWhichPlayerFrame(self.master))

    def on_port(self):
        self.master.set_frame(WithWhichPortFrame(self.master))

    def can_make_trade(self):
        return False

    def can_cancel(self):
        return False


class WithWhichPlayerFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WithWhichPlayerFrame, self).__init__(*args, **kwargs)
        self.master.game.observers.add(self)

        self.player_btns = list()
        count = 0
        for p in self.master.game.players.copy():
            b = tk.Button(self, text='{}'.format(p), state=tk.DISABLED, command=functools.partial(self.on_player, p))
            b.grid(row=count // 2, column=count % 2, sticky=tk.NSEW)
            self.player_btns.append(b)
            count += 1

        self.set_states()

    def notify(self, observable):
        self.set_states()

    def set_states(self):
        for player_btn, player in zip(self.player_btns, self.master.game.players.copy()):
            state = (self.master.game.state.can_trade()
                     and self.master.game.get_cur_player() != player)
            player_btn.configure(state=can_do[state])

    def can_make_trade(self):
        return False

    def can_cancel(self):
        return True

    def on_player(self, player):
        logging.debug('trade: player={} selected'.format(player))
        self.master.trade.set_getter(player)
        self.master.set_frame(WhichResourcesFrame(self.master))


class WithWhichPortFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WithWhichPortFrame, self).__init__(*args, **kwargs)
        self.master.game.observers.add(self)

        # grid of buttons
        # x x x
        # x x x
        # any in topleft (functions as both 3:1 and 4:1), others have text=terrain.value
        self.port_btns = list()
        count = 0
        for p_type in PortType:
            b = tk.Button(self, text='{}'.format(p_type.value), state=tk.DISABLED,
                          command=functools.partial(self.on_port, p_type))
            b.grid(row=count // 4, column=count % 4, sticky=tk.NSEW)
            self.port_btns.append(b)
            count += 1

        self.set_states()

    def notify(self, observable):
        self.set_states()

    def set_states(self):
        can_trade = self.master.game.state.can_trade()
        for btn, port_type in zip(self.port_btns, PortType):
            if port_type == PortType.any4:
                btn.configure(state=can_do[can_trade])
            else:
                btn.configure(state=can_do[can_trade and self.master.game.cur_player_has_port_type(port_type)])

    def on_port(self, port_type):
        logging.debug('trade: port_type={} selected'.format(port_type))
        self.master.trade.set_getter(Port(1, 'OO', port_type))
        self.master.set_frame(WhichResourcesFrame(self.master))

    def can_make_trade(self):
        return False

    def can_cancel(self):
        return True


class WhichResourcesFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WhichResourcesFrame, self).__init__(*args, **kwargs)
        self.master.game.observers.add(self)

        self.input = WhichResourcesInputFrame(self)
        self.output = WhichResourcesOutputFrame(self)

        self.input.pack()
        self.output.pack()

        self.notify()

    def notify(self, observable=None):
        self.input.notify()
        self.output.notify()

    def can_make_trade(self):
        return True

    def can_cancel(self):
        return True


class WhichResourcesInputFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WhichResourcesInputFrame, self).__init__(*args, **kwargs)

        self.give_label = tk.Label(self, text='give')
        self.get_label = tk.Label(self, text='get')

        self.give_btns = list()
        self.get_btns = list()
        for t in filter(lambda t: t != Terrain.desert, Terrain):
            self.give_btns.append(tk.Button(self, text=t.value, command=functools.partial(self.on_give, t)))
            self.get_btns.append(tk.Button(self, text=t.value, command=functools.partial(self.on_get, t)))

        self.give_label.grid(row=0, column=0, sticky=tk.W)
        for column, btn in enumerate(self.give_btns, 1):
            btn.grid(row=0, column=column, sticky=tk.NSEW)

        self.get_label.grid(row=1, column=0, sticky=tk.W)
        for column, btn in enumerate(self.get_btns, 1):
            btn.grid(row=1, column=column, sticky=tk.NSEW)

        self.set_states()

    def notify(self, observable=None):
        """WhichResourcesFrame calls notify()"""
        self.set_states()

    def set_states(self):
        getter = self.trade().getter()
        num_getting = self.trade().num_getting()
        giving_types = [giving_type.value for _, giving_type in self.trade().giving()]
        for btn in self.get_btns:
            if hasattr(getter, 'type') in PortType:
                btn.configure(state=can_do[num_getting < 1
                                           and btn['text'] != getter.type.value
                                           and btn['text'] not in giving_types])

    def on_give(self, terrain):
        getter = self.trade().getter()
        num = 1
        if hasattr(getter, 'type'):
            if getter.type == PortType.any4:
                num = 4
            elif getter.type == PortType.any3:
                num = 3
            elif getter.type in PortType:
                num = 2
        self.trade().give(terrain, num=num)
        self.master.notify()

    def on_get(self, terrain):
        self.trade().get(terrain)
        self.master.notify()

    def trade(self):
        return self.master.master.trade


class WhichResourcesOutputFrame(tk.Frame):
    def __init__(self, *args, **kwargs):
        super(WhichResourcesOutputFrame, self).__init__(*args, **kwargs)

        self.giving_str = tk.StringVar()
        self.getting_str = tk.StringVar()

        tk.Label(self, textvariable=self.giving_str).pack()
        tk.Label(self, textvariable=self.getting_str).pack()

        self.set_states()

    def notify(self, observable=None):
        """WhichResourcesFrame calls notify()"""
        self.set_states()

    def set_states(self):
        self.giving_str.set('giving to {}: {}'.format(self.trade().getter(), self.trade().giving()))
        self.getting_str.set('getting from {}: {}'.format(self.trade().getter(), self.trade().getting()))
        logging.debug('trade: giving_str="{}", getting_str="{}" (trade={})'.format(
            self.giving_str.get(),
            self.getting_str.get(),
            self.trade()
        ))

    def trade(self):
        return self.master.master.trade


# ##
# # Players
# #
# self.player_frame = tk.Frame(self)
#

#
# ##
# # Ports
# #
# self.port_frame = tk.Frame(self)
# resources = list(t.value for t in Terrain if t != Terrain.desert)
# tk.Label(self.port_frame, text="Trade: Ports").grid(row=0, column=0, sticky=tk.W)
# self.port_give = tk.StringVar(value=resources[0])
# self.port_get = tk.StringVar(value=resources[1])
# tk.OptionMenu(self.port_frame, self.port_give, *resources).grid(row=1, column=0, sticky=tk.NSEW)
# tk.OptionMenu(self.port_frame, self.port_get, *resources).grid(row=1, column=1, sticky=tk.NSEW)
# self.btn_31 = tk.Button(self.port_frame, text='3:1', command=self.on_three_for_one)
# self.btn_31.grid(row=1, column=2, sticky=tk.NSEW)
# self.btn_21 = tk.Button(self.port_frame, text='2:1', command=self.on_two_for_one)
# self.btn_21.grid(row=1, column=3, sticky=tk.NSEW)
#
# ##
# # Place elements in frame
# #
# self.label_player.grid(row=0, sticky=tk.W)
# for i, button in enumerate(self.player_buttons):
#     button.grid(row=1 + i // 2, column=i % 2, sticky=tk.EW)
#
# self.player_frame.pack(anchor=tk.W)
# self.port_frame.pack(anchor=tk.W)


