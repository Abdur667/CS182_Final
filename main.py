import tkinter
import pprint
import logging
import argparse
from catan.board import Board
from catan.game import Game

import views


class CatanSpectator(tkinter.Frame):

    def __init__(self, options=None, *args, **kwargs):
        print('\n\n\n\n*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\n\n\n\n\
                !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!STARTING NEW GAME!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n\n\n\
*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\
*******************************************************************************************************\n\n\n\n')
        super(CatanSpectator, self).__init__()
        self.options = options or dict()
        # print('initializing board from CatanSpectator')
        board = Board(board=self.options.get('board'),
                      terrain=self.options.get('terrain'),
                      numbers=self.options.get('numbers'),
                      ports=self.options.get('ports'),
                      pieces=self.options.get('pieces'),
                      players=self.options.get('players'))
        # print('initializing game from CatanSpectator')
        self.game = Game(board=board, pregame=self.options.get('pregame'), use_stdout=self.options.get('use_stdout'))
        # print('adding observer to game')
        self.game.observers.add(self)
        # print('self.game.observers={}'.format(self.game.observers))
        self._in_game = self.game.state.is_in_game()

        self._board_frame = views.BoardFrame(self, self.game)
        self._log_frame = views.LogFrame(self, self.game)
        self._board_frame.grid(row=0, column=0, sticky=tkinter.NSEW)
        self._log_frame.grid(row=1, column=0, sticky=tkinter.W)

        self._board_frame.redraw()

        self._setup_game_toolbar_frame = views.SetupGameToolbarFrame(self, self.game)
        self._toolbar_frame = self._setup_game_toolbar_frame
        self._toolbar_frame.grid(row=0, column=1, rowspan=2, sticky=tkinter.N)
        print('finished initializing board, game, and drawing shit\n')

        # self.lift()

    def notify(self, observable):
        print('notify method of catan-spectator hit')
        was_in_game = self._in_game
        self._in_game = self.game.state.is_in_game()
        if was_in_game and not self.game.state.is_in_game():
            logging.debug('we were in game, NOW WE\'RE NOT')
            self._toolbar_frame.grid_forget()
            self._toolbar_frame = self._setup_game_toolbar_frame
            self._toolbar_frame.grid(row=0, column=1, rowspan=2, sticky=tkinter.N)
        elif not was_in_game and self.game.state.is_in_game():
            logging.debug('we were not in game, NOW WE ARE')
            self._toolbar_frame.grid_forget()
            self._toolbar_frame = views.GameToolbarFrame(self, self.game)
            self._toolbar_frame.grid(row=0, column=1, rowspan=2, sticky=tkinter.N)

    def setup_options(self):
        return self._setup_game_toolbar_frame.options.copy()


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(module)s:%(funcName)s:%(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='log a game of catan')
    parser.add_argument('--board', help="""string with space-separated short-codes for terrain and numbers,
                                           e.g. 'w w h b s o w w b ... 2 None 9 3 4 6 ...'""")
    parser.add_argument('--terrain', help='random|preset|empty|debug, default random')
    parser.add_argument('--numbers', help='random|preset|empty|debug, default preset')
    parser.add_argument('--ports', help='random|preset|empty|debug, default preset')
    parser.add_argument('--pieces', help='random|preset|empty|debug, default preset')
    parser.add_argument('--players', help='random|preset|empty|debug, default preset')
    parser.add_argument('--pregame', help='on|off, default on')
    parser.add_argument('--use_stdout', help='write to stdout', action='store_true')

    args = parser.parse_args()
    options = {
        'board': args.board,
        'terrain': args.terrain,
        'numbers': args.numbers,
        'ports': args.ports,
        'pieces': args.pieces,
        'players': args.players,
        'pregame': args.pregame,
        'use_stdout': args.use_stdout
    }

    # logging.info('args=\n{}'.format(pprint.pformat(options)))
    app = CatanSpectator(options=options)
    app.mainloop()


if __name__ == "__main__":
    main()
