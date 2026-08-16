import { useState } from 'react'

export default function SearchBar({ onSearch }) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex-1 max-w-2xl">
      <div className="relative flex items-center">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Amazon.sg products..."
          className="w-full px-4 py-2.5 pl-4 pr-12 rounded-lg bg-[#131921] border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-[#ff9900] focus:ring-1 focus:ring-[#ff9900] transition-colors"
        />
        <button
          type="submit"
          className="absolute right-1 px-3 py-1.5 bg-[#ff9900] hover:bg-[#e68a00] text-black font-medium rounded-md transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </button>
      </div>
    </form>
  )
}