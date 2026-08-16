import { useState, useEffect } from 'react'

function DealCard({ product, onClick }) {
  const {
    title,
    image_url,
    price,
    original_price,
    rating,
    review_count,
    discount_percent,
  } = product

  const hasDiscount = original_price && original_price > price
  const savings = hasDiscount ? (original_price - price).toFixed(2) : '0.00'

  return (
    <div
      onClick={() => onClick(product)}
      className="bg-[#1a2332] rounded-lg overflow-hidden border border-gray-700 hover:border-[#ff9900] hover:shadow-lg hover:shadow-[#ff9900]/10 transition-all cursor-pointer group"
    >
      {/* Discount Badge + Image */}
      <div className="relative">
        <div className="aspect-square bg-white p-4">
          {image_url ? (
            <img
              src={image_url}
              alt={title}
              className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
        </div>
        {/* Discount Badge */}
        <div className="absolute top-2 left-2 bg-red-600 text-white text-sm font-bold px-2.5 py-1 rounded-md">
          -{discount_percent || 0}%
        </div>
        {/* Savings Badge */}
        <div className="absolute bottom-2 right-2 bg-green-600 text-white text-xs font-bold px-2 py-1 rounded">
          Save S${savings}
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-2">
        <h3 className="text-sm text-white font-medium line-clamp-2 leading-tight group-hover:text-[#ff9900] transition-colors">
          {title || 'Product'}
        </h3>

        {/* Rating */}
        <div className="flex items-center gap-1">
          <div className="flex">
            {Array.from({ length: 5 }).map((_, i) => (
              <span
                key={i}
                className={`text-sm ${
                  i < Math.round(rating || 0) ? 'text-[#ff9900]' : 'text-gray-600'
                }`}
              >
                ★
              </span>
            ))}
          </div>
          <span className="text-xs text-gray-400">
            ({review_count?.toLocaleString() || 0})
          </span>
        </div>

        {/* Price */}
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-white">
            S${price ? price.toFixed(2) : '0.00'}
          </span>
          {hasDiscount && (
            <span className="text-sm text-gray-400 line-through">
              S${original_price.toFixed(2)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function DealsSection({ apiUrl, onProductClick }) {
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [minDiscount, setMinDiscount] = useState(20)

  useEffect(() => {
    const fetchDeals = async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `${apiUrl}/api/deals?min_discount=${minDiscount}`
        )
        if (res.ok) {
          const data = await res.json()
          setDeals(data)
        }
      } catch (err) {
        console.error('Failed to fetch deals:', err)
      }
      setLoading(false)
    }

    fetchDeals()
  }, [apiUrl, minDiscount])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            🔥 Hot Deals
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Products with the biggest discounts
          </p>
        </div>

        {/* Discount Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Min discount:</span>
          <div className="flex gap-1">
            {[20, 30, 50].map((d) => (
              <button
                key={d}
                onClick={() => setMinDiscount(d)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  minDiscount === d
                    ? 'bg-[#ff9900] text-black'
                    : 'bg-[#1a2332] text-gray-400 border border-gray-600 hover:text-white'
                }`}
              >
                {d}%
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Deals Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-12 h-12 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin" />
        </div>
      ) : deals.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {deals.map((product) => (
            <DealCard
              key={product.asin}
              product={product}
              onClick={onProductClick}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
          </svg>
          <p className="text-lg">No deals found</p>
          <p className="text-sm text-gray-500 mt-1">
            Try lowering the minimum discount threshold
          </p>
        </div>
      )}
    </div>
  )
}