import { useState, useEffect } from 'react'
import DiskPrices from './components/DiskPrices'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    setLoaded(true)
  }, [])

  if (!loaded) {
    return (
      <div className="min-h-screen bg-[#131921] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-[#ff9900] text-sm tracking-widest uppercase">Loading...</p>
        </div>
      </div>
    )
  }

  return <DiskPrices />
}

export default App
