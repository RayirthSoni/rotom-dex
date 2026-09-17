/**
 * Payload shapes, written by hand.
 *
 * The API types `Envelope.data` as `Any`, so OpenAPI codegen emits `unknown` for every payload —
 * exactly where types would be worth having. These mirror the SQL in `rotom_dex/repositories/`;
 * `tests/test_web_contract.py` fails if the backend stops matching them.
 *
 * SQLite booleans arrive as 0/1 on most rows but as real booleans on a few (`is_main_series`,
 * `holdable`, `neutral`). `asBool` in `client.ts` is the single place that difference is absorbed.
 */

export type CoverageStatus = 'complete' | 'partial' | 'missing' | 'disputed'
export type SupportTier = 'validated' | 'imported' | 'catalog' | 'excluded'
export type Availability = 'reachable' | 'locked' | 'unavailable' | 'unknown'
export type DerivedStatus = 'reachable' | 'locked' | 'unknown' | 'not-applicable'
export type DamageClass = 'physical' | 'special' | 'status'
export type VerificationStatus = 'source-derived' | 'reference-reviewed' | 'unverified' | 'disputed'

export interface GameSummary {
  id: number
  slug: string
  name: string
  version_group: string
  generation: number
  support_tier: SupportTier
}

export interface CoverageRow {
  feature: string
  subject: string
  status: CoverageStatus
  note: string
  evidence_id: string
}

export interface Pagination {
  limit: number
  offset: number
  total: number
}

export interface EvidenceSource {
  source_id: string
  kind: 'dataset' | 'game-pack' | 'reference' | 'code'
  url: string
  retrieved_at: string
  sha256: string | null
  license: string
  review_status: string
  selector: string
}

export interface Evidence {
  id: string
  sources: EvidenceSource[]
}

export interface Envelope<T> {
  game: GameSummary | null
  snapshot_id: string
  coverage_status: CoverageStatus
  coverage: CoverageRow[]
  data: T
  assumptions: string[]
  evidence: Evidence[]
  pagination?: Pagination
}

/* -- conditions ------------------------------------------------------------------------------ */

export type Condition =
  | { op: 'and' | 'or'; args: Condition[] }
  | { op: 'unknown'; reason: string }
  | { op: string; value?: string | number; reason?: string }

export interface ConditionLeaf {
  op: string
  value?: string | number
  reason?: string
}

export interface Verdict {
  status: DerivedStatus
  evaluation: boolean | null
  blocked_by: ConditionLeaf[]
  unknown_because: ConditionLeaf[]
  reason?: string
}

/* -- games and coverage ---------------------------------------------------------------------- */

export interface GameListRow {
  id: number
  slug: string
  name: string
  support_tier: SupportTier
  is_main_series: boolean
  note: string
  version_group: string
  generation: number
  coverage_status: CoverageStatus
  coverage_counts: Record<CoverageStatus, number>
}

export interface MechanicRow {
  key: string
  value: number
  note: string
  verification_status: string
  evidence_id: string
}

export interface GameDetail extends GameSummary {
  is_main_series: boolean
  note: string
  mechanics: MechanicRow[]
  issues: DataIssue[]
  regions: string[]
}

export interface DataIssue {
  id: string
  game_id?: number | null
  feature: string
  subject: string
  kind: 'missing' | 'disputed' | 'unverified'
  description: string
  evidence_id: string
}

export interface CoverageMatrix {
  features: string[]
  games: Array<{
    slug: string
    name: string
    support_tier: SupportTier
    generation: number
    version_group: string
    coverage_status: CoverageStatus
    has_facts: boolean
    features: Record<string, { status: CoverageStatus; note?: string }>
    counts: Record<CoverageStatus, number>
    issue_count: number
  }>
  global_issues: DataIssue[]
}

export type Mechanics = Record<string, number>

export interface Vocabulary {
  types: Array<{ slug: string; name: string }>
  stats: string[]
  damage_classes: DamageClass[]
  acquisition_methods: string[]
  learnset_methods: string[]
  evolution_triggers: string[]
  item_categories: string[]
  item_pockets: string[]
  egg_groups: string[]
  machine_kinds: string[]
  regions: string[]
  condition_ops: string[]
  availability_states: Availability[]
  coverage_statuses: CoverageStatus[]
  issue_kinds: string[]
  spoiler_levels: string[]
  verification_statuses: string[]
  mechanics: Mechanics
}

/* -- pokemon --------------------------------------------------------------------------------- */

export interface PokemonListRow {
  id: number
  slug: string
  name: string
  species_id: number
  is_default: number
  presence: 'present' | 'unknown'
  evidence_id: string
  types: string[]
}

export interface StatRow {
  stat: string
  base_stat: number
  effort: number
  evidence_id: string
}

export interface PokemonCard {
  form: {
    id: number
    slug: string
    name: string
    species_id: number
    species_slug: string
    species_name: string
    is_default: number
    height_dm: number | null
    weight_hg: number | null
    base_experience: number | null
    evidence_id: string
  }
  presence: { presence: string; evidence_id: string }
  species: {
    generation_id: number
    evolves_from_species_id: number | null
    evolution_chain_id: number | null
    gender_rate: number | null
    capture_rate: number | null
    base_happiness: number | null
    hatch_counter: number | null
    growth_rate: string | null
    is_baby: number
    is_legendary: number
    is_mythical: number
    evidence_id: string
  }
  types: Array<{ slot: number; type: string; evidence_id: string }>
  stats: StatRow[]
  abilities: Array<{ slot: number; ability: string; name: string; is_hidden: number; evidence_id: string }>
  abilities_note?: string
  egg_groups: string[]
  held_items: Array<{ item: string; name: string; rarity: number; evidence_id: string }>
  dex_numbers: Array<{ pokedex: string; number: number; evidence_id: string }>
  variants: Array<{ id: number; slug: string; form_name: string; is_default: number; is_mega: number; is_battle_only: number }>
  other_forms: Array<{ id: number; slug: string; name: string; presence: string | null }>
  included?: string[]
  acquisition?: AcquisitionData
  evolution?: EvolutionData
  learnset?: LearnsetData
}

export interface AcquisitionRoute {
  id: string
  method: string
  min_level: number | null
  max_level: number | null
  chance_percent: number | null
  availability: Availability
  prerequisites: Condition
  encounter_conditions: Condition | null
  verification_status: VerificationStatus
  note: string
  location: string | null
  location_name: string | null
  location_area: string | null
  location_area_name: string | null
  evidence_id: string
  encounter_rate?: { rate: number } | null
  derived?: Verdict
}

export interface AcquisitionData {
  form: { id: number; slug: string; name: string }
  routes: AcquisitionRoute[]
  route_counts: Record<string, number>
}

export interface EvolutionRule {
  id: number
  trigger: string
  conditions: Condition
  raw: Record<string, unknown>
  from_pokemon: string
  from_name: string
  to_pokemon: string
  to_name: string
  applicability: 'applies' | 'not-applicable' | 'unknown' | null
  reason: string | null
  verification_status: VerificationStatus | null
  evidence_id: string
  derived?: Verdict
}

export interface EvolutionData {
  form: { id: number; slug: string; name: string }
  outgoing: EvolutionRule[]
  incoming: EvolutionRule[]
}

export interface EvolutionChain {
  chain_id: number | null
  form: { id: number; slug: string; name: string }
  nodes: Array<{
    form_id: number
    slug: string
    name: string
    species_id: number
    is_default: number
    is_baby: number
    presence: string | null
    types: string[]
  }>
  edges: Array<{
    id: number
    trigger: string
    conditions: Condition
    from_pokemon: string
    to_pokemon: string
    applicability: 'applies' | 'not-applicable' | 'unknown' | null
    reason: string | null
  }>
  applicability_counts: Record<string, number>
}

export interface Access {
  status: DerivedStatus
  reason?: string
  item?: string
  reusable?: number | null
  note?: string
  routes?: Array<Verdict & { kind: string; id: string; method?: string; location?: string | null; name?: string; price?: number | null }>
}

export interface LearnsetMove {
  method: string
  level: number
  ord: number | null
  move_id: number
  move: string
  move_name: string
  type: string
  damage_class: DamageClass
  power: number | null
  accuracy: number | null
  pp: number | null
  priority: number
  machine_kind: string | null
  machine_number: number | null
  machine_item: string | null
  evidence_id: string
  eligible?: boolean
  access?: Access
}

export interface LearnsetData {
  form: { id: number; slug: string; name: string }
  moves: LearnsetMove[]
  method_counts: Record<string, number>
  machine_rules: Record<string, number | null>
  access_counts?: Record<string, number>
}

/* -- moves, items, abilities, natures --------------------------------------------------------- */

export interface MoveListRow {
  id: number
  slug: string
  name: string
  type: string
  damage_class: DamageClass
  power: number | null
  accuracy: number | null
  pp: number | null
  priority: number
  evidence_id: string
}

export interface MoveDetail extends MoveListRow {
  generation_id: number
  target: string
  effect_chance: number | null
  short_effect: string | null
  effect: string | null
  effect_wording: string | null
  flavor_text: { text: string; evidence_id: string } | null
  meta: Record<string, number | string | null> | null
  flags: string[]
  machine: { kind: string; machine_number: number; item: string; evidence_id: string } | null
  learner_count: number
}

export interface ItemListRow {
  id: number
  slug: string
  name: string
  category: string
  pocket: string
  purchase_price: number | null
  sell_price: number | null
  price_provenance: 'version-group' | 'default-cost' | 'unknown'
  evidence_id: string
}

export interface ItemDetail extends ItemListRow {
  fling_power: number | null
  flavor_text: string | null
  effect: { short_effect: string; effect: string; wording: string; evidence_id: string } | null
  attributes: string[]
  holdable: boolean
  machine: { kind: string; machine_number: number; move: string; move_name: string; reusable: number | null } | null
  acquisition: AcquisitionRoute[]
  shops: Array<{ id: string; name: string; location: string | null; price: number | null; prerequisites: Condition; derived?: Verdict }>
  held_by: Array<{ pokemon: string; name: string; rarity: number }>
}

export interface AbilityListRow {
  id: number
  slug: string
  name: string
  generation_id: number
  evidence_id: string
}

export interface AbilityDetail extends AbilityListRow {
  effect: { short_effect: string; effect: string; wording: string; evidence_id: string } | null
  flavor_text: { text: string; evidence_id: string } | null
  changes: Array<{ changed_in: string; effect: string }>
  pokemon: Array<{ id: number; slug: string; name: string; slot: number; is_hidden: number }>
}

export interface Nature {
  id: number
  slug: string
  name: string
  increased_stat: string
  decreased_stat: string
  likes_flavor: string | null
  hates_flavor: string | null
  neutral: boolean
  modifiers?: Record<string, number>
  evidence_id: string
}

export interface TypeRow {
  id: number
  slug: string
  name: string
  generation_id: number
  evidence_id: string
}

export interface TypeChart {
  generation: number
  pairs: Array<{ attack: string; defense: string; damage_factor: number; evidence_id: string }>
}

export interface Matchup {
  generation: number
  attack: string
  defenses: string[]
  multiplier: number
  parts: Array<{ defense_type_id: number; damage_factor: number; evidence_id: string }>
}

/* -- progression ------------------------------------------------------------------------------ */

export interface Milestone {
  id: string
  slug: string
  name: string
  ord: number
  kind: string
  location: string | null
  prerequisites: Condition
  spoiler_level: 'none' | 'hint' | 'full'
  verification_status: VerificationStatus
  evidence_id: string
}

export interface BattleSummary {
  id: string
  name: string
  trainer_class: string
  milestone_id: string | null
  location: string | null
  prize_money: number | null
  verification_status: VerificationStatus
  evidence_id: string
}

export interface BattleDetail extends BattleSummary {
  party: Array<{
    slot: number
    pokemon: string
    name: string
    level: number
    gender: string | null
    ability: string | null
    held_item: string | null
    moves: string[] | null
    types: string[]
    verification_status: VerificationStatus
  }>
}

export interface TutorsData {
  tutors: Array<{ id: string; move: string; move_name: string; location: string | null; cost_item: string | null; cost_amount: number | null }>
  eligible_learnset_rows: number
}

/* -- analysis services ------------------------------------------------------------------------ */

export interface TypeMultiplierRow {
  attack: string
  multiplier: number
  ability_multiplier?: number
  ability_applied?: Array<{ applies_to: string; type: string | null; damage_factor: number; note: string; evidence_id: string }>
}

export interface DefenceLayer {
  by_type?: TypeMultiplierRow[]
  immunities: string[]
  resistances: string[]
  weaknesses: string[]
}

export interface DefenceProfile {
  generation: number
  types: string[]
  basic: DefenceLayer & { by_type: TypeMultiplierRow[] }
  ability?: {
    ability: string | null
    modifiers: Array<{ applies_to: string; type: string | null; damage_factor: number; note: string; evidence_id: string }>
    note?: string
  } & Partial<DefenceLayer>
}

export interface OffensiveCoverage {
  generation: number
  attacking_moves: Array<{ pokemon: string; move: string; slug: string; name: string; type: string; damage_class: DamageClass; power: number | null }>
  excluded_moves: Array<{ pokemon: string; move: string; reason: string; type?: string }>
  by_type: Array<{ defense: string; multiplier: number; moves: Array<{ pokemon: string; move: string; type: string }> }>
  super_effective_against: string[]
  neutral_at_best_against: string[]
  resisted_against: string[]
  no_effect_against: string[]
}

