import logging
import tkinter
from tkinter import messagebox
import math
import collections
import functools
import catanlog
import hexgrid
from catan import states
from catan.board import PortType, HexNumber, Terrain
from catan.game import Player
from catan.pieces import PieceType, Piece
import tkinterutils
import views_trading

can_do = {
    True: tkinter.NORMAL,
    False: tkinter.DISABLED,
    None: tkinter.DISABLED
}

LOG_WIDTH = 85
LOG_MAX_HEIGHT = 13
LOG_MIN_HEIGHT = 1
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 550


class LogFrame(tkinter.Frame):

    def __init__(self, master, game, *args, **kwargs):
        super(LogFrame, self).__init__()
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.log = tkinter.Text(self, width=85, height=LOG_MIN_HEIGHT, state=tkinter.NORMAL)
        self.log.insert(tkinter.END, '{} {}'.format(catanlog.__name__, catanlog.__version__))
        self.log.see(tkinter.END)
        self.log.pack(expand=tkinter.YES, fill=tkinter.BOTH)

    def notify(self, observable):
        # logging.debug('LogFrame.notify called and calling LogFrame.redraw()')
        self.redraw()

    def redraw(self):
        self.log.delete(1.0, tkinter.END)
        logs = self.game.catanlog.dump()
        self.log.configure(height=max(LOG_MIN_HEIGHT,min(LOG_MAX_HEIGHT,len(logs))))
        self.log.insert(tkinter.END, logs)

        # logging.debug('Redrew latest={} lines of game log'.format(len(logs.split('\n'))))
        self.log.see(tkinter.END) # scroll to end


