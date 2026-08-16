import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'

export default function ProductDetail({ product, onBack, apiUrl }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `${apiUrl}/api/products/${product.asin}/history?days=${days}`
        )
        if (res.ok) {
          const data = await res.json()
          setHistory(data)
        }
      } catch (err) {
        console.error('Failed to fetch price history:', err)
      }
      setLoading(false)
    }

    fetchHistory()
  }, [product.asin, apiUrl, days])

  const {
    title,
    image_url,
    price,
    original_price,
    rating,
    review_count,
    description,
    category,
    url,
  } = product

  const hasDiscount = original_price && original_price > price
  const discount = hasDiscount
    ? Math.round(((original_price - price) / original_price) * 100)
    : 0

  // Calculate price stats
  const pricePoints = history.map((h) => h.price).filter(Boolean)
  const minPrice = pricePoints.length > 0 ? Math.min(...pricePoints) : price
  const maxPrice = pricePoints.length > 0 ? Math.max(...pricePoints) : price
  const avgPrice =
    pricePoints.length > 0
      ? pricePoints.reduce((a, b) => a + b, 0) / pricePoints.length
      : price

  const chartData = history.map((h) => ({
    date: h.date,
    price: h.price,
  }))

  const isCurrentLowest = price <= minPrice

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-gray-400 hover:text-[#ff9900] transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        <span>Back to Products</span>
      </button>

      {/* Product Info */}
      <div className="bg-[#1a2332] rounded-xl border border-gray-700 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Image */}
          <div className="flex items-center justify-center">
            <div className="bg-white rounded-lg p-4 w-full max-w-sm aspect-square">
              {image_url ? (
                <img
                  src={image_url}
                  alt={title}
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-20 w-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              )}
            </div>
          </div>

          {/* Details */}
          <div className="md:col-span-2 space-y-4">
            <h1 className="text-xl font-bold text-white leading-tight">
              {title}
            </h1>

            {category && (
              <span className="inline-block bg-[#232f3e] text-gray-300 text-xs px-3 py-1 rounded-full">
                {category}
              </span>
            )}

            {/* Rating */}
            <div className="flex items-center gap-2">
              <div className="flex">
                {Array.from({ length: 5 }).map((_, i) => (
                  <span
                    key={i}
                    className={i < Math.round(rating || 0) ? 'text-[#ff9900]' : 'text-gray-600'}
                  >
                    ★
                  </span>
                ))}
              </div>
              <span className="text-sm text-gray-400">
                {rating ? rating.toFixed(1) : 'No rating'} ({review_count?.toLocaleString() || 0} reviews)
              </span>
            </div>

            {/* Price */}
            <div className="space-y-1">
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-bold text-white">
                  S${price ? price.toFixed(2) : '0.00'}
                </span>
                {hasDiscount && (
                  <span className="text-lg text-gray-400 line-through">
                    S${original_price.toFixed(2)}
                  </span>
                )}
                {discount > 0 && (
                  <span className="text-sm font-bold text-red-400">
                    -{discount}% OFF
                  </span>
                )}
              </div>
              {isCurrentLowest && (
                <span className="inline-flex items-center gap-1 text-green-400 text-sm font-medium">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Lowest price in {days} days!
                </span>
              )}
            </div>

            {/* Price Stats */}
            <div className="grid grid-cols-3 gap-4 pt-2">
              <div className="bg-[#131921] rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Lowest</p>
                <p className="text-sm font-bold text-green-400">
                  S${minPrice ? minPrice.toFixed(2) : '0.00'}
                </p>
              </div>
              <div className="bg-[#131921] rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Average</p>
                <p className="text-sm font-bold text-white">
                  S${avgPrice ? avgPrice.toFixed(2) : '0.00'}
                </p>
              </div>
              <div className="bg-[#131921] rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Highest</p>
                <p className="text-sm font-bold text-red-400">
                  S${maxPrice ? maxPrice.toFixed(2) : '0.00'}
                </p>
              </div>
            </div>

            {/* View on Amazon */}
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#ff9900] hover:bg-[#e68a00] text-black font-medium rounded-lg transition-colors"
              >
                View on Amazon.sg
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Price History Chart */}
      <div className="bg-[#1a2332] rounded-xl border border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-white">Price History</h2>
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  days === d
                    ? 'bg-[#ff9900] text-black'
                    : 'bg-[#131921] text-gray-400 hover:text-white'
                }`}
              >
                {d}D
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-10 h-10 border-4 border-[#ff9900]/20 border-t-[#ff9900] rounded-full animate-spin" />
          </div>
        ) : chartData.length > 0 ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff9900" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ff9900" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="date"
                  stroke="#9ca3af"
                  fontSize={12}
                  tickFormatter={(val) => {
                    const date = new Date(val)
                    return `${date.getMonth() + 1}/${date.getDate()}`
                  }}
                />
                <YAxis
                  stroke="#9ca3af"
                  fontSize={12}
                  tickFormatter={(val) => `S$${val}`}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a2332',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                  formatter={(value) => [`S$${value.toFixed(2)}`, 'Price']}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke="#ff9900"
                  strokeWidth={2}
                  fill="url(#priceGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex items-center justify-center h-64 text-gray-400">
            <p>No price history available</p>
          </div>
        )}
      </div>

      {/* Description */}
      {description && (
        <div className="bg-[#1a2332] rounded-xl border border-gray-700 p-6">
          <h2 className="text-lg font-bold text-white mb-4">Description</h2>
          <p className="text-gray-300 leading-relaxed whitespace-pre-line">
            {description}
          </p>
        </div>
      )}
    </div>
  )
}