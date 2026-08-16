export default function CategoryFilter({ categories, selected, onSelect }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {/* All Categories Pill */}
        <button
          onClick={() => onSelect('')}
          className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            selected === ''
              ? 'bg-[#ff9900] text-black'
              : 'bg-[#1a2332] text-gray-300 border border-gray-600 hover:border-[#ff9900] hover:text-white'
          }`}
        >
          All
        </button>

        {/* Category Pills */}
        {categories.map((category) => (
          <button
            key={category.name}
            onClick={() => onSelect(category.name)}
            className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              selected === category.name
                ? 'bg-[#ff9900] text-black'
                : 'bg-[#1a2332] text-gray-300 border border-gray-600 hover:border-[#ff9900] hover:text-white'
            }`}
          >
            {category.name}
            {category.count && (
              <span className="ml-1.5 text-xs opacity-70">({category.count})</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}