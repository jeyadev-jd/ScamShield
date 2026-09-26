import { NavLink, Link } from 'react-router-dom'

const LINKS = [
  ['/', 'Analyze'], ['/cases', 'Cases'], ['/research', 'Research'],
  ['/dataset', 'Dataset'], ['/train', 'Train'], ['/method', 'Method'],
]

export default function TopNav() {
  return (
    <header className="border-b border-rule bg-paper">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-baseline gap-x-8 gap-y-2 px-4 py-3 sm:px-8">
        <Link to="/" className="font-serif text-xl font-semibold tracking-[0.12em]">SCAMSHIELD</Link>
        <nav className="flex flex-wrap gap-x-5 text-sm">
          {LINKS.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `border-b py-1 ${isActive ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink'}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
