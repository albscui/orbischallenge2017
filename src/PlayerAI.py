from PythonClientAPI.Game import PointUtils
from PythonClientAPI.Game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.Game.Enums import Direction, MoveType, MoveResult
from PythonClientAPI.Game.World import World


class PlayerAI:

    def __init__(self):
        """
        Any instantiation code goes here
        """
        self.current_target_nest = None
        self.avoid = set()
        self.queen_nest = None
        self.nesting_sites = None
        self.map_size = None
        self.current_phase = 1
        self.original_neutral_tiles = None

    def do_move(self, world, friendly_units, enemy_units):
        """
        This method will get called every turn.
        
        :param world: World object reflecting current game state
        :param friendly_units: list of FriendlyUnit objects
        :param enemy_units: list of EnemyUnit objects
        """

        if self.map_size is None:
            self.map_size = world.get_height() * world.get_width()
        if self.original_neutral_tiles is None:
            self.original_neutral_tiles = len(world.get_neutral_tiles())

        if len(world.get_neutral_tiles()) / self.original_neutral_tiles >= 0.1:
            # Phase I
            self.phaseI(world, friendly_units, enemy_units)
        else:
            # Phase II
            self.phaseII(world, friendly_units, enemy_units)

    def move_unit(self, world, unit, position, avoid=set()):
        path = world.get_shortest_path(unit.position, position, avoid)
        if path:
            world.move(unit, path[0])

    def phaseI(self, world, friendly_units, enemy_units):
        if self.queen_nest is None:
            self.queen_nest = world.get_friendly_nest_positions()[0]

        ## Build nests
        builders = set()
        if self.nesting_sites is None:
            self.nesting_sites = set(self.get_nesting_sites(world))
            self.avoid = self.avoid.union(self.nesting_sites)
        builder_target_sites = {site for l in [self.get_nesting_site_targets(world, site) for site in self.nesting_sites] for site in l}
        for target in builder_target_sites:
            builder = world.get_closest_friendly_from(target, builders)
            self.move_unit(world, builder, target, self.avoid)
            builders.add(builder)

        # Check which sites are nests and remove them from self.nesting_sites
        self.nesting_sites = self.nesting_sites - set(world.get_friendly_nest_positions())

        ## Explorer
        explorers = set(friendly_units) - builders
        for explorer in explorers:
            target_tile = world.get_closest_capturable_tile_from(explorer.position, self.avoid)
            self.move_unit(world, explorer, target_tile.position, self.avoid)

    def phaseII(self, world, friendly_units, enemy_units):
        friendly_nests = world.get_friendly_nest_positions()

        # Defend
        dangerous_enemies = set()
        defenders = set()
        for nest in friendly_nests:
            for d, position in world.get_neighbours(nest).items():
                enemy = world.get_closest_enemy_from(position, dangerous_enemies)
                defender1 = world.get_closest_friendly_from(enemy.position, defenders)
                defenders.add(defender1)
                dangerous_enemies.add(enemy)
                self.move_unit(world, defender1, enemy.position)

                if world.get_shortest_path_distance(enemy.position, position) <= 3:
                    defender2 = world.get_closest_friendly_from(position, defenders)
                    defenders.add(defender2)
                    self.move_unit(world, defender2, position)

        # Explore then attack
        friendly_units = sorted(list(set(friendly_units) - defenders), key=lambda x: x.health)
        split = len(friendly_units) // 10
        # Use a small portion of units to keep on exploring
        for unit in friendly_units[:split]:
            target_tile = world.get_closest_capturable_tile_from(unit.position, set())
            self.move_unit(world, unit, target_tile.position, set())

        # Use majority of units to attack enemy nests
        for unit in friendly_units[split:]:
            target = world.get_closest_enemy_nest_from(unit.position, set())
            self.move_unit(world, unit, target)

    def get_nesting_sites(self, world):

        limit = self.original_neutral_tiles // 100

        # Figure out which positions to exclude as potential nesting sites
        # avoid = {p for d, p in world.get_neighbours(self.queen_nest).items()}.union({self.queen_nest})
        avoid = set(self.get_neighbours_fc(world, self.queen_nest))
        position_to_tiles = world.get_position_to_tile_dict()

        potential_nesting_sites = []
        for position, tile in position_to_tiles.items():
            if position in avoid or world.is_wall(position) or not tile.is_neutral():
                continue
            num_neighbours = len([t for d, t in world.get_tiles_around(position).items() if not t.is_friendly()])
            distance = world.get_shortest_path_distance(position, self.queen_nest)
            potential_nesting_sites.append((position, num_neighbours, distance))

        potential_nesting_sites = sorted(potential_nesting_sites, key=lambda x: (x[1], x[2]))

        nesting_sites = []
        for position, _, _ in potential_nesting_sites:
            if position in avoid:
                continue
            elif len(nesting_sites) == limit:
                break
            nesting_sites.append(position)
            avoid.union(set(self.get_neighbours_fc(world, position)))

        return nesting_sites

    def get_nesting_site_targets(self, world, nesting_site):

        neighbours = world.get_tiles_around(nesting_site)
        return [tile.position for d, tile in neighbours.items() if not tile.is_friendly()]

    def get_neighbours_fc(self, world, position):
        corners = ['NW', 'SW', 'NE', 'SE']
        neighbours = world.get_neighbours(position)
        result = [p for d, p in neighbours.items()]
        for corner in corners:
            try:
                if corner == "NW":
                    _neighbours = world.get_neighbours(neighbours[Direction.WEST])
                    result.append(_neighbours[Direction.NORTH])
                elif corner == 'SW':
                    _neighbours = world.get_neighbours(neighbours[Direction.WEST])
                    result.append(_neighbours[Direction.SOUTH])
                elif corner == 'NE':
                    _neighbours = world.get_neighbours(neighbours[Direction.EAST])
                    result.append(_neighbours[Direction.NORTH])
                elif corner == 'SE':
                    _neighbours = world.get_neighbours(neighbours[Direction.EAST])
                    result.append(_neighbours[Direction.SOUTH])
            except KeyError:
                continue

        return result

