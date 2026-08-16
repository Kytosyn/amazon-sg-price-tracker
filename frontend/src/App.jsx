import { useState, useEffect } from 'react'
import ProductGrid from './components/ProductGrid'
import ProductDetail from './components/ProductDetail'
import SearchBar from './components/SearchBar'
import CategoryFilter from './components/CategoryFilter'
import DealsSection from './components/DealsSection'
import StatsBar from './components/StatsBar'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [view, setView] = useState('home') // home, search, deals, product
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetchStats()
    fetchCategories()
    fetchProducts()
  }, [selectedCategory])

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/stats`)
      if (res.ok) setStats(await res.json())
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  const fetchCategories = async () => {
    try {
      const res = await fetch(`${API_URL}/api/categories`)
      if (res.ok) setCategories(await res.json())
    } catch (err) {
      console.error('Failed to fetch categories:', err)
    }
  }

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '50' })
      if (selectedCategory) params.set('category', selectedCategory)
      
      const res = await fetch(`${API_URL}/api/products?${params}`)
      if (res.ok) setProducts(await res.json())
    } catch (err) {
      console.error('Failed to fetch products:', err)
    }
    setLoading(false)
  }

  const handleSearch = async (query) => {
    setSearchQuery(query)
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}`)
      if (res.ok) {
        setTimeout(fetchProducts, 5000) // Wait for scraping
      }
    } catch (err) {
      console.error('Search failed:', err)
    }
    setLoading(false)
    setView('home')
  }

  const handleProductClick = (product) => {
    setSelectedProduct(product)
    setView('product')
  }

  const handleBack = () => {
    setView('home')
    setSelectedProduct(null)
  }

  return (
    <div className="min-h-screen bg-[#131921]">
      {/* Header */}
      <header className="bg-[#232f3e] border-b border-gray-700 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center gap-4">
            <button onClick={handleBack} className="flex items-center gap-2">
              <span className="text-2xl">🛒</span>
              <span className="text-xl font-bold text-white">Amazon.sg Tracker</span>
            </button>
            
            <SearchBar onSearch={handleSearch} />
            
            <div className="flex gap-2 ml-auto">
              <button
                onClick={() => { setView('home'); fetchProducts() }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  view === 'home' ? 'bg-[#ff9900] text-black' : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
              >
                Products
              </button>
              <button
                onClick={() => setView('deals')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  view === 'deals' ? 'bg-[#ff9900] text-black' : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
              >
                🔥 Deals
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      {stats && <StatsBar stats={stats} />}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {view === 'home' && (
          <>
            <CategoryFilter
              categories={categories}
              selected={selectedCategory}
              onSelect={(cat) => { setSelectedCategory(cat); fetchProducts() }}
            />
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-12 h-12 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin" />
              </div>
            ) : (
              <ProductGrid products={products} onProductClick={handleProductClick} />
            )}
          </>
        )}

        {view === 'product' && selectedProduct && (
          <ProductDetail product={selectedProduct} onBack={handleBack} apiUrl={API_URL} />
        )}

        {view === 'deals' && (
          <DealsSection apiUrl={API_URL} onProductClick={handleProductClick} />
        )}
      </main>
    </div>
  )
}