class BoardFrame(tkinter.Frame):
    def __init__(self, master, game, *args, **kwargs):
        super(BoardFrame, self).__init__()
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self._board = game.board

        board_canvas = tkinter.Canvas(self, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, background='Royal Blue')
        board_canvas.pack(expand=tkinter.YES, fill=tkinter.BOTH)

        self._board_canvas = board_canvas
        self._center_to_edge = math.cos(math.radians(30)) * self._tile_radius

    def tile_click(self, event):
        if not self._board.state.modifiable():
            return

        tag = self._board_canvas.gettags(event.widget.find_closest(event.x, event.y))[0]
        if self.master.setup_options()['hex_resource_selection']:
            self._board.cycle_hex_type(self._tile_id_from_tag(tag))
        if self.master.setup_options()['hex_number_selection']:
            self._board.cycle_hex_number(self._tile_id_from_tag(tag))
        self.redraw()

    def piece_click(self, piece_type, event):
        tags = self._board_canvas.gettags(event.widget.find_closest(event.x, event.y))
        # avoid processing tile clicks
        tag = None
        for t in tags:
            if 'tile' not in t:
                tag = t
                break

        # logging.debug('Piece clicked with tag={}'.format(tag))
        if piece_type == PieceType.road:
            self.game.place_road(self._coord_from_road_tag(tag))
        elif piece_type == PieceType.settlement:
            self.game.place_settlement(self._coord_from_settlement_tag(tag))
        elif piece_type == PieceType.city:
            self.game.place_city(self._coord_from_city_tag(tag))
        elif piece_type == PieceType.robber:
            self.game.move_robber(hexgrid.tile_id_from_coord(self._coord_from_robber_tag(tag)))
        # logging.debug('boardFrame.piece_click calling boardFrame.redraw')
        self.redraw()

    def port_click(self, port, event):
        if not self._board.state.modifiable():
            return

        # logging.debug('port={} clicked'.format(port))
        tags = self._board_canvas.gettags(event.widget.find_closest(event.x, event.y))
        tag = tags[0]
        if 'port' not in tag:
            logging.warning('Port click handler running on non-port tag={}, returning early.'.format(tag))
            return
        tile_id, direction = self._tile_and_direction_from_port_tag(tag)
        self._board.cycle_port_type(tile_id, direction)
        # todo add onclick events for invisible ports yet to be clicked on and made into ports

    def notify(self, observable):
        # logging.debug('BoardFrame.notify called and calling BoardFrame.redraw()')
        self.redraw()

    def draw(self, board):
        """Render the board to the canvas widget.

        Taking the center of the first tile as 0, 0 we follow the path of tiles
        around the graph as given by the board (must be guaranteed to be a
        connected path that visits every tile) and calculate the center of each
        tile as the offset from the last one, based on it's direction from the
        last tile and the radius of the hexagons (and padding etc.)

        We then shift all the individual tile centers so that the board center
        is at 0, 0.
        """
        terrain_centers = self._draw_terrain(board)
        self._draw_numbers(board, terrain_centers)
        self._draw_pieces(board, terrain_centers)
        if self.game.state.can_place_road():
            self._draw_piece_shadows(PieceType.road, board, terrain_centers)
        if self.game.state.can_place_settlement():
            self._draw_piece_shadows(PieceType.settlement, board, terrain_centers)
        if self.game.state.can_place_city():
            self._draw_piece_shadows(PieceType.city, board, terrain_centers)
        if self.game.state.can_move_robber():
            self._draw_piece_shadows(PieceType.robber, board, terrain_centers)

        if self.game.state.is_in_game():
            self._draw_ports(board, terrain_centers)
        else:
            self._draw_port_shadows(board, terrain_centers)

    def redraw(self):
        self._board_canvas.delete(tkinter.ALL)
        self.draw(self._board)

    def _draw_terrain(self, board):
        # logging.debug('Drawing terrain (resource tiles)')
        centers = {}
        last = None
        for tile in board.tiles:
            if not last:
                centers[tile.tile_id] = (0, 0)
                last = tile
                continue

            # Calculate the center of this tile as an offset from the center of
            # the neighboring tile in the given direction.
            ref_center = centers[last.tile_id]
            direction = hexgrid.direction_to_tile(last.tile_id, tile.tile_id)
            theta = self._tile_angle_order.index(direction) * 60
            radius = 2 * self._center_to_edge + self._tile_padding
            dx = radius * math.cos(math.radians(theta))
            dy = radius * math.sin(math.radians(theta))
            centers[tile.tile_id] = (ref_center[0] + dx, ref_center[1] + dy)
            last = tile

        centers = self._fixup_terrain_centers(centers)
        for tile_id, (x, y) in centers.items():
            tile = board.tiles[tile_id - 1]
            self._draw_tile(x, y, tile.terrain, tile)
            self._board_canvas.tag_bind(self._tile_tag(tile), '<ButtonPress-1>', func=self.tile_click)

        return dict(centers)

    def _draw_tile(self, x, y, terrain, tile):
        self._draw_hexagon(self._tile_radius, offset=(x, y), fill=self._colors[terrain], tags=self._tile_tag(tile))

    def _draw_hexagon(self, radius, offset=(0, 0), rotate=30, fill='black', tags=None):
        points = self._hex_points(radius, offset, rotate)
        self._board_canvas.create_polygon(*points, fill=fill, tags=tags)

    def _draw_numbers(self, board, terrain_centers):
        # logging.debug('Drawing numbers')
        for tile_id, (x, y) in terrain_centers.items():
            tile = board.tiles[tile_id - 1]
            self._draw_number(x, y, tile.number, tile)

    def _draw_ports(self, board, terrain_centers, ports=None, ghost=False):
        if ports is None:
            ports = board.ports
        # logging.debug('Drawing ports')
        # logging.debug('ports={}'.format(ports))
        port_centers = []
        for port in ports:
            tile_x, tile_y = terrain_centers[port.tile_id]
            theta = self._tile_angle_order.index(port.direction) * 60
            radius = 2 * self._center_to_edge + self._tile_padding
            dx = radius * math.cos(math.radians(theta))
            dy = radius * math.sin(math.radians(theta))
            # logging.debug('tile_id={}, port={}, x+dx={}+{}, y+dy={}+{}'.format(tile_id, port, tile_x, dx, tile_y, dy))
            port_centers.append((tile_x + dx, tile_y + dy, theta))

        port_centers = self._fixup_port_centers(port_centers)
        for (x, y, angle), port in zip(port_centers, ports):
            # logging.debug('Drawing port={} at ({},{})'.format(port, x, y))
            self._draw_port(x, y, angle, port, ghost=ghost)

    def _draw_port_shadows(self, board, terrain_centers):
        coastal_coords = hexgrid.coastal_coords()
        ports = list(map(lambda cc: board.get_port_at(*cc), coastal_coords))
        self._draw_ports(board, terrain_centers, ports=ports, ghost=True)


    def _draw_port(self, x, y, angle, port, ghost=False):
        """
        Draw the given port.

        Currently, draws a equilateral triangle with the top point at x, y and the
        bottom facing the direction given by the angle.

        :param x: int
        :param y: int
        :param angle: ccw from E, in degrees
        :param port: Port
        """
        opts = self._port_tkinter_opts(port, ghost=ghost)
        points = [x, y]
        for adjust in (-30, 30):
            x1 = x + math.cos(math.radians(angle + adjust)) * self._tile_radius
            y1 = y + math.sin(math.radians(angle + adjust)) * self._tile_radius
            points.extend([x1, y1])
        self._board_canvas.create_polygon(*points,
                                          **opts)
        if port.type != PortType.none:
            self._board_canvas.create_text(x, y, text=port.type.value, font=self._hex_font)
        self._board_canvas.tag_bind(self._port_tag(port), '<ButtonPress-1>',
                                    functools.partial(self.port_click, port))

    def _draw_pieces(self, board, terrain_centers):
        roads, settlements, cities, robber = self._get_pieces(board)

        for coord, road in roads:
            self._draw_piece(coord, road, terrain_centers)
        # logging.debug('Roads drawn: {}'.format(len(roads)))

        for coord, settlement in settlements:
            self._draw_piece(coord, settlement, terrain_centers)

        for coord, city in cities:
            self._draw_piece(coord, city, terrain_centers)

        coord, robber = robber
        self._draw_piece(coord, robber, terrain_centers)

    def _draw_piece_shadows(self, piece_type, board, terrain_centers):
        # logging.debug('Drawing piece shadows of type={}'.format(piece_type.value))
        piece = Piece(piece_type, self.game.get_cur_player())
        if piece_type == PieceType.road:
            edges = hexgrid.legal_edge_coords()
            count = 0
            for edge in edges:
                if (hexgrid.EDGE, edge) in board.pieces:
                    # logging.debug('Not drawing shadow road at coord={}'.format(edge))
                    continue
                count += 1
                self._draw_piece(edge, piece, terrain_centers, ghost=True)
            # logging.debug('Road shadows drawn: {}'.format(count))
        elif piece_type == PieceType.settlement:
            nodes = hexgrid.legal_node_coords()
            for node in nodes:
                if (hexgrid.NODE, node) in board.pieces:
                    continue
                self._draw_piece(node, piece, terrain_centers, ghost=True)
        elif piece_type == PieceType.city:
            for (_, node), p in board.pieces.items():
                if p.type == PieceType.settlement and p.owner.color == piece.owner.color:
                    self._draw_piece(node, piece, terrain_centers, ghost=True)
        elif piece_type == PieceType.robber:
            for coord in hexgrid.legal_tile_coords():
                if hexgrid.tile_id_from_coord(coord) != self.game.robber_tile:
                    self._draw_piece(coord, piece, terrain_centers, ghost=True)
        else:
            logging.warning('Attempted to draw piece shadows for nonexistent type={}'.format(piece_type))

    def _draw_piece(self, coord, piece, terrain_centers, ghost=False):
        x, y, angle = self._get_piece_center(coord, piece, terrain_centers)
        tag = None
        if piece.type == PieceType.road:
            self._draw_road(x, y, coord, piece, angle=angle, ghost=ghost)
            tag = self._road_tag(coord)
        elif piece.type == PieceType.settlement:
            self._draw_settlement(x, y, coord, piece, ghost=ghost)
            tag = self._settlement_tag(coord)
        elif piece.type == PieceType.city:
            self._draw_city(x, y, coord, piece, ghost=ghost)
            tag = self._city_tag(coord)
        elif piece.type == PieceType.robber:
            self._draw_robber(x, y, coord, piece, ghost=ghost)
            tag = self._robber_tag(coord)
        else:
            logging.warning('Attempted to draw piece of unknown type={}'.format(piece.type))

        if ghost:
            self._board_canvas.tag_bind(tag, '<ButtonPress-1>',
                                        func=functools.partial(self.piece_click, piece.type))
        else:
            self._board_canvas.tag_unbind(tag, '<ButtonPress-1>')

    def _piece_tkinter_opts(self, coord, piece, **kwargs):
        opts = dict()
        tag_funcs = {
            PieceType.road: self._road_tag,
            PieceType.settlement: self._settlement_tag,
            PieceType.city: self._city_tag,
            PieceType.robber: self._robber_tag,
        }
        if piece.type == PieceType.robber:
            # robber has no owner
            color = 'black'
        else:
            color = piece.owner.color

        opts['tags'] = tag_funcs[piece.type](coord)
        opts['outline'] = color
        opts['fill'] = color
        if 'ghost' in kwargs and kwargs['ghost'] == True:
            opts['fill'] = '' # transparent
            opts['activefill'] = color
        del kwargs['ghost']
        opts.update(kwargs)
        return opts

    def _port_tkinter_opts(self, port, **kwargs):
        opts = dict()
        color = self._colors[port.type]
        next_color = self._colors[PortType.next_ui(port.type)]

        ghost = 'ghost' in kwargs and kwargs['ghost'] == True

        opts['tags'] = self._port_tag(port)
        opts['outline'] = color
        opts['fill'] = color
        if ghost:
            opts['activefill'] = next_color

        del kwargs['ghost']
        opts.update(kwargs)
        return opts

    def _draw_road(self, x, y, coord, piece, angle, ghost=False):
        opts = self._piece_tkinter_opts(coord, piece, ghost=ghost)
        length = self._tile_radius * 0.7
        height = self._tile_padding * 2.5
        points = [x - length/2, y - height/2] # left top
        points += [x + length/2, y - height/2] # right top
        points += [x + length/2, y + height/2] # right bottom
        points += [x - length/2, y + height/2] # left bottom
        points = tkinterutils.rotate_2poly(angle, points, (x, y))
        # logging.debug('Drawing road={} at coord={}, angle={} with opts={}'.format(
        #     piece, coord, angle, opts
        # ))
        self._board_canvas.create_polygon(*points,
                                          **opts)

    def _draw_settlement(self, x, y, coord, piece, ghost=False):
        opts = self._piece_tkinter_opts(coord, piece, ghost=ghost)
        width = 18
        height = 14
        point_height = 8
        points = [x - width/2, y - height/2] # left top
        points += [x, y - height/2 - point_height] # middle point
        points += [x + width/2, y - height/2] # right top
        points += [x + width/2, y + height/2] # right bottom
        points += [x - width/2, y + height/2] # left bottom
        self._board_canvas.create_polygon(*points,
                                          **opts)

    def _draw_city(self, x, y, coord, piece, ghost=False):
        opts = self._piece_tkinter_opts(coord, piece, ghost=ghost)
        self._board_canvas.create_rectangle(x-20, y-20, x+20, y+20,
                                            **opts)

    def _draw_robber(self, x, y, coord, piece, ghost=False):
        opts = self._piece_tkinter_opts(coord, piece, ghost=ghost)
        radius = 10
        self._board_canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                       **opts)

    def _get_pieces(self, board):
        """Returns roads, settlements, and cities on the board as lists of (coord, piece) tuples.

        Also returns the robber as a single (coord, piece) tuple.
        """
        roads = list()
        settlements = list()
        cities = list()
        robber = None
        for (_, coord), piece in board.pieces.items():
            if piece.type == PieceType.road:
                roads.append((coord, piece))
            elif piece.type == PieceType.settlement:
                settlements.append((coord, piece))
            elif piece.type == PieceType.city:
                cities.append((coord, piece))
            elif piece.type == PieceType.robber:
                if robber is not None:
                    logging.critical('More than one robber found on board, there can only be one robber')
                robber = (coord, piece)
        if robber is None:
            logging.critical('No robber found on the board, this is probably wrong')
        return roads, settlements, cities, robber

    def _get_piece_center(self, piece_coord, piece, terrain_centers):
        """Takes a piece's hex coordinate, the piece itself, and the terrain_centers
        dictionary which maps tile_id->(x,y)

        Returns the piece's center, as an (x,y) pair. Also returns the angle the
        piece should be rotated at, if any
        """
        if piece.type == PieceType.road:
            # these pieces are on edges
            tile_id = hexgrid.nearest_tile_to_edge(piece_coord)
            tile_coord = hexgrid.tile_id_to_coord(tile_id)
            direction = hexgrid.tile_edge_offset_to_direction(piece_coord - tile_coord)
            terrain_x, terrain_y = terrain_centers[tile_id]
            angle = 60*self._edge_angle_order.index(direction)
            dx = math.cos(math.radians(angle)) * self.distance_tile_to_edge()
            dy = math.sin(math.radians(angle)) * self.distance_tile_to_edge()
            return terrain_x + dx, terrain_y + dy, angle + 90
        elif piece.type in [PieceType.settlement, PieceType.city]:
            # these pieces are on nodes
            tile_id = hexgrid.nearest_tile_to_node(piece_coord)
            tile_coord = hexgrid.tile_id_to_coord(tile_id)
            direction = hexgrid.tile_node_offset_to_direction(piece_coord - tile_coord)
            terrain_x, terrain_y = terrain_centers[tile_id]
            angle = 30 + 60*self._node_angle_order.index(direction)
            dx = math.cos(math.radians(angle)) * self._tile_radius
            dy = math.sin(math.radians(angle)) * self._tile_radius
            return terrain_x + dx, terrain_y + dy, 0
        elif piece.type == PieceType.robber:
            # these pieces are on tiles
            tile_id = hexgrid.tile_id_from_coord(piece_coord)
            terrain_x, terrain_y = terrain_centers[tile_id]
            return terrain_x, terrain_y, 0
        else:
            logging.warning('Unknown piece={}'.format(piece))

    def _fixup_offset(self):
        offx, offy = self._board_center
        radius = 4 * self._center_to_edge + 2 * self._tile_padding
        offx += radius * math.cos(math.radians(240))
        offy += radius * math.sin(math.radians(240))
        return (offx, offy)

    def _fixup_terrain_centers(self, centers):
        offx, offy = self._fixup_offset()
        return dict((tile_id, (x + offx, y + offy)) for tile_id, (x, y) in centers.items())

    def _fixup_port_centers(self, port_centers):
        return [(x, y, angle + 180) for x, y, angle in port_centers]

    def _draw_number(self, x, y, number, tile):
        if number is HexNumber.none:
            return
        # logging.debug('Drawing number={}, HexNumber={}'.format(number.value, number))
        color = 'red' if number.value in (6, 8) else 'black'
        self._board_canvas.create_oval(tkinterutils.circle_bbox(15, (x, y)), fill='white', tags=self._tile_tag(tile))
        self._board_canvas.create_text(x, y, text=str(number.value), font=self._hex_font, fill=color, tags=self._tile_tag(tile))

    def _hex_points(self, radius, offset, rotate):
        offx, offy = offset
        points = []
        for theta in (60 * n for n in range(6)):
            x = (math.cos(math.radians(theta + rotate)) * radius) + offx
            y = (math.sin(math.radians(theta + rotate)) * radius) + offy
            points += [x, y]
        return points

    def distance_tile_to_edge(self):
        return self._tile_radius * math.cos(math.radians(30)) + 1/2*self._tile_padding

    def _tile_tag(self, tile):
        return 'tile_' + str(tile.tile_id)

    def _road_tag(self, coord):
        return 'road_' + hex(coord)

    def _settlement_tag(self, coord):
        return 'settlement_' + hex(coord)

    def _city_tag(self, coord):
        return 'city_' + hex(coord)

    def _robber_tag(self, coord):
        return 'robber_' + hex(coord)

    def _port_tag(self, port):
        return 'port_{:02}_{}'.format(port.tile_id, port.direction)

    def _tile_id_from_tag(self, tag):
        return int(tag[len('tile_'):])

    def _coord_from_road_tag(self, tag):
        return int(tag[len('road_0x'):], 16)

    def _coord_from_settlement_tag(self, tag):
        return int(tag[len('settlement_0x'):], 16)

    def _coord_from_city_tag(self, tag):
        return int(tag[len('city_0x'):], 16)

    def _coord_from_robber_tag(self, tag):
        return int(tag[len('robber_0x'):], 16)

    def _tile_and_direction_from_port_tag(self, tag):
        tile_id = int(tag[len('port_'):len('port_')+2])
        direction = tag[len('port_##_'):]
        return tile_id, direction

    _tile_radius  = 50
    _tile_padding = 3
    _board_center = (300, 300)
    _tile_angle_order = ('E', 'SE', 'SW', 'W', 'NW', 'NE') # 0 + 60*index
    _edge_angle_order = ('E', 'SE', 'SW', 'W', 'NW', 'NE') # 0 + 60*index
    _node_angle_order = ('SE', 'S', 'SW', 'NW', 'N', 'NE') # 30 + 60*index
    _hex_font     = (('Helvetica'), 18)
    _colors = {
        Terrain.wood: '#12782D',
        Terrain.brick: '#D14728',
        Terrain.wheat: '#FFFF63',
        Terrain.sheep: '#AEFA66',
        Terrain.ore: '#8A8A8A',
        Terrain.desert: 'white',
        PortType.wood: '#12782D',
        PortType.brick: '#D14728',
        PortType.wheat: '#FFFF63',
        PortType.sheep: '#AEFA66',
        PortType.ore: '#8A8A8A',
        PortType.any3: 'white',
        PortType.none: '', # transparent
    }


