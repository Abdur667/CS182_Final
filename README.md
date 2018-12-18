catan-spectator
---------------

A GUI for Mac and Windows for spectating and logging games of Settlers of Catan.

Other projects can read game logs and do useful things, i.e.

* semi-automated tournaments: draws, matchups, stats, tiebreakers computed from game logs.
* machine learning: game outcome prediction, AI development

Todos are listed below.

> Author: Ross Anderson ([rosshamish](https://github.com/rosshamish))

### Demo
![Demo](/doc/gifs/v0.1.3-demo.mov.gif)

### Usage

See http://rosshamish.github.io/catan-spectator

### Development

Clone, install dependencies:
```
$ git clone https://github.com/rosshamish/catan-spectator
$ cd catan-spectator
$ pip3 install -r requirements.txt
```

Basic usage:
```
$ python3 main.py
```

Full list of options:
```
$ python3 main.py --help
usage: main.py [-h] [--board BOARD] [--terrain TERRAIN] [--numbers NUMBERS]
               [--ports PORTS] [--pieces PIECES] [--players PLAYERS]
               [--pregame PREGAME]  [--use_stdout]

log a game of catan

optional arguments:
  -h, --help         show this help message and exit
  --board BOARD      string with space-separated short-codes for terrain and
                     numbers, e.g. 'w w h b s o w w b ... 2 None 9 3 4 6 ...'
  --terrain TERRAIN  random|preset|empty|debug, default random
  --numbers NUMBERS  random|preset|empty|debug, default preset
  --ports PORTS      random|preset|empty|debug, default preset
  --pieces PIECES    random|preset|empty|debug, default preset
  --players PLAYERS  random|preset|empty|debug, default preset
  --pregame PREGAME  on|off, default oncatan-spectator
  --use_stdout       write to stdout
```

Make targets:
```
- `make relaunch`: launch (or relaunch) the GUI
- `make logs`: cat the python logs
- `make tail`: tail the python logs
- `make`: alias for relaunch && tailFor a particular board layout:
```

### File Format

<!-- remember to update this section in sync with "File Format" in github.com/rosshamish/catan-py/README.md -->

catan-spectator writes game logs in the `.catan` format described by package [`catanlog`](https://github.com/rosshamish/catanlog).

They look like this:

```
green rolls 6
blue buys settlement, builds at (1 NW)
orange buys city, builds at (1 SE)
red plays monopoly on ore
```

### Todos

Need to have
- [ ] views documented
- [x] piece placing should be cancellable (via undo)
- [x] all actions should be undoable
- [ ] ui+catanlog: save log file to custom location on End Game
- [ ] ui: city-shaped polygon for cities
- [ ] ui/ux improvements

Nice to have
- [ ] board: random number setup obeys red number rule
- [ ] ui+board+hexgrid: during piece placement, use little red x’s (at least in debug mode) on “killed spots”
- [ ] ui+game+player+states: dev cards, i.e. keep a count of how many dev cards a player has played and enable Play Dev Card buttons if num > 0
- [x] ui+game+port+hexgrid: port trading, disable buttons if the current player doesn’t have the port. 4:1 is always enabled.
- [x] ui+port+hexgrid: port trading, don't allow getting or giving more or less than defined by the port type (3:1, 2:1).
- [ ] ui+port: port trading, don’t allow n for 0 trades
- [ ] ui: large indicator off what the current player is (and what the order is)
- [x] ui: cancelling of roads/settlements/cities while placing
- [ ] ui: images, colors in UI buttons (eg dice for roll, )
- [attempted, might be worse] ui: tile images instead of colored hexagons
- [ ] ui: port images instead of colored triangles
- [ ] ui: piece images instead of colored polygons
- [x] ui: number images instead of text (or avoid contrast issues otherwise)
- [ ] ui+game+states+robber: steal dropdown has “nil” option always, for in case it goes on a person with no cards and no steal happens. Name it something obvious, don’t use an empty string.

### Attribution

Codebase originally forked from [fruitnuke/catan](https://github.com/fruitnuke/catan), a catan board generator

### License

GPLv3
# CS182_Final
# CS182_Final
