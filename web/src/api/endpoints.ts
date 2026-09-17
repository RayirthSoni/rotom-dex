/**
 * One function per endpoint. `game` is a required argument everywhere the API requires it, so no
 * module can quietly fall back to a default and show one game's data under another's name.
 */

import { get, plain, post, query } from './client'
import type {
  AbilityDetail, AbilityListRow, AcquisitionData, BattleDetail, BattleSummary, BossPreparation,
  CoverageMatrix, CoverageRow, DataIssue, Envelope, EvolutionChain, EvolutionData,
  EvolutionRequirements, GameDetail, GameListRow, Health, ItemDetail, ItemListRow, LearnsetData,
  ChatAnswer, ChatStatus, ChatTurn,
  Matchup, Milestone, MoveAccessResult, MoveDetail, MoveListRow, Nature, PokemonCard,
  PokemonListRow, ReachabilityResult, TeamAnalysis, TutorsData, TypeChart, TypeRow, Vocabulary,
} from './types'

export interface Paged {
  limit?: number
  offset?: number
}

export const api = {
  health: () => plain<Health>('/health'),

  games: () => get<GameListRow[]>('/api/games'),
  game: (game: string) => get<GameDetail>(`/api/games/${game}`),
  coverage: (game: string) => get<CoverageRow[]>(`/api/coverage${query({ game })}`),
  coverageMatrix: (notes = false) => get<CoverageMatrix>(`/api/coverage/matrix${query({ notes: notes || undefined })}`),
  issues: (game?: string) => get<DataIssue[]>(`/api/issues${query({ game })}`),
  vocabulary: (game: string) => get<Vocabulary>(`/api/vocabulary${query({ game })}`),

  types: (game: string) => get<TypeRow[]>(`/api/types${query({ game })}`),
  typeChart: (game: string) => get<TypeChart>(`/api/type-effectiveness/chart${query({ game })}`),
  matchup: (game: string, attack: string, defense: string, defense2?: string) =>
    get<Matchup>(`/api/type-effectiveness${query({ game, attack, defense, defense2 })}`),
  natures: (game: string) => get<Nature[] | null>(`/api/natures${query({ game })}`),
  nature: (game: string, nature: string) => get<Nature | null>(`/api/natures/${nature}${query({ game })}`),

  pokemonSearch: (game: string, opts: Paged & { q?: string; type?: string } = {}) =>
    get<PokemonListRow[]>(`/api/pokemon${query({ game, ...opts })}`),
  pokemon: (game: string, slug: string, include?: string, maxLevel?: number) =>
    get<PokemonCard | null>(`/api/pokemon/${slug}${query({ game, include, max_level: maxLevel })}`),
  acquisition: (game: string, slug: string) => get<AcquisitionData | null>(`/api/pokemon/${slug}/acquisition${query({ game })}`),
  evolution: (game: string, slug: string) => get<EvolutionData | null>(`/api/pokemon/${slug}/evolution${query({ game })}`),
  evolutionChain: (game: string, slug: string) => get<EvolutionChain | null>(`/api/pokemon/${slug}/evolution-chain${query({ game })}`),
  learnset: (game: string, slug: string, opts: { method?: string; max_level?: number } = {}) =>
    get<LearnsetData | null>(`/api/pokemon/${slug}/learnset${query({ game, ...opts })}`),

  moves: (game: string, opts: Paged & { q?: string; type?: string; damage_class?: string } = {}) =>
    get<MoveListRow[]>(`/api/moves${query({ game, ...opts })}`),
  move: (game: string, slug: string) => get<MoveDetail | null>(`/api/moves/${slug}${query({ game })}`),
  items: (game: string, opts: Paged & { q?: string; category?: string } = {}) =>
    get<ItemListRow[]>(`/api/items${query({ game, ...opts })}`),
  item: (game: string, slug: string) => get<ItemDetail | null>(`/api/items/${slug}${query({ game })}`),
  abilities: (game: string, opts: Paged & { q?: string } = {}) => get<AbilityListRow[] | null>(`/api/abilities${query({ game, ...opts })}`),
  ability: (game: string, slug: string) => get<AbilityDetail | null>(`/api/abilities/${slug}${query({ game })}`),
  tutors: (game: string) => get<TutorsData | null>(`/api/tutors${query({ game })}`),

  milestones: (game: string) => get<Milestone[] | null>(`/api/milestones${query({ game })}`),
  battles: (game: string) => get<BattleSummary[] | null>(`/api/battles${query({ game })}`),
  battle: (game: string, slug: string) => get<BattleDetail | null>(`/api/battles/${slug}${query({ game })}`),

  teamAnalyze: (context: unknown) => post<TeamAnalysis | null>('/api/team/analyze', { context }),
  bossPrepare: (context: unknown, battle: string) => post<BossPreparation | null>('/api/boss/prepare', { context, battle }),
  reachability: (context: unknown, pokemon: string[], items: string[]) =>
    post<ReachabilityResult | null>('/api/acquisition/reachability', { context, pokemon, items }),
  moveAccess: (context: unknown, pokemon: string, member?: number) =>
    post<MoveAccessResult | null>(`/api/pokemon/${pokemon}/move-access`, { context, pokemon, member }),
  evolutionRequirements: (context: unknown, pokemon: string, member?: number) =>
    post<EvolutionRequirements | null>(`/api/pokemon/${pokemon}/evolution-requirements`, { context, pokemon, member }),

  chatStatus: () => plain<ChatStatus>('/api/chat/status'),
  chat: (context: unknown, message: string, history: ChatTurn[]) =>
    post<ChatAnswer | null>('/api/chat', { context, message, history }),
}

export type Api = typeof api
export type { Envelope }