class SetupGameToolbarFrame(tkinter.Frame):

    def __init__(self, master, game, options=None, *args, **kwargs):
        super(SetupGameToolbarFrame, self).__init__()
        self.master = master
        self.game = game

        self.options = options or dict()
        self.options.update({
            'hex_resource_selection': True,
            'hex_number_selection': False
        })

        tkinter.Label(self, text="Players", anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)

        self.start_game_player_order = StartGamePlayerOrderFrame(self, game)
        self.start_game_player_order.pack()

        tkinter.Label(self, text="Board", anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)
        for option in TkinterOptionWrapper(self.options):
            option.callback()
            tkinter.Checkbutton(self, text=option.text, justify=tkinter.LEFT, command=option.callback, var=option.var) \
                .pack(side=tkinter.TOP, fill=tkinter.X)
        tkinter.Button(self, text="Reset Board", command=self.on_reset_board, anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)
        tkinter.Button(self, text="Reset Pieces", command=self.on_reset_pieces, anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)
        tkinter.Button(self, text="Move Robber", command=self.on_move_robber, anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)
        tkinter.Button(self, text="Rotate Ports", command=self.on_rotate_ports, anchor=tkinter.W).pack(side=tkinter.TOP, fill=tkinter.X)

        tkinter.Label(self, text="---").pack(side=tkinter.TOP)
        btn_start_game = tkinter.Button(self, text='Start Game', command=self.on_start_game)
        btn_start_game.pack(side=tkinter.TOP, fill=tkinter.X)

    def on_reset_board(self):
        self.game.board.reset()
        self.game.notify_observers()

    def on_reset_pieces(self):
        for (hextype, coord), piece in self.game.board.pieces.copy().items():
            if piece.type != PieceType.robber:
                self.game.board.remove_piece(piece, coord)
        self.game.notify_observers()

    def on_move_robber(self):
        self.game.set_state(states.GameStateNotInGameMoveRobber(self.game))

    def on_rotate_ports(self):
        self.game.board.rotate_ports()

    def on_start_game(self):
        print('*******************************************************************************************************\
*******************************************************************************************************\
                        !!!!!!!!!!!!!!!!!!!!CLICKED START!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!                \
*******************************************************************************************************\
*******************************************************************************************************')        
        def get_name(var):
            return var.get().split(' ')[0]

        def get_color(var):
            return var.get().split(' ')[1]

        players = list()
        for (spinner, var), (entry, evar) in zip(self.start_game_player_order.player_order_vars,
                                                 self.start_game_player_order.player_entries_vars):
            p = Player(int(var.get()),get_name(evar), get_color(evar ))
            players.append(p)

        players.sort(key=lambda p: p.seat)
        # logging.debug('views.on_start_game calling game.start with players={}'.format(players))

        self.game.start(players)


