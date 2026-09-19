import { useState, useEffect, useMemo } from 'react'

const LOCAL_DATA_URL = '/products.json'
const REMOTE_DATA_URL =
  'https://raw.githubusercontent.com/Kytosyn/amazon-sg-price-tracker/master/data/products.json'

const PLATFORMS = ['all', 'Shopee', 'Lazada', 'Amazon.sg']
const TYPE_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'ssd', label: 'SSD' },
  { id: 'hdd', label: 'HDD' },
]

const platformColors = {
  Shopee: 'bg-[#EE4D2D]',
  Lazada: 'bg-[#0F146D]',
  'Amazon.sg': 'bg-[#FF9900]',
}

function Chip({ active, onClick, children, title }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`flex-shrink-0 min-h-[44px] px-3.5 py-2 rounded-full text-xs sm:text-sm font-medium transition-colors whitespace-nowrap inline-flex items-center ${
        active
          ? 'bg-[#ff9900] text-black'
          : 'bg-white/5 text-slate-200 border border-white/10 hover:border-[#ff9900]/60 hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}

function DiskPriceCard({ product }) {
  const costPerTb = Number(product.cost_per_tb)
  const capacityTb = Number(product.capacity_tb)
  const price = Number(product.price)
  const original = Number(product.original_price)

  return (
    <a
      href={product.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white/5 rounded-lg px-3 py-2.5 border border-white/10 hover:border-[#4ade80]/50 hover:bg-white/10 transition-all group"
    >
      <div className="flex items-start gap-2.5">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt=""
            className="w-14 h-14 object-cover rounded-md flex-shrink-0 bg-black/20"
            loading="lazy"
          />
        ) : (
          <div className="w-14 h-14 rounded-md flex-shrink-0 bg-white/5 border border-white/10" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span
              className={`text-[10px] text-white px-1.5 py-0.5 rounded ${
                platformColors[product.platform] || 'bg-gray-600'
              }`}
            >
              {product.platform}
            </span>
            <span className="text-[10px] font-medium text-slate-300 tracking-wide">
              {product.is_ssd ? 'SSD' : 'HDD'}
            </span>
            {Number.isFinite(capacityTb) && (
              <span className="text-[10px] text-slate-500">
                {capacityTb >= 1
                  ? `${capacityTb % 1 === 0 ? capacityTb.toFixed(0) : capacityTb.toFixed(1)} TB`
                  : `${Math.round(capacityTb * 1000)} GB`}
              </span>
            )}
          </div>
          <div className="text-sm font-medium leading-snug line-clamp-2 group-hover:text-[#4ade80] transition-colors">
            {product.title}
          </div>
          <div className="mt-1.5 flex items-baseline gap-2 flex-wrap">
            <span className="text-lg font-bold text-[#4ade80] tabular-nums">
              {Number.isFinite(costPerTb) ? `S$${costPerTb.toFixed(2)}` : '—'}/TB
            </span>
            <span className="text-xs text-slate-400 tabular-nums">
              {Number.isFinite(price) ? `S$${price.toFixed(2)}` : ''}
              {Number.isFinite(original) && original > price ? (
                <span className="ml-1 line-through text-slate-600">
                  S${original.toFixed(2)}
                </span>
              ) : null}
            </span>
          </div>
        </div>
      </div>
    </a>
  )
}

function EmptyState({ kind, onRetry, onClearFilters }) {
  if (kind === 'error') {
    return (
      <div className="text-center py-16 px-4 rounded-xl border border-red-500/20 bg-red-500/5">
        <p className="text-base font-medium text-red-200">Couldn’t load prices</p>
        <p className="text-sm text-slate-400 mt-2 max-w-md mx-auto">
          The product feed didn’t load. Check your connection, then try again.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-[#ff9900] text-black hover:bg-[#ffb84d] transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  if (kind === 'filtered') {
    return (
      <div className="text-center py-16 px-4 rounded-xl border border-white/10 bg-white/[0.03]">
        <p className="text-base font-medium text-slate-200">No matches for these filters</p>
        <p className="text-sm text-slate-400 mt-2 max-w-md mx-auto">
          Try All / All Platforms, or clear filters. Platforms with a “soon” chip have no
          listings in the current feed yet.
        </p>
        <button
          type="button"
          onClick={onClearFilters}
          className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-white/10 text-white hover:bg-white/15 transition-colors"
        >
          Clear filters
        </button>
      </div>
    )
  }

  return (
    <div className="text-center py-16 px-4 rounded-xl border border-white/10 bg-white/[0.03]">
      <p className="text-base font-medium text-slate-200">No products yet</p>
      <p className="text-sm text-slate-400 mt-2 max-w-md mx-auto">
        GitHub Actions scrapes daily at 9 AM SGT. Hit Refresh after a successful run.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-[#ff9900] text-black hover:bg-[#ffb84d] transition-colors"
      >
        Refresh
      </button>
    </div>
  )
}

export default function DiskPrices() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [filter, setFilter] = useState('all')
  const [platform, setPlatform] = useState('all')
  const [sortBy, setSortBy] = useState('cost_per_tb')

  const fetchProducts = async () => {
    setLoading(true)
    setFetchError(null)
    const tryUrl = async (url) => {
      const res = await fetch(url, { cache: 'no-cache' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }
    try {
      // Prefer GitHub raw (freshest scrape). Fall back to Vercel build bundle.
      let data
      try {
        data = await tryUrl(REMOTE_DATA_URL)
      } catch {
        data = await tryUrl(LOCAL_DATA_URL)
      }
      const products = Array.isArray(data.products) ? data.products : []
      // If raw is empty but the build bundle has rows, use the bundle.
      if (products.length === 0) {
        try {
          const local = await tryUrl(LOCAL_DATA_URL)
          const localProducts = Array.isArray(local.products) ? local.products : []
          if (localProducts.length > 0) {
            data = local
          }
        } catch {
          /* keep remote/empty */
        }
      }
      setProducts(Array.isArray(data.products) ? data.products : [])
      setLastUpdated(data.lastUpdated || null)
    } catch (err) {
      console.error('Failed to fetch:', err)
      setProducts([])
      setLastUpdated(null)
      setFetchError(err?.message || 'fetch failed')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchProducts()
  }, [])

  const platformCounts = useMemo(() => {
    const counts = { all: products.length }
    for (const p of PLATFORMS) {
      if (p === 'all') continue
      counts[p] = products.filter((x) => x.platform === p).length
    }
    return counts
  }, [products])

  const typeCounts = useMemo(
    () => ({
      all: products.length,
      ssd: products.filter((p) => p.is_ssd).length,
      hdd: products.filter((p) => !p.is_ssd).length,
    }),
    [products]
  )

  const filteredProducts = useMemo(() => {
    let list = products
    if (filter === 'ssd') list = list.filter((p) => p.is_ssd)
    if (filter === 'hdd') list = list.filter((p) => !p.is_ssd)
    if (platform !== 'all') list = list.filter((p) => p.platform === platform)

    const sorted = [...list]
    if (sortBy === 'cost_per_tb') {
      sorted.sort((a, b) => (a.cost_per_tb ?? Infinity) - (b.cost_per_tb ?? Infinity))
    } else if (sortBy === 'price') {
      sorted.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity))
    } else if (sortBy === 'capacity') {
      sorted.sort((a, b) => (b.capacity_tb ?? 0) - (a.capacity_tb ?? 0))
    }
    return sorted
  }, [products, filter, platform, sortBy])

  const emptyKind = fetchError
    ? 'error'
    : products.length === 0
      ? 'none'
      : filteredProducts.length === 0
        ? 'filtered'
        : null

  const clearFilters = () => {
    setFilter('all')
    setPlatform('all')
    setSortBy('cost_per_tb')
  }

  return (
    <div className="min-h-screen bg-[#131921] text-white">
      <header className="bg-[#232f3e] border-b border-gray-700 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-bold truncate">DiskPrices Singapore</h1>
            <p className="text-[11px] text-slate-400 truncate">
              Best S$/TB
              {livePlatforms.length > 0
                ? ` across ${livePlatforms.join(' · ')}`
                : ' — loading platforms…'}
              {pendingPlatforms.length > 0
                ? ` · ${pendingPlatforms.join(' & ')} soon`
                : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={fetchProducts}
            disabled={loading}
            className="flex-shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium bg-[#ff9900] text-black hover:bg-[#ffb84d] disabled:opacity-60 transition-colors"
          >
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-5">
        {/* Compact stats */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-4">
          {[
            { label: 'Total', value: typeCounts.all },
            { label: 'SSD', value: typeCounts.ssd },
            { label: 'HDD', value: typeCounts.hdd },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-white/5 rounded-lg px-2 py-2.5 text-center border border-white/10"
            >
              <div className="text-xl sm:text-2xl font-bold text-[#4ade80] tabular-nums">
                {loading && !fetchError ? '—' : s.value}
              </div>
              <div className="text-[10px] sm:text-xs text-slate-400 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="space-y-3 mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Type</div>
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
              {TYPE_FILTERS.map((f) => (
                <Chip
                  key={f.id}
                  active={filter === f.id}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                  {!loading && (
                    <span className="ml-1 opacity-70 tabular-nums">
                      {typeCounts[f.id] ?? 0}
                    </span>
                  )}
                </Chip>
              ))}
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
              Platform
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
              {PLATFORMS.map((p) => {
                const count = platformCounts[p] ?? 0
                const soon = p !== 'all' && !loading && count === 0
                return (
                  <Chip
                    key={p}
                    active={platform === p}
                    onClick={() => setPlatform(p)}
                    title={soon ? 'No listings yet for this platform' : undefined}
                  >
                    {p === 'all' ? 'All' : p}
                    {!loading && (
                      <span className="ml-1 opacity-70 tabular-nums">{count}</span>
                    )}
                    {soon ? (
                      <span className="ml-1 text-[10px] opacity-60">soon</span>
                    ) : null}
                  </Chip>
                )
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <label
                htmlFor="sort-by"
                className="text-[10px] uppercase tracking-wider text-slate-500 flex-shrink-0"
              >
                Sort
              </label>
              <select
                id="sort-by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="min-h-[44px] px-3 py-2 rounded-lg text-sm bg-white/5 text-white border border-white/10 focus:outline-none focus:border-[#ff9900]"
              >
                <option value="cost_per_tb">S$/TB (best first)</option>
                <option value="price">Price (low → high)</option>
                <option value="capacity">Capacity (high → low)</option>
              </select>
            </div>
            {!loading && !fetchError && products.length > 0 && (
              <p className="text-xs text-slate-500 tabular-nums">
                Showing {filteredProducts.length} of {products.length}
              </p>
            )}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-10 h-10 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin" />
          </div>
        ) : emptyKind ? (
          <EmptyState
            kind={emptyKind}
            onRetry={fetchProducts}
            onClearFilters={clearFilters}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2.5">
            {filteredProducts.map((product) => (
              <DiskPriceCard
                key={product.id || `${product.platform}-${product.url}`}
                product={product}
              />
            ))}
          </div>
        )}

        {lastUpdated && !fetchError && (
          <div className="mt-6 text-center text-[11px] text-slate-500">
            Last updated:{' '}
            {new Date(lastUpdated).toLocaleString('en-SG', {
              timeZone: 'Asia/Singapore',
            })}{' '}
            SGT
          </div>
        )}
      </main>
    </div>
  )
}
