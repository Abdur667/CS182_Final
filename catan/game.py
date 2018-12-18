import copy
import logging
import random 

import hexgrid
import catanlog
import undoredo 

import catan.states
import catan.board
import catan.pieces


class Game(object):
    """
    class Game represents a single game of catan. It has players, a board, and a log.

    A Game has observers. Observers register themselves by adding themselves to
    the Game's observers set. When the Game changes, it will notify all its observers,
    who can then poll the game state and make changes accordingly.

    e.g. self.game.observers.add(self)

    A Game has state. When changing state, remember to pass the current game to the
    state's constructor. This allows the state to modify the game as appropriate in
    the current state.

    e.g. self.set_state(states.GameStateNotInGame(self))
    """
    def __init__(self, players=None, board=None, logging='on', pregame='on', use_stdout=False):
        """
        Create a Game with the given options.

        :param players: list(Player)
        :param board: Board
        :param logging: (on|off)
        :param pregame: (on|off)
        :param use_stdout: bool (log to stdout?)
        """
        # print('Init method for game hit')
        self.observers = set()
        self.undo_manager = undoredo.UndoManager()
        self.options = {
            'pregame': pregame,
        }
        self.players = players or list()
        self.board = board or catan.board.Board()
        self.robber = catan.pieces.Piece(catan.pieces.PieceType.robber, None)

        # catanlog: writing, reading
        if logging == 'on':
            self.catanlog = catanlog.CatanLog(use_stdout=use_stdout)
        else:
            self.catanlog = catanlog.NoopCatanLog()
        # self.catanlog_reader = catanlog.Reader()

        self.state = None # set in #set_state
        self.dev_card_state = None # set in #set_dev_card_state
        self._cur_player = None # set in #set_players
        self.last_roll = None # set in #roll
        self.last_player_to_roll = None # set in #roll
        self._cur_turn = 0 # incremented in #end_turn
        self.robber_tile = None # set in #move_robber
        self.terrain_to_tiles = {} # set in #_terrain_to_tiles
        # self.resources_owned = {player: [] for player in self.players}
        # self.pregame_coords = {player: [] for player in self.players}
        self.player_to_resources = {}

        self.board.observers.add(self)

        self.set_state(catan.states.GameStateNotInGame(self))
        self.set_dev_card_state(catan.states.DevCardNotPlayedState(self))
        # print('ENDING INIT METHOD FOR GAME')
        # print('players={0}, observers={1}, robber={2}\n*******\n'.format(
            # self.players, self.observers, self.robber))

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == 'observers':
                setattr(result, k, set(v))
            elif k == 'state':
                setattr(result, k, v)
            elif k == 'undo_manager':
                setattr(result, k, v)
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    def do(self, command: undoredo.Command):
        """
        Does the command using the undo_manager's stack
        :param command: Command
        """
        self.undo_manager.do(command)
        self.notify_observers()

    def undo(self):
        """
        Rewind the game to the previous state.
        """
        self.undo_manager.undo()
        self.notify_observers()
        # logging.debug('undo_manager undo stack={}'.format(self.undo_manager._undo_stack))

    def redo(self):
        """
        Redo the latest undone command.
        """
        self.undo_manager.redo()
        self.notify_observers()
        # logging.debug('undo_manager redo stack={}'.format(self.undo_manager._redo_stack))

    def copy(self):
        """
        Return a deep copy of this Game object. See Game.__deepcopy__ for the copy implementation.
        :return: Game
        """
        return copy.deepcopy(self)

    def restore(self, game):
        """
        Restore this Game object to match the properties and state of the given Game object
        :param game: properties to restore to the current (self) Game
        """
        self.observers = game.observers
        # self.undo_manager = game.undo_manager
        self.options = game.options
        self.players = game.players
        self.board.restore(game.board)
        self.robber = game.robber
        self.catanlog = game.catanlog

        self.state = game.state
        self.state.game = self

        self.dev_card_state = game.dev_card_state

        self._cur_player = game._cur_player
        self.last_roll = game.last_roll
        self.last_player_to_roll = game.last_player_to_roll
        self._cur_turn = game._cur_turn
        self.robber_tile = game.robber_tile

        self.notify_observers()

    # def read_from_file(self, file):
    #     self.catanlog_reader.use_file(file)

    def notify(self, observable):
        self.notify_observers()

    def notify_observers(self):
        # print('game\'s notify_observers called')
        for obs in self.observers.copy():
            # print('calling .notify() on obs={}'.format(obs))
            obs.notify(self)

    def set_state(self, game_state):
        # print('set_state called with game_state={}'.format(game_state))
        _old_state = self.state
        _old_board_state = self.board.state
        self.state = game_state
        if game_state.is_in_game():
            print('set_state calling board.lock')
            self.board.lock()
        else:
            # print('5')
            self.board.unlock()
        # logging.info('Game now={}, was={}. Board now={}, was={}'.format(
            # type(self.state).__name__,
            # type(_old_state).__name__,
            # type(self.board.state).__name__,
            # type(_old_board_state).__name__
        # ))
        # print('set_state calling notify_observers')
        self.notify_observers()

    def set_dev_card_state(self, dev_state):
        self.dev_card_state = dev_state
        self.notify_observers()

    @undoredo.undoable
    def start(self, players):
        """
        Start the game.

        The value of option 'pregame' determines whether the pregame will occur or not.

        - Resets the board
        - Sets the players
        - Sets the game state to the appropriate first turn of the game
        - Finds the robber on the board, sets the robber_tile appropriately
        - Logs the catanlog header

        :param players: players to start the game with
        """
        # print('game\'s start method called')
        from .boardbuilder import Opt
        # print('-calling reset()')
        self.reset()
        if self.board.opts.get('players') == Opt.debug:
            # print('-using debug players={}'.format(Game.get_debug_players()))
            players = Game.get_debug_players()
        # print('-calling set_players({})'.format(players))
        self.set_players(players)
        if self.options.get('pregame') is None or self.options.get('pregame') == 'on':
            # logging.debug('Entering pregame, game options={}'.format(self.options))
            # print('-call set_state(catan.states.GameStatePreGamePlacingPiece(self, catan.pieces.PieceType.settlement))')
            self.set_state(catan.states.GameStatePreGamePlacingPiece(self, catan.pieces.PieceType.settlement))
        elif self.options.get('pregame') == 'off':
            # logging.debug('Skipping pregame, game options={}'.format(self.options))
            self.set_state(catan.states.GameStateBeginTurn(self))

        terrain = list()
        numbers = list()
        for tile in self.board.tiles:
            terrain.append(tile.terrain)
            numbers.append(tile.number)
        # print('-populated terrain={0} and numbers={1} from tiles={2}'
            # .format(terrain, numbers, self.board.tiles))

        for (_, coord), piece in self.board.pieces.items():
            if piece.type == catan.pieces.PieceType.robber:
                self.robber_tile = hexgrid.tile_id_from_coord(coord)
                # logging.debug('Found robber at coord={}, set robber_tile={}'.format(coord, self.robber_tile))

        self.catanlog.log_game_start(self.players, terrain, numbers, self.board.ports)
        self.notify_observers()

    def end(self):
        print('Game\'s end method called')
        self.catanlog.log_wins(self.get_cur_player())
        print('final pieces = {}'.format(self.board.player_to_pieces))
        self.evaluate_final(self.board.player_to_pieces)
        self.set_state(catan.states.GameStateNotInGame(self))
        self.notify_observers()

    def evaluate_final(self, pieces):
        self.player_to_resources = {player: [] for player in pieces}

        terrain_to_tiles = {}
        vocab = {catan.board.Terrain.desert: 'Desert',
        catan.board.Terrain.wheat: 'Wheat',
        catan.board.Terrain.ore: 'Ore',
        catan.board.Terrain.sheep: 'Sheep',
        catan.board.Terrain.brick: 'Brick',
        catan.board.Terrain.wood: 'Wood'}

        for tile in self.board.tiles: 
            print('tile={}'.format(tile))
            if vocab[tile.terrain] in terrain_to_tiles:
                print('tile.terrain={}'.format(tile.terrain))
                print('vocab[tile.terrain]={}'.format(vocab[tile.terrain])) 
                terrain_to_tiles[vocab[tile.terrain]].append(tile.tile_id)
            else:
                terrain_to_tiles[vocab[tile.terrain]] = [tile.tile_id]  
        print('terrain_to_tiles={}'.format(terrain_to_tiles))

        tile_id_to_terrain_type = {tile: [] for tile in hexgrid.legal_tile_ids()}
        # for each terrain type
        for terrain in terrain_to_tiles:
            # for each tile
            for tile in hexgrid.legal_tile_ids():
                if tile in terrain_to_tiles[terrain]:
                    tile_id_to_terrain_type[tile].append(terrain)

        
        # for each player 
        for player in pieces:
            # for each resource owned by the player 
            for item in pieces[player]:
                # if resource is a city 
                if item[1] == catan.pieces.PieceType.settlement:
                    coord = item[0]
                    adjacent_tiles = hexgrid.adjacent_tiles_to_node(coord)
                    for adj_tile in adjacent_tiles:
                        self.player_to_resources[player].append(tile_id_to_terrain_type[adj_tile])

        print(self.player_to_resources)

    def reset(self):
        # print('Game\'s reset method called')
        self.players = list()
        # print('setting state to catan.states.GameStateNotInGame and notifying observers')
        self.state = catan.states.GameStateNotInGame(self)

        self.last_roll = None
        self.last_player_to_roll = None
        self._cur_player = None
        self._cur_turn = 0

        self.notify_observers()

    def get_cur_player(self):
        # print('Game\'s get_cur_player method called when cur_player={}'.format(self._cur_player))
        if self._cur_player is None:
            return Player(1, 'nobody', 'nobody')
        else:
            return Player(self._cur_player.seat, self._cur_player.name, self._cur_player.color)

    def set_cur_player(self, player):
        print('Game\'s set_cur_player method called with cur_player={}'.format(Player(player.seat, player.name, player.color)))
        self._cur_player = Player(player.seat, player.name, player.color)
        # print('self._cur_player={}'.format(Player(player.seat, player.name, player.color)))

    def set_players(self, players):
        # print('Game\'s set_players method called')
        self.players = list(players)
        # print('set_players calling set_cur_player({})'.format(self.players[0]))
        self.set_cur_player(self.players[0])
        self.notify_observers()

    def cur_player_has_port_type(self, port_type):
        # print('Game\'s cur_player_has_port_type method called')
        return self.player_has_port_type(self.get_cur_player(), port_type)

    def player_has_port_type(self, player, port_type):
        # print('Game\'s player_has_port_type method called')
        for port in self.board.ports:
            if port.type == port_type and self._player_has_port(player, port):
                return True
        return False

    def _player_has_port(self, player, port):
        # print('\nGame\'s _player_has_port method called\n')
        edge_coord = hexgrid.edge_coord_in_direction(port.tile_id, port.direction)
        for node in hexgrid.nodes_touching_edge(edge_coord):
            pieces = self.board.get_pieces((catan.pieces.PieceType.settlement, catan.pieces.PieceType.city), node)
            if len(pieces) < 1:
                continue
            elif len(pieces) > 1:
                raise Exception('Probably a bug, num={} pieces found on node={}'.format(
                    len(pieces), node
                ))
            assert len(pieces) == 1  # will be asserted by previous if/elif combo
            piece = pieces[0]
            if piece.owner == player:
                return True
        return False

    @undoredo.undoable
    def roll(self, roll):
        # print('\nGame\'s roll method called\n')
        self.catanlog.log_roll(self.get_cur_player(), roll)
        self.last_roll = roll
        self.last_player_to_roll = self.get_cur_player()
        if int(roll) == 7:
            self.set_state(catan.states.GameStateMoveRobber(self))
        else:
            self.set_state(catan.states.GameStateDuringTurnAfterRoll(self))

    @undoredo.undoable
    def move_robber(self, tile):
        # print('\nGame\'s move_robber method called\n')
        self.state.move_robber(tile)

    @undoredo.undoable
    def steal(self, victim):
        # print('\nGame\'s steal method called\n')
        if victim is None:
            victim = Player(1, 'nobody', 'nobody')
        self.state.steal(victim)

    def stealable_players(self):
        print('\nGame\'s stealable_players method called\n')
        if self.robber_tile is None:
            return list()
        stealable = set()
        for node in hexgrid.nodes_touching_tile(self.robber_tile):
            pieces = self.board.get_pieces(types=(catan.pieces.PieceType.settlement, catan.pieces.PieceType.city), coord=node)
            if pieces:
                # print('if pieces hit')
                # logging.debug('found stealable player={}, cur={}'.format(pieces[0].owner, self.get_cur_player()))
                stealable.add(pieces[0].owner)
        # print('stealable={}'.format(stealable))
        if self.get_cur_player() in stealable:
            # print('if cur_player is stealable, remove it from stealable')
            stealable.remove(self.get_cur_player())
        # logging.debug('stealable players={} at robber tile={}'.format(stealable, self.robber_tile))
        # print('stealable={}'.format(stealable))
        return stealable

    @undoredo.undoable
    def begin_placing(self, piece_type):
        # print('\nGame\'s begin_placing method called with piece_type={}\n'.format(piece_type))
        if self.state.is_in_pregame():
            self.set_state(catan.states.GameStatePreGamePlacingPiece(self, piece_type))
        else:
            self.set_state(catan.states.GameStatePlacingPiece(self, piece_type))

    # @undoredo.undoable # state.place_road calls this, place_road is undoable
    def buy_road(self, edge):
        # print('\nGame\'s buy_road method called with edge={}\n'.format(edge))
        #self.assert_legal_road(edge)
        piece = catan.pieces.Piece(catan.pieces.PieceType.road, self.get_cur_player())
        self.board.place_piece(piece, edge)
        self.catanlog.log_buys_road(self.get_cur_player(), hexgrid.location(hexgrid.EDGE, edge))
        if self.state.is_in_pregame():
            self.end_turn()
        else:
            self.set_state(catan.states.GameStateDuringTurnAfterRoll(self))

    # @undoredo.undoable # state.place_settlement calls this, place_settlement is undoable
    def buy_settlement(self, node):
        print('\nGame\'s buy_settlement method called with node={}\n'.format(node))
        #self.assert_legal_settlement(node)
        piece = catan.pieces.Piece(catan.pieces.PieceType.settlement, self.get_cur_player())
        # print('piece = {0} = catan.pieces.Piece({1}, {2})'.format(piece, catan.pieces.PieceType.settlement, self.get_cur_player()))
        # print('calling self.board.place_piece(piece={0}, node={1}'.format(piece, node))

        self.board.place_piece(piece, node)
        self.catanlog.log_buys_settlement(self.get_cur_player(), hexgrid.location(hexgrid.NODE, node))


        if self.state.is_in_pregame():
            self.set_state(catan.states.GameStatePreGamePlacingPiece(self, catan.pieces.PieceType.road))
        else:
            self.set_state(catan.states.GameStateDuringTurnAfterRoll(self))

    # @undoredo.undoable # state.place_city calls this, place_city is undoable
    def buy_city(self, node):
        # print('\nGame\'s buy_city method called with node={}\n'.format(node))
        #self.assert_legal_city(node)
        piece = catan.pieces.Piece(catan.pieces.PieceType.city, self.get_cur_player())
        self.board.place_piece(piece, node)

        # self.resources_owned[self._cur_player].append() 
        # self.pregame_coords[self._cur_player].append()

        self.catanlog.log_buys_city(self.get_cur_player(), hexgrid.location(hexgrid.NODE, node))
        self.set_state(catan.states.GameStateDuringTurnAfterRoll(self))

    @undoredo.undoable
    def buy_dev_card(self):
        # print('\nGame\'s buy_dev_card method called\n')
        self.catanlog.log_buys_dev_card(self.get_cur_player())
        self.notify_observers()

    @undoredo.undoable
    def place_road(self, edge_coord):
        # print('\nGame\'s place_road method called with edge_coord={}\n'.format(edge_coord))
        self.state.place_road(edge_coord)

    @undoredo.undoable
    def place_settlement(self, node_coord):
        # print('\nGame\'s place_settlement method called with node_coord={}\n'.format(node_coord))
        self.state.place_settlement(node_coord)

    @undoredo.undoable
    def place_city(self, node_coord):
        # print('\nGame\'s place_city method called with node={}\n'.format(node_coord))
        self.state.place_city(node_coord)

    @undoredo.undoable
    def trade(self, trade):
        # print('\nGame\'s trade method called with trade-={}\n'.format(trade))
        giver = trade.giver()
        giving = trade.giving()
        getting = trade.getting()
        if hasattr(trade.getter(), 'type') and trade.getter().type in catan.board.PortType:
            getter = trade.getter()
            self.catanlog.log_trades_with_port(giver, giving, getter, getting)
            # logging.debug('trading {} to port={} to get={}'.format(giving, getter, getting))
        else:
            getter = trade.getter()
            self.catanlog.log_trades_with_player(giver, giving, getter, getting)
            # logging.debug('trading {} to player={} to get={}'.format(giving, getter, getting))
        self.notify_observers()

    @undoredo.undoable
    def play_knight(self):
        # print('\nGame\'s play_knight method called\n')
        self.set_dev_card_state(catan.states.DevCardPlayedState(self))
        self.set_state(catan.states.GameStateMoveRobberUsingKnight(self))

    @undoredo.undoable
    def play_monopoly(self, resource):
        # print('\nGame\'s play_monopoly method called with resource={}\n'.format(resource))
        self.catanlog.log_plays_monopoly(self.get_cur_player(), resource)
        self.set_dev_card_state(catan.states.DevCardPlayedState(self))

    @undoredo.undoable
    def play_year_of_plenty(self, resource1, resource2):
        # print('\nGame\'s play_year_of_plenty method called\n')
        self.catanlog.log_plays_year_of_plenty(self.get_cur_player(), resource1, resource2)
        self.set_dev_card_state(catan.states.DevCardPlayedState(self))

    @undoredo.undoable
    def play_road_builder(self, edge1, edge2):
        # print('\nGame\'s play_road_builder method called\n')
        self.catanlog.log_plays_road_builder(self.get_cur_player(),
                                                    hexgrid.location(hexgrid.EDGE, edge1),
                                                    hexgrid.location(hexgrid.EDGE, edge2))
        self.set_dev_card_state(catan.states.DevCardPlayedState(self))

    @undoredo.undoable
    def play_victory_point(self):
        # print('\nGame\'s play_victory_point method called\n')
        self.catanlog.log_plays_victory_point(self.get_cur_player())
        self.set_dev_card_state(catan.states.DevCardPlayedState(self))

    @undoredo.undoable
    def end_turn(self):
        print('*******************************************************************************************************\
*******************************************************************************************************\
                        !!!!!!!!!!!!!!!!!!!!FINISHED TURN!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!                \
*******************************************************************************************************\
*******************************************************************************************************')      
        print('\nGame\'s end_turn method called when cur_player={0}, next_player={1}\n'.format(self._cur_player, self.state.next_player))
        self.catanlog.log_ends_turn(self.get_cur_player())
        # print('self.state.next_player()={}'.format(self.state.next_player()))

        self.set_cur_player(self.state.next_player())
        logging.debug('self.state is {}'.format(self.state))
        if self.state.can_end_game():
            print('self.state.can_end_game={}'.format(self.state.can_end_game))
            logging.debug('*****************************************')
            self.end()

        self._cur_turn += 1
        logging.debug('cur_turn incremented to {}'.format(self._cur_turn))

        self.set_dev_card_state(catan.states.DevCardNotPlayedState(self))
        if self.state.is_in_pregame():
            print('self.state.is_in_pregame() == TRUE')
            self.set_state(catan.states.GameStatePreGamePlacingPiece(self, catan.pieces.PieceType.settlement))
        else:
            print('self.state.is_in_pregame() == False and setting state to GSBT')
            self.end()
            # self.set_state(catan.states.GameStateBeginTurn(self))

        if 'agent1' in self._cur_player.name:
            if self.state.is_in_pregame():
                node, edge = self.get_random_assignment(self.board.pieces)
                self.place_settlement(node)
                self.place_road(edge)
        elif 'agent2' in self._cur_player.name:
            if self.state.is_in_pregame():
                node, edge = self.get_best_assignment(self.board.pieces)
                self.place_settlement(node)
                self.place_road(edge)

    # def node_to_resources(self, node):



    def get_random_assignment(self, d):
        assigned_nodes = {piece[1] for piece in d if piece[0] == 1}
        free_nodes = hexgrid.legal_node_coords() - assigned_nodes

        assigned_edges = {piece[1] for piece in d if piece[0] == 0}
        free_edges = hexgrid.legal_edge_coords() - assigned_edges

        return (random.sample(free_nodes, 1)[0], random.sample(free_edges, 1)[0])

    def get_best_assignment(self, d):
        assigned_nodes = {piece[1] for piece in d if piece[0] == 1}
        free_nodes = hexgrid.legal_node_coords() - assigned_nodes
        node_choice = random.sample(free_nodes, 1)[0]

        assigned_edges = {piece[1] for piece in d if piece[0] == 0}
        free_edges = hexgrid.legal_edge_coords() - assigned_edges
        edge_choice = random.sample(free_edges, 1)[0]

        # not building on the same hex 
        if self._cur_player in self.board.player_to_pieces:
            flag = True
            while flag:
                choice_adjacent = hexgrid.adjacent_tiles_to_node(node_choice)

                past_choice = self.board.player_to_pieces[self._cur_player][0]
                past_adjacent = hexgrid.adjacent_tiles_to_node(past_choice[0])

                if set(choice_adjacent).isdisjoint(set(past_adjacent)):
                    flag = False
                else:
                    node_choice = random.sample(free_nodes, 1)[0] 

        return (node_choice, edge_choice)

    @classmethod
    def get_debug_players(cls):
        # print('\nGame\'s get_debug_players method called\n')
        return [Player(1, 'abdur', 'green'),
                Player(2, 'Qlearn', 'blue'),
                Player(3, 'vitor', 'orange'),
                Player(4, 'brian', 'red')]


class Player(object):
    """class Player represents a single player on the game board.

    :param seat: integer, with 1 being top left, and increasing clockwise
    :param name: will be lowercased, spaces will be removed
    :param color: will be lowercased, spaces will be removed
    """
    def __init__(self, seat, name, color):
        # print('\nHitting Player init method\n')
        if not (1 <= seat <= 4):
            raise Exception("Seat must be on [1,4]")
        self.seat = seat

        self.name = name.lower().replace(' ', '')
        self.color = color.lower().replace(' ', '')

    def __eq__(self, other):
        if other is None:
            return False
        if other.__class__ != Player:
            return False
        return (self.color == other.color
                and self.name == other.name
                and self.seat == other.seat)

    def __repr__(self):
        return '{} ({})'.format(self.color, self.name)

    def __hash__(self):
        return sum(bytes(str(self), encoding='utf8'))

