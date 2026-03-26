import { Link, Outlet, useLocation } from 'react-router-dom'
import { Zap, FolderOpen, Settings, BookOpen } from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { to: '/', label: 'Projects', icon: FolderOpen },
  { to: '/presets', label: 'Presets', icon: Settings },
]

export default function Layout() {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-titan-700 text-white shadow-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-lg tracking-tight">
            <Zap size={22} className="text-yellow-300" />
            TitanTool
          </Link>
          <nav className="flex gap-1">
            {nav.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                  pathname === to
                    ? 'bg-white/20 text-white'
                    : 'text-blue-100 hover:bg-white/10 hover:text-white',
                )}
              >
                <Icon size={15} />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-3 text-center text-xs text-gray-400">
        TitanTool v0.1 · Electrical Takeoff Automation
      </footer>
    </div>
  )
}
