/**
 * Icons as grid strings. `#` is ink, `.` is transparent, `o` is a second ink
 * used only for the robot's eyes; one character is one pixel. Every icon is
 * rendered with `shape-rendering: crispEdges` so it lands on whole device pixels
 * at any size — the one rule that separates a pixel icon from a smooth SVG that
 * happens to be small.
 *
 * This replaces three hand-written smooth SVGs (SunIcon, MoonIcon, GitHubMark),
 * the chevron that was baked into a CSS data-URI on `.select`, and the loose
 * Unicode glyphs (`✓ ✗ ⊘ ▲ ▼ →`) typed inline as text.
 */

export const ICONS = {
  /* Navigation and chrome */
  "chevron-down": [
    "#.......#",
    "##.....##",
    "###...###",
    "#########",
    ".#######.",
    "..#####..",
    "...###...",
    "....#....",
    ".........",
  ],
  "chevron-right": [
    "...#.....",
    "..##.....",
    ".###.....",
    "########.",
    ".###.....",
    "..##.....",
    "...#.....",
  ],
  "arrow-left": [
    "....#....",
    "....##...",
    "...###...",
    "..####...",
    "#########",
    "..####...",
    "...###...",
    "....##...",
    "....#....",
  ],
  "arrow-right": [
    "....#....",
    "...##....",
    "..###....",
    ".####....",
    "#########",
    ".####....",
    "..###....",
    "...##....",
    "....#....",
  ],

  /* Theme toggle */
  sun: [
    "....#....",
    "#...#...#",
    ".#.#.#.#.",
    "..#.#.#..",
    "#########",
    "..#.#.#..",
    ".#.#.#.#.",
    "#...#...#",
    "....#....",
  ],
  moon: [
    "..#####..",
    ".#######.",
    "#####....",
    "####.....",
    "####.....",
    "#####....",
    ".#######.",
    "..#####..",
  ],

  /* Brand mark — a filled square with a bite out of the top-right corner. */
  logo: [
    "######...",
    "######...",
    "#####....",
    "####.....",
    "###......",
    "##.......",
    "#........",
  ],

  /* Login hero — a 16×16 robot head. Every row is exactly 16 characters;
     PixelIcon.test.ts fails the build if one is not. */
  "robot-open": [
    "....########....",
    "...##oo##oo##...",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..############..",
    "..############..",
    "..#..######..#..",
    "..#..######..#..",
    "..############..",
    "..############..",
    "...##########...",
    "................",
    "................",
  ],
  "robot-blink": [
    "....########....",
    "...##oo##oo##...",
    "..############..",
    "..##oo#####oo#..",
    "..############..",
    "..############..",
    "..############..",
    "..############..",
    "..#..######..#..",
    "..#..######..#..",
    "..############..",
    "..############..",
    "..############..",
    "...##########...",
    "................",
    "................",
  ],

  /* Feedback — the old Unicode glyphs, as sprites. */
  check: [
    ".......#",
    "......##",
    "#....##.",
    "##..##..",
    ".####...",
    "..##....",
    "........",
    "........",
  ],
  cross: [
    "#......#",
    "##....##",
    ".##..##.",
    "..####..",
    "...##...",
    "..####..",
    ".##..##.",
    "##....##",
    "#......#",
  ],
  ban: [
    ".#######.",
    "##.....##",
    "#.#...#.#",
    "#..#....#",
    "#.#...#.#",
    "#..#....#",
    "#.#...#.#",
    "##.....##",
    ".#######.",
  ],
  triangle: [
    "....#....",
    "...###...",
    "..#####..",
    "#########",
    "....#....",
    "....#....",
    "....#....",
    ".........",
  ],
  copy: [
    "####....",
    "####..##",
    "#..#..##",
    "#..#....",
    "#..#####",
    "#..#####",
    "#..#....",
    "####....",
  ],

  /* Providers */
  github: [
    ".####..###...###",
    "#....#.#......#.",
    "#.......#.....#.",
    "#.##....#.##..#.",
    "#.#...........#.",
    "#..##.....##..#.",
    ".####..###...###",
  ],
} as const satisfies Record<string, readonly string[]>;

export type PixelIconName = keyof typeof ICONS;

export interface PixelIconProps {
  name: PixelIconName;
  /** Rendered size in CSS pixels. Defaults to 16. */
  size?: number;
  className?: string;
  /** Supplying this makes the icon labelled; omitting it marks it decorative. */
  title?: string;
}

/**
 * `o` is a second "ink" cell, used by the robot sprite for its eyes. It renders in
 * the same colour — the shape reads at 16px, a two-tone eye would not.
 */
function cellsOf(grid: readonly string[]): Array<{ x: number; y: number }> {
  const cells: Array<{ x: number; y: number }> = [];
  grid.forEach((row, y) => {
    row.split("").forEach((char, x) => {
      if (char === "#" || char === "o") cells.push({ x, y });
    });
  });
  return cells;
}

export function PixelIcon({ name, size = 16, className, title }: PixelIconProps) {
  const grid = ICONS[name] as readonly string[];
  const columns = grid[0].length;
  const rows = grid.length;
  const cell = size / Math.max(columns, rows);
  const labels = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true };

  return (
    <svg
      width={columns * cell}
      height={rows * cell}
      viewBox={`0 0 ${columns} ${rows}`}
      fill="currentColor"
      shapeRendering="crispEdges"
      className={className}
      {...labels}
    >
      {title ? <title>{title}</title> : null}
      {cellsOf(grid).map(({ x, y }) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} />
      ))}
    </svg>
  );
}