export interface TeamAnalysis {
  team: Array<{
    pokemon: string
    nickname?: string | null
    level: number | null
    types: string[]
    ability?: string | null
    nature?: string | null
    held_item?: string | null
    defence: DefenceProfile | null
    note?: string
  }>
  coverage: OffensiveCoverage | null
  mechanics: Mechanics
  warnings: string[]
}

export interface ReachabilityResult {
  pokemon: Array<{ pokemon: string; routes?: AcquisitionRoute[]; counts?: Record<string, number>; data?: null; assumptions: string[] }>
  items: Array<{
    item: string
    routes?: AcquisitionRoute[]
    shops?: Array<{ id: string; name: string; price: number | null; derived: Verdict }>
    counts?: Record<string, number>
    data?: null
    assumptions: string[]
  }>
  closed_world: string[]
}

export interface BossPreparation {
  battle: BattleDetail
  threats: Array<{
    slot: number
    pokemon: string
    name: string
    level: number
    types: string[]
    ability: string | null
    held_item: string | null
    moves: string[]
    their_move_types: Array<{ move: string; type: string; power: number | null; damage_class: DamageClass; note?: string }>
    our_best_move: { pokemon: string; move: string; multiplier: number } | null
    defence: DefenceProfile
    verification_status: VerificationStatus
  }>
  team: Array<{
    pokemon: string
    level: number | null
    types: string[]
    ability?: string | null
    defence?: DefenceProfile
    takes_super_effective?: Array<{ move: string; type: string; multiplier: number; from: string[] }>
    note?: string
  }>
  coverage: OffensiveCoverage | null
  levels: { yours: number[]; theirs: number[]; their_highest: number | null; your_lowest: number | null; note: string }
  resources: {
    shop_items: Array<{ shop_id: string; name: string; location: string | null; item: string; item_name: string; price: number | null; derived: Verdict }>
    counts: Record<string, number>
  }
}

export interface MoveAccessResult extends LearnsetData {
  pokemon: string
  member: string | null
  access_counts: Record<string, number>
}

export interface EvolutionRequirements {
  pokemon: string
  member: string | null
  outgoing: EvolutionRule[]
  incoming: EvolutionRule[]
}

export interface Health {
  status: string
  snapshot_id: string
  database: string
}

// -- Ask Rotom ---------------------------------------------------------------------------------

export interface ChatLimits {
  max_message_chars: number
  max_history_turns: number
  max_tool_calls: number
  deadline_s: number
}

export interface ChatStatus {
  enabled: boolean
  provider: string
  model: string | null
  research_enabled: boolean
  reason: string
  limits: ChatLimits
}

export interface ChatFact {
  claim: string
  evidence_id: string
  tool: string
}

export interface ChatAssumption {
  text: string
  because: 'missing_data' | 'unrecorded_progress' | 'untracked_mechanic' | 'open_world' | 'spoiler_filter' | 'unreviewed_web'
}

/** `unavailable` is absent by construction: the server never derives it, so advice cannot claim it. */
export type RecommendationStatus = 'reachable' | 'locked' | 'unknown'

export interface ChatRecommendation {
  text: string
  rationale: string
  status: RecommendationStatus
  subject?: string
}

export interface ChatCardRow {
  label: string
  value: string
  evidence_id?: string
}

export interface ChatCard {
  kind: string
  title: string
  subject?: string
  tool: string
  rows: ChatCardRow[]
}

/** Proposed only. `applied` is forced false by the server; the player confirms in the interface. */
export interface ChatAction {
  kind: 'pin_plan' | 'add_team_member' | 'set_member_level' | 'set_member_moves' | 'mark_milestone' | 'set_current_location'
  label: string
  payload: Record<string, unknown>
  applied: false
}

export interface ChatReference {
  kind: 'evidence' | 'web'
  id: string
  url?: string
  title?: string
  review_status?: string
}

export interface ChatAnswer {
  prose: string
  abstained: boolean
  abstain_reason?: string
  facts: ChatFact[]
  assumptions: ChatAssumption[]
  recommendations: ChatRecommendation[]
  cards: ChatCard[]
  actions: ChatAction[]
  references: ChatReference[]
  tools_used: { tool: string; arguments: Record<string, unknown> }[]
  spoiler_level: string
  limits_reached: string[]
  verification_notes: string[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}
