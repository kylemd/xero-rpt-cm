function App() {
  return (
    <div className="flex flex-col h-screen bg-white text-gray-800">
      {/* Header */}
      <header className="flex items-center h-12 px-4 border-b border-gray-200 shrink-0">
        <span className="text-blue-600 font-semibold text-lg tracking-tight">
          Xero Code Mapper
        </span>
      </header>

      {/* Body: sidebar + main */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-70 shrink-0 border-r border-gray-200 bg-gray-50 p-4">
          <p className="text-sm text-gray-400">Sidebar</p>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <p className="text-sm text-gray-400">Main content area</p>
        </main>
      </div>
    </div>
  )
}

export default App
