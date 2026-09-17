/**
 * One colour per game, keyed by PokéAPI version slug, for the cartridge spine on a game card and the
 * game slot in the header. Decorative only: no text sits on these, so they carry no contrast duty.
 * Expansions share their base game's colour. Anything unknown falls back to the chassis orange.
 */

const COLORS: Record<string, string> = {
  red: '#E3350D',
  'red-japan': '#E3350D',
  'green-japan': '#2E9E4F',
  blue: '#0075BE',
  'blue-japan': '#0075BE',
  yellow: '#FFCB05',
  gold: '#D4A017',
  silver: '#9DA3AE',
  crystal: '#5CC3E6',
  ruby: '#A00E1E',
  sapphire: '#1F4FB0',
  emerald: '#009E60',
  firered: '#E64A19',
  leafgreen: '#43A047',
  colosseum: '#4B3F72',
  xd: '#5B2C6F',
  diamond: '#5A8FC7',
  pearl: '#D77BB0',
  platinum: '#8A8F9C',
  heartgold: '#D9A21B',
  soulsilver: '#8FA3B1',
  black: '#2B2B2B',
  white: '#BFC6D1',
  'black-2': '#2B2B2B',
  'white-2': '#BFC6D1',
  x: '#025DA6',
  y: '#EA1A3E',
  'omega-ruby': '#C8102E',
  'alpha-sapphire': '#1E64B4',
  sun: '#F58220',
  moon: '#6A3FA0',
  'ultra-sun': '#FF9F1C',
  'ultra-moon': '#4B2E83',
  'lets-go-pikachu': '#F5C518',
  'lets-go-eevee': '#B5651D',
  sword: '#1D9BF0',
  shield: '#E0245E',
  'the-isle-of-armor-sword': '#1D9BF0',
  'the-isle-of-armor-shield': '#E0245E',
  'the-crown-tundra-sword': '#1D9BF0',
  'the-crown-tundra-shield': '#E0245E',
  'brilliant-diamond': '#4F9ED9',
  'shining-pearl': '#E07FB5',
  'legends-arceus': '#6E8B3D',
  scarlet: '#F34134',
  violet: '#8B3FC8',
  'the-teal-mask-scarlet': '#F34134',
  'the-teal-mask-violet': '#8B3FC8',
  'the-indigo-disk-scarlet': '#F34134',
  'the-indigo-disk-violet': '#8B3FC8',
  'legends-za': '#2F6F9F',
  'mega-dimension': '#7B61FF',
  champions: '#FFB000',
}

export const GAME_COLOR_FALLBACK = 'var(--chassis)'

export function gameColor(slug: string | null | undefined): string {
  return (slug && COLORS[slug]) || GAME_COLOR_FALLBACK
}
