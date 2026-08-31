import LayerToggle from '../components/map/LayerToggle'
import MineMap from '../components/map/MineMap'

export default function MapPage() {
  return (
    <div className="-m-6 flex h-[calc(100vh-4rem)] overflow-hidden">
      <LayerToggle />
      <MineMap />
    </div>
  )
}
