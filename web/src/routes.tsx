import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Shell } from './App'
import { GameSelector } from './features/games/GameSelector'
import { PlaythroughsScreen } from './features/playthroughs/PlaythroughsScreen'
import { DexSearch } from './features/pokedex/DexSearch'
import { PokemonDetail } from './features/pokedex/PokemonDetail'
import { MovesScreen } from './features/moves/MovesScreen'
import { ItemsScreen } from './features/items/ItemsScreen'
import { ToolsScreen } from './features/tools/ToolsScreen'
import { TeamScreen } from './features/team/TeamScreen'
import { JourneyScreen } from './features/journey/JourneyScreen'
import { Landing } from './features/games/Landing'
import { AskRotomScreen } from './features/chat/AskRotomScreen'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <Landing /> },
      { path: 'games', element: <GameSelector /> },
      { path: 'playthroughs', element: <PlaythroughsScreen /> },
      {
        path: 'g/:game',
        children: [
          { index: true, element: <Navigate to="journey" replace /> },
          { path: 'journey', element: <JourneyScreen /> },
          { path: 'dex', element: <DexSearch /> },
          { path: 'dex/:pokemon', element: <PokemonDetail /> },
          { path: 'team', element: <TeamScreen /> },
          { path: 'moves', element: <MovesScreen /> },
          { path: 'items', element: <ItemsScreen /> },
          { path: 'tools', element: <ToolsScreen /> },
          { path: 'ask', element: <AskRotomScreen /> },
        ],
      },
    ],
  },
])
