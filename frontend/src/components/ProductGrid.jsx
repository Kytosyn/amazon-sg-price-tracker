function StarRating({ rating, reviewCount }) {
  const fullStars = Math.floor(rating)
  const hasHalfStar = rating - fullStars >= 0.5
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0)

  return (
    <div className="flex items-center gap-1">
      <div className="flex">
        {Array.from({ length: fullStars }).map((_, i) => (
          <span key={`full-${i}`} className="text-[#ff9900]">★</span>
        ))}
        {hasHalfStar && <span className="text-[#ff9900]">★</span>}
        {Array.from({ length: emptyStars }).map((_, i) => (
          <span key={`empty-${i}`} className="text-gray-600">★</span>
        ))}
      </div>
      <span className="text-sm text-gray-400 ml-1">
        {rating > 0 ? rating.toFixed(1) : 'No rating'}
      </span>
      {reviewCount > 0 && (
        <span className="text-xs text-gray-500">({reviewCount.toLocaleString()})</span>
      )}
    </div>
  )
}

function ProductCard({ product, onClick }) {
  const {
    asin,
    title,
    image_url,
    price,
    original_price,
    rating,
    review_count,
    discount_percent,
  } = product

  const hasDiscount = original_price && original_price > price

  return (
    <div
      onClick={() => onClick(product)}
      className="bg-[#1a2332] rounded-lg overflow-hidden border border-gray-700 hover:border-[#ff9900] hover:shadow-lg hover:shadow-[#ff9900]/10 transition-all cursor-pointer group"
    >
      {/* Image Container */}
      <div className="relative aspect-square bg-white p-4 overflow-hidden">
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
        {discount_percent > 0 && (
          <div className="absolute top-2 left-2 bg-red-600 text-white text-xs font-bold px-2 py-1 rounded">
            -{discount_percent}%
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4 space-y-2">
        {/* Title */}
        <h3 className="text-sm text-white font-medium line-clamp-2 leading-tight group-hover:text-[#ff9900] transition-colors">
          {title || 'Product'}
        </h3>

        {/* Rating */}
        <StarRating rating={rating || 0} reviewCount={review_count || 0} />

        {/* Price */}
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold text-white">
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

export default function ProductGrid({ products, onProductClick }) {
  if (!products || products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
        <p className="text-lg">No products found</p>
        <p className="text-sm text-gray-500 mt-1">Try adjusting your search or filters</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {products.map((product) => (
        <ProductCard
          key={product.asin}
          product={product}
          onClick={onProductClick}
        />
      ))}
    </div>
  )
}