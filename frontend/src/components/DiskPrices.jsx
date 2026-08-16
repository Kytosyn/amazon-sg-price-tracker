import { useState, useEffect } from 'react'

const DATA_URL = 'https://raw.githubusercontent.com/Kytosyn/amazon-sg-price-tracker/master/data/products.json'

function DiskPriceCard({ product }) {
  const platformColors = {
    'Shopee': 'bg-[#EE4D2D]',
    'Lazada': 'bg-[#0F146D]',
    'Amazon.sg': 'bg-[#FF9900]',
  }

  return (
    <a
      href={product.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white/5 rounded-xl p-4 border border-white/10 hover:border-[#4ade80]/50 hover:bg-white/10 transition-all group"
    >
      <div className="flex items-start gap-3">
        {product.image_url && (
          <img
            src={product.image_url}
            alt={product.title}
            className="w-16 h-16 object-cover rounded-lg"
            loading="lazy"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] text-white px-1.5 py-0.5 rounded ${platformColors[product.platform] || 'bg-gray-600'}`}>
              {product.platform}
            </span>
            <span className="text-[10px] text-slate-400">
              {product.is_ssd ? 'SSD' : 'HDD'}
            </span>
          </div>
          <div className="text-sm font-medium truncate group-hover:text-[#4ade80] transition-colors">
            {product.title}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-lg font-bold text-[#4ade80]">
              S${product.price.toFixed(2)}
            </span>
            {product.original_price > product.price && (
              <span className="text-xs text-slate-500 line-through">
                S${product.original_price.toFixed(2)}
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {product.capacity_tb.toFixed(1)}TB · S${product.cost_per_tb.toFixed(2)}/TB
          </div>
        </div>
      </div>
    </a>
  )
}

export default function DiskPrices() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [filter, setFilter] = useState('all')
  const [platform, setPlatform] = useState('all')
  const [sortBy, setSortBy] = useState('cost_per_tb')

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const res = await fetch(DATA_URL)
      if (res.ok) {
        const data = await res.json()
        setProducts(data.products || [])
        setLastUpdated(data.lastUpdated || null)
      }
    } catch (err) {
      console.error('Failed to fetch:', err)
    }
    setLoading(false)
  }

  // Filter products
  let filteredProducts = products
  if (filter === 'ssd') filteredProducts = filteredProducts.filter(p => p.is_ssd)
  if (filter === 'hdd') filteredProducts = filteredProducts.filter(p => !p.is_ssd)
  if (platform !== 'all') filteredProducts = filteredProducts.filter(p => p.platform === platform)

  // Sort products
  if (sortBy === 'cost_per_tb') {
    filteredProducts.sort((a, b) => a.cost_per_tb - b.cost_per_tb)
  } else if (sortBy === 'price') {
    filteredProducts.sort((a, b) => a.price - b.price)
  } else if (sortBy === 'capacity') {
    filteredProducts.sort((a, b) => b.capacity_tb - a.capacity_tb)
  }

  const stats = {
    total: products.length,
    ssd: products.filter(p => p.is_ssd).length,
    hdd: products.filter(p => !p.is_ssd).length,
  }

  return (
    <div className="min-h-screen bg-[#131921] text-white">
      <header className="bg-[#232f3e] border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-2xl">💾</span>
              <span className="text-xl font-bold">DiskPrices Singapore</span>
            </div>
            <button
              onClick={fetchProducts}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-[#ff9900] text-black hover:bg-[#ffb84d] transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
            <div className="text-2xl font-bold text-[#4ade80]">{stats.total}</div>
            <div className="text-xs text-slate-400 mt-1">Total Products</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
            <div className="text-2xl font-bold text-[#4ade80]">{stats.ssd}</div>
            <div className="text-xs text-slate-400 mt-1">SSDs</div>
          </div>
          <div className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
            <div className="text-2xl font-bold text-[#4ade80]">{stats.hdd}</div>
            <div className="text-xs text-slate-400 mt-1">HDDs</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-6">
          <div className="flex gap-2">
            {['all', 'ssd', 'hdd'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  filter === f ? 'bg-[#ff9900] text-black' : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
              >
                {f === 'all' ? 'All' : f.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            {['all', 'Shopee', 'Lazada', 'Amazon.sg'].map((p) => (
              <button
                key={p}
                onClick={() => setPlatform(p)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  platform === p ? 'bg-[#ff9900] text-black' : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
              >
                {p === 'all' ? 'All Platforms' : p}
              </button>
            ))}
          </div>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-4 py-2 rounded-lg text-sm bg-gray-700 text-white border-0"
          >
            <option value="cost_per_tb">Sort by: Cost/TB</option>
            <option value="price">Sort by: Price</option>
            <option value="capacity">Sort by: Capacity</option>
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-12 h-12 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredProducts.map((product) => (
              <DiskPriceCard key={product.id} product={product} />
            ))}
          </div>
        )}

        {!loading && filteredProducts.length === 0 && (
          <div className="text-center py-20 text-slate-400">
            <p>No products found.</p>
            <p className="text-sm mt-2">GitHub Actions scrapes daily at 9 AM SGT.</p>
            <p className="text-sm">Check back soon or click Refresh.</p>
          </div>
        )}

        {lastUpdated && (
          <div className="mt-8 text-center text-xs text-slate-500">
            Last updated: {new Date(lastUpdated).toLocaleString()}
          </div>
        )}
      </main>
    </div>
  )
}