class StartGamePlayerOrderFrame(tkinter.Frame):

    def __init__(self, master, game, *args, **kwargs):
        super(StartGamePlayerOrderFrame, self).__init__(master)
        self.master = master
        self.game = game

        defaults = ('abdur green', 'agent1 blue', 'vitor orange', 'agent2 red')
        self.player_entries_vars = [(tkinter.Entry(self), tkinter.StringVar()) for i in range(len(defaults))]
        for (entry, var), default in zip(self.player_entries_vars, defaults):
            var.set(default)
            entry.config(textvariable=var)
            entry.grid(row=defaults.index(default), column=1)

        values = ['1','2','3','4']
        self.player_order_vars = [(tkinter.Spinbox(self, values=values), tkinter.StringVar()) for i in range(len(values))]
        for (entry, var),val in zip(self.player_order_vars, values):
            var.set(val)
            entry.config(textvariable=var)
            entry.grid(row=int(val)-1, column=2)


class GameToolbarFrame(tkinter.Frame):

    def __init__(self, master, game, *args, **kwargs):
        super(GameToolbarFrame, self).__init__()
        self.master = master
        self.game = game

        self.game.observers.add(self)

        self._cur_player = self.game.get_cur_player()
        self._cur_player_name = tkinter.StringVar()
        self.set_cur_player_name()

        label_cur_player_name = tkinter.Label(self, textvariable=self._cur_player_name, anchor=tkinter.W)
        frame_roll = RollFrame(self, self.game)
        frame_undo = UndoRedoFrame(self, self.game)
        frame_robber = RobberFrame(self, self.game)
        frame_build = BuildFrame(self, self.game)
        frame_trade = views_trading.TradeFrame(self, self.game)
        frame_play_dev = PlayDevCardFrame(self, self.game)
        frame_end_turn = EndTurnFrame(self, self.game)
        frame_end_game = EndGameFrame(self, self.game)

        label_cur_player_name.pack(fill=tkinter.X)
        frame_roll.pack(fill=tkinter.X)
        frame_undo.pack(fill=tkinter.X)
        frame_robber.pack(fill=tkinter.X)
        frame_build.pack(fill=tkinter.X)
        frame_trade.pack(fill=tkinter.X)
        frame_play_dev.pack(fill=tkinter.X)
        frame_end_turn.pack(fill=tkinter.X)
        frame_end_game.pack(side=tkinter.BOTTOM, fill=tkinter.BOTH)

    def set_game(self, game):
        self.game = game

    def notify(self, observable):
        # logging.debug('GameToolbarFrame.notify called and calling game.get_cur_player')
        if self._cur_player.color != self.game.get_cur_player().color:
            self.set_cur_player_name()

    def set_cur_player_name(self):
        self._cur_player = self.game.get_cur_player()
        self._cur_player_name.set('Current Player: {0} ({1})'.format(
            self._cur_player.color,
            self._cur_player.name
        ))


class UndoRedoFrame(tkinter.Frame):

    def __init__(self, master, game, *args, **kwargs):
        super(UndoRedoFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        tkinter.Label(self, text="Undo").pack(anchor=tkinter.W)
        self.undo = tkinter.Button(self, text="Undo", command=self.on_undo)
        self.redo = tkinter.Button(self, text="Redo", command=self.on_redo)

        self.undo.pack(side=tkinter.LEFT, fill=tkinter.X, expand=tkinter.YES)
        self.redo.pack(side=tkinter.RIGHT, fill=tkinter.X, expand=tkinter.YES)

        self.set_states()

        self.bind_all('<Left>', lambda e: self.on_undo())
        self.bind_all('<Right>', lambda e: self.on_redo())

    def notify(self, observable):
        # logging.debug('UndoRedoFrame.notify called and calling undoredoframe.set_states')
        self.set_states()

    def set_states(self):
        self.undo.configure(state=can_do[self.game.undo_manager.can_undo()])
        self.redo.configure(state=can_do[self.game.undo_manager.can_redo()])

    def on_undo(self):
        self.game.undo()

    def on_redo(self):
        self.game.redo()


class RollFrame(tkinter.Frame):

    def __init__(self, master, game, *args, **kwargs):
        super(RollFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.smallnumbers = tkinter.Frame (self)
        self.smallnumbers.pack (side='left')
        self.mediumnumbers = tkinter.Frame (self)
        self.mediumnumbers.pack (side='left', fill=tkinter.Y)
        self.largenumbers = tkinter.Frame (self,)
        self.largenumbers.pack (side='left')

        self.two = tkinter.Button (self.smallnumbers, command=lambda:self.on_roll(2), text= '2')
        self.two.grid (row=1, column=1, sticky=tkinter.NSEW)
        self.three = tkinter.Button (self.smallnumbers, command=lambda:self.on_roll(3), text= '3')
        self.three.grid (row=1, column=2, sticky=tkinter.NSEW)
        self.four = tkinter.Button (self.smallnumbers, command=lambda:self.on_roll(4), text= '4')
        self.four.grid (row=2, column=1, sticky=tkinter.NSEW)
        self.five = tkinter.Button (self.smallnumbers, command=lambda:self.on_roll(5), text= '5')
        self.five.grid (row=2, column=2, sticky=tkinter.NSEW)

        self.six = tkinter.Button (self.mediumnumbers, command=lambda:self.on_roll(6), text= '6')
        self.six.pack (side='left', expand=True)
        self.seven = tkinter.Button (self.mediumnumbers, command=lambda:self.on_roll(7), text= '7')
        self.seven.pack (side='left', expand=True)
        self.eight = tkinter.Button (self.mediumnumbers, command=lambda:self.on_roll(8), text= '8')
        self.eight.pack (side='left', expand=True)
        self.nine = tkinter.Button (self.largenumbers, command=lambda:self.on_roll(9), text= '9')
        self.nine.grid (row=1, column =1)
        self.ten = tkinter.Button (self.largenumbers, command=lambda:self.on_roll(10), text= '10')
        self.ten.grid (row=1, column=2)
        self.eleven = tkinter.Button (self.largenumbers, command=lambda:self.on_roll(11), text='11')
        self.eleven.grid (row=2, column =1)
        self.twelve = tkinter.Button (self.largenumbers, command=lambda:self.on_roll(12), text='12')
        self.twelve.grid (row=2, column=2)

        self.bind_all('2', self.roll_event_HO(2))
        self.bind_all('3', self.roll_event_HO(3))
        self.bind_all('4', self.roll_event_HO(4))
        self.bind_all('5', self.roll_event_HO(5))
        self.bind_all('6', self.roll_event_HO(6))
        self.bind_all('7', self.roll_event_HO(7))
        self.bind_all('8', self.roll_event_HO(8))
        self.bind_all('9', self.roll_event_HO(9))
        self.bind_all('0', self.roll_event_HO(10))
        self.bind_all('-', self.roll_event_HO(11))
        self.bind_all('=', self.roll_event_HO(12))

        self.set_states()

    def roll_event_HO(self, roll):
        def roll_event(event):
            if self.game.state.can_roll():
                self.on_roll(roll)
        return roll_event

    def notify(self, observable):
        # logging.debug('rollframe.notify called and calling RollFrame.set_states')
        self.set_states()

    def set_states(self):
        self.two.configure(state=can_do[self.game.state.can_roll()])
        self.three.configure(state=can_do[self.game.state.can_roll()])
        self.four.configure(state=can_do[self.game.state.can_roll()])
        self.five.configure(state=can_do[self.game.state.can_roll()])
        self.six.configure(state=can_do[self.game.state.can_roll()])
        self.seven.configure(state=can_do[self.game.state.can_roll()])
        self.eight.configure(state=can_do[self.game.state.can_roll()])
        self.nine.configure(state=can_do[self.game.state.can_roll()])
        self.ten.configure(state=can_do[self.game.state.can_roll()])
        self.eleven.configure(state=can_do[self.game.state.can_roll()])
        self.twelve.configure(state=can_do[self.game.state.can_roll()])


    def on_roll(self, roll):
        self.game.roll(roll)
        self.set_states()


class RobberFrame(tkinter.Frame):

    def __init__(self, master, game):
        super(RobberFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.label = tkinter.Label(self, text="Steal", anchor=tkinter.W)

        self.steal_frame = tkinter.Frame(self)
        self.player_strs = [str(player) for player in self.game.players]
        self.player_str = tkinter.StringVar()
        self.player_picker = tkinter.OptionMenu(self.steal_frame, self.player_str, self.player_str.get(), *self.player_strs) # reassigned in set_states
        self.steal = tkinter.Button(self.steal_frame, text="Steal", state=tkinter.DISABLED, command=self.on_steal)

        self.player_picker.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.steal.pack(side=tkinter.RIGHT, fill=tkinter.X, expand=True)

        self.set_states()

        self.label.pack(fill=tkinter.X)
        self.steal_frame.pack(fill=tkinter.X, expand=True)

    def notify(self, observable):
        # logging.debug('robberframe.notify called and calling robberframe.set_states')
        self.set_states()

    def set_states(self):
        # logging.debug('views.set_states called and calling game.stealable_players')
        stealable_strs = [str(player) for player in self.game.stealable_players()]
        # logging.debug('stealable_players={}'.format(stealable_strs))
        if stealable_strs:
            self.player_str.set(stealable_strs[0])
        else:
            self.player_str.set('')
        if stealable_strs:
            # logging.debug('stealable set state stealable_strs({})={}, picked_str({})={}'.format(
                # type(stealable_strs[0]), stealable_strs,
                # type(self.player_str.get()), self.player_str.get()
            # ))
            tkinterutils.refresh_option_menu(self.player_picker, self.player_str,
                                         new_options=[s for s in stealable_strs if s != self.player_str.get()])

        self.player_picker.configure(state=can_do[self.game.state.can_steal()])
        self.steal.configure(state=can_do[self.game.state.can_steal()])

    def on_steal(self):
        victim_str = self.player_str.get()
        victim = None
        for player in self.game.players:
            if victim_str == str(player):
                victim = player
        # logging.debug('in view, stealing from victim={} (victim_str={})'.format(victim, victim_str))
        self.game.steal(victim)

    def _other_player_strs(self):
        cur_str = str(self.game.get_cur_player())
        return list(filter(lambda pstr: pstr != cur_str, self.player_strs))


class BuildFrame(tkinter.Frame):

    def __init__(self, master, game):
        super(BuildFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.label = tkinter.Label(self, text="Build", anchor=tkinter.W)
        self.road = tkinter.Button(self, text="Road", command=self.on_buy_road, anchor=tkinter.W)
        self.settlement = tkinter.Button(self, text="Settlement", command=self.on_buy_settlement, anchor=tkinter.E)
        self.city = tkinter.Button(self, text="City", command=self.on_buy_city, anchor=tkinter.W)
        self.dev_card = tkinter.Button(self, text="Dev Card", command=self.on_buy_dev_card, anchor=tkinter.E)

        self.bind_all('r', lambda e: self.on_buy_road())
        self.bind_all('s', lambda e: self.on_buy_settlement())
        self.bind_all('c', lambda e: self.on_buy_city())
        self.bind_all('d', lambda e: self.on_buy_dev_card())

        self.set_states()

        self.label.grid(row=1, column=1, sticky=tkinter.W)
        self.road.grid(row=2, column=1, sticky=tkinter.EW)
        self.settlement.grid(row=2, column=2, sticky=tkinter.EW)
        self.city.grid(row=3, column=1, sticky=tkinter.EW)
        self.dev_card.grid(row=3, column=2, sticky=tkinter.EW)

    def notify(self, observable):
        # logging.debug('buildframe.notify called and calling builframe.set_states')
        self.set_states()

    def set_states(self):
        self.road.configure(state=can_do[self.game.state.can_buy_road()])
        self.settlement.configure(state=can_do[self.game.state.can_buy_settlement()])
        self.city.configure(state=can_do[self.game.state.can_buy_city()])
        self.dev_card.configure(state=can_do[self.game.state.can_buy_dev_card()])

    def on_buy_road(self):
        # actual road purchase and catanlog happens in the piece onclick in BoardFrame
        self.game.begin_placing(PieceType.road)

    def on_buy_settlement(self):
        # see on_buy_road
        self.game.begin_placing(PieceType.settlement)

    def on_buy_city(self):
        # see on_buy_road
        self.game.begin_placing(PieceType.city)

    def on_buy_dev_card(self):
        self.game.buy_dev_card()


class PlayDevCardFrame(tkinter.Frame):

    def __init__(self, master, game):
        super(PlayDevCardFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.label = tkinter.Label(self, text="Play Dev Card", anchor=tkinter.W)
        self.knight = tkinter.Button(self, text="Knight", command=self.on_knight)
        self.road_builder = tkinter.Button(self, text="Road Builder", command=self.on_road_builder)
        self.victory_point = tkinter.Button(self, text="Victory Point", command=self.on_victory_point)

        self.bind_all('k', lambda e: self.on_knight())

        self.monopoly_frame = tkinter.Frame(self)
        self.monopoly = tkinter.Button(self.monopoly_frame, text="Monopoly", command=self.on_monopoly)
        option_list = list(t.value for t in Terrain if t != Terrain.desert)
        self.monopoly_choice = tkinter.StringVar()
        self.monopoly_choice.set(option_list[0])
        self.monopoly_picker = tkinter.OptionMenu(self.monopoly_frame, self.monopoly_choice, *option_list)

        self.year_of_plenty_frame = tkinter.Frame(self)
        self.year_of_plenty = tkinter.Button(self.year_of_plenty_frame, text="Year of Plenty", command=self.on_year_of_plenty)
        option_list = list(t.value for t in Terrain if t != Terrain.desert)
        self.year_of_plenty_choice1 = tkinter.StringVar()
        self.year_of_plenty_choice2 = tkinter.StringVar()
        self.year_of_plenty_choice1.set(option_list[0])
        self.year_of_plenty_choice2.set(option_list[1])
        self.year_of_plenty_picker1 = tkinter.OptionMenu(self.year_of_plenty_frame,
                                                         self.year_of_plenty_choice1,
                                                         *option_list)
        self.year_of_plenty_picker2 = tkinter.OptionMenu(self.year_of_plenty_frame,
                                                         self.year_of_plenty_choice2,
                                                         *option_list)

        self.set_states()

        self.monopoly_picker.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.monopoly.pack(side=tkinter.RIGHT, fill=tkinter.X, expand=True)

        self.year_of_plenty_picker1.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.year_of_plenty_picker2.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.year_of_plenty.pack(side=tkinter.RIGHT, fill=tkinter.X, expand=True)

        self.label.pack(fill=tkinter.X)
        self.knight.pack(fill=tkinter.X, expand=True)
        self.monopoly_frame.pack(fill=tkinter.X, expand=True)
        self.year_of_plenty_frame.pack(fill=tkinter.X, expand=True)
        self.road_builder.pack(fill=tkinter.X, expand=True)
        self.victory_point.pack(fill=tkinter.X, expand=True)

    def notify(self, observable):
        # logging.debug('PlayDevCardFrame.notify called and calling PlayDevCardFrame.set_states')
        self.set_states()

    def set_states(self):
        self.knight.configure(state=can_do[self.game.state.can_play_knight()])
        self.monopoly.configure(state=can_do[self.game.state.can_play_monopoly()])
        self.monopoly_picker.configure(state=can_do[self.game.state.can_play_monopoly()])
        self.year_of_plenty.configure(state=can_do[self.game.state.can_play_year_of_plenty()])
        self.year_of_plenty_picker1.configure(state=can_do[self.game.state.can_play_year_of_plenty()])
        self.year_of_plenty_picker2.configure(state=can_do[self.game.state.can_play_year_of_plenty()])
        self.road_builder.configure(state=can_do[self.game.state.can_play_road_builder()])
        self.victory_point.configure(state=can_do[self.game.state.can_play_victory_point()])

    def on_knight(self):
        # logging.debug('play dev card: knight clicked')
        self.game.play_knight()

    def on_monopoly(self):
        # logging.debug('play dev card: monopoly clicked, resource={}'.format(self.monopoly_choice.get()))
        self.game.play_monopoly(Terrain(self.monopoly_choice.get()))

    def on_year_of_plenty(self):
        # logging.debug('play dev card: year of plenty clicked, resources=({} and {})'.format(
            # self.year_of_plenty_choice1.get(),
            # self.year_of_plenty_choice2.get()
        # ))
        self.game.play_year_of_plenty(Terrain(self.year_of_plenty_choice1.get()),
                                      Terrain(self.year_of_plenty_choice2.get()))

    def on_road_builder(self):
        # logging.debug('play dev card: road builder clicked')
        self.game.set_state(states.GameStatePlacingRoadBuilderPieces(self.game))

    def on_victory_point(self):
        # logging.debug('play dev card: victory point clicked')
        self.game.play_victory_point()


class EndTurnFrame(tkinter.Frame):

    def __init__(self, master, game):
        super(EndTurnFrame, self).__init__(master)
        self.master = master
        self.game = game
        self.game.observers.add(self)

        self.label = tkinter.Label(self, text='--')
        self.end_turn = tkinter.Button(self, text='End Turn', state=tkinter.DISABLED, command=self.on_end_turn)

        self.bind_all('<space>', self.on_end_turn)

        self.set_states()

        self.label.pack()
        self.end_turn.pack(side=tkinter.TOP, fill=tkinter.X)

    def notify(self, observable):
        # logging.debug('EndTurnFrame.notify called and calling EndTurnFrame.set_states')
        self.set_states()

    def set_states(self):
        if self.game.state.can_end_turn():
            self.end_turn.configure(state=tkinter.NORMAL)
        else:
            self.end_turn.configure(state=tkinter.DISABLED)

    def on_end_turn(self, event=None):
        if self.game.state.can_end_turn():
            self.game.end_turn()


class EndGameFrame(tkinter.Frame):

    def __init__(self, master, game):
        super(EndGameFrame, self).__init__(master)
        self.master = master
        self.game = game

        self.end_game = tkinter.Button(self, text='End Game', state=tkinter.NORMAL, command=self.on_end_game)
        self.end_game.pack(side=tkinter.TOP, fill=tkinter.X)

    def on_end_game(self):
        title = 'End Game Confirmation'
        message = 'End Game? ({0} ({1}) wins)'.format(
            self.game.get_cur_player().color, self.game.get_cur_player().name
        )
        if messagebox.askyesno(title, message):
            self.game.end()


class TkinterOptionWrapper:
    """Dynamically hook up the board options to tkinter checkbuttons.

    Tkinter checkbuttons use a tkinter 'var' object to store the checkbutton
    value, so dynamically create those vars based on the board options and
    keep them here, along with callbacks to update the board options when the
    checkbutton is checked/unchecked.

    Also stores the option description text. That should probably belong to the
    board option 'class', but at the moment there's no reason not to keep that
    a simple dict.

    Parameters
    ----------

    options : A dict of option identifier (name) to option value

    The wrapper will dynamically update the value of the option in the
    option_dict when the user checks or unchecks the corresponding checkbutton
    in the UI.
    """

    Option = collections.namedtuple('_Option', ['text', 'var', 'callback'])
    _descriptions = {
        'hex_resource_selection': 'Cycle resource',
        'hex_number_selection': 'Cycle number'
    }

    def __init__(self, option_dict):
        self._opts = {}

        # Can't define this as a closure inside the following for loop as each
        # definition will become the value of cb which has a scope local to the
        # function, not to the for loop.  Use functools.partial in the loop to
        # create a specific callable instance.
        def cb_template(name, var):
            option_dict[name] = var.get()
        for name, value in option_dict.items():
            var = tkinter.BooleanVar()
            var.set(value)
            cb = functools.partial(cb_template, name, var)
            self._opts[name] = self.Option(self._descriptions.get(name) or name, var, cb)

    def __getattr__(self, name):
        attr = self.__dict__.get(name)
        if '_opts' in self.__dict__ and not attr:
            attr = self._opts.get(name)
        return attr

    def __iter__(self):
        for opt in sorted(self._opts.values()):
            yield opt

