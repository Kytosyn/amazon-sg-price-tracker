export default function StatsBar({ stats }) {
  const {
    total_products,
    total_price_points,
    products_updated_today,
    lowest_price,
    highest_price,
    average_discount,
  } = stats || {}

  const statItems = [
    {
      label: 'Products',
      value: total_products || 0,
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
      ),
    },
    {
      label: 'Price Points',
      value: total_price_points || 0,
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      label: 'Updated Today',
      value: products_updated_today || 0,
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      ),
    },
    {
      label: 'Lowest Price',
      value: lowest_price ? `S$${lowest_price.toFixed(2)}` : 'S$0.00',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
        </svg>
      ),
      color: 'text-green-400',
    },
    {
      label: 'Highest Price',
      value: highest_price ? `S$${highest_price.toFixed(2)}` : 'S$0.00',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ),
      color: 'text-red-400',
    },
    {
      label: 'Avg Discount',
      value: average_discount ? `${average_discount.toFixed(1)}%` : '0%',
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
      ),
      color: 'text-[#ff9900]',
    },
  ]

  return (
    <div className="bg-[#1a2332] border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
          {statItems.map((item, index) => (
            <div key={index} className="flex items-center gap-3">
              <div className="text-gray-400">{item.icon}</div>
              <div>
                <p className={`text-lg font-bold ${item.color || 'text-white'}`}>
                  {typeof item.value === 'number'
                    ? item.value.toLocaleString()
                    : item.value}
                </p>
                <p className="text-xs text-gray-400">{item.label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}