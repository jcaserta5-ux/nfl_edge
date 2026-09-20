import { useQuery } from '@tanstack/react-query';
import { gamesApi } from '../api/client';
import { GameCard } from '../components/GameCard';
import { WeekSelector } from '../components/WeekSelector';
import { useState } from 'react';
import { Activity, TrendingUp, Cloud, Zap, Shield, LogOut, AlertTriangle } from 'lucide-react';
import { useAuthStore } from '../store/auth';
import { Link, useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const [week, setWeek] = useState<number>(3);
  const season = 2026;
  const { username, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();

  const { data, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['games', season, week],
    queryFn: () => gamesApi.list({ season, week }).then((r) => r.data),
    refetchInterval: 60_000,
  });

  const games      = data?.games ?? [];
  const highEdge   = games.filter((g: any) => g.edge?.confidence === 'high');
  const medEdge    = games.filter((g: any) => g.edge?.confidence === 'medium');
  const lastUpdate = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : '—';

  // Count games with notable injuries (QB Out/Doubtful anywhere)
  const injuryAlerts = games.filter((g: any) => {
    const hi = g.injury_summary?.home ?? {};
    const ai = g.injury_summary?.away ?? {};
    return (
      (hi.qb_status && ['Out', 'Doubtful', 'IR'].includes(hi.qb_status)) ||
      (ai.qb_status && ['Out', 'Doubtful', 'IR'].includes(ai.qb_status)) ||
      (hi.out ?? 0) + (hi.doubtful ?? 0) >= 3 ||
      (ai.out ?? 0) + (ai.doubtful ?? 0) >= 3
    );
  });

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-gray-800 px-4 sm:px-6 py-3 flex items-center justify-between gap-3 sticky top-0 z-10 bg-gray-950/95 backdrop-blur">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <span className="text-xl sm:text-2xl flex-shrink-0">🏈</span>
          <h1 className="text-base sm:text-xl font-bold tracking-tight truncate">NFL Betting Edge</h1>
          <span className="hidden sm:inline text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full px-2 py-0.5 flex-shrink-0">
            LIVE
          </span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <WeekSelector week={week} onChange={setWeek} />

          {/* ── Power Rankings nav link ── */}
          <Link
            to="/rankings"
            className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 hover:text-emerald-400 border border-gray-700 hover:border-emerald-600 rounded-lg px-2.5 py-1.5 transition-colors"
            title="Power Rankings"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Rankings</span>
          </Link>

          {/* ── Injury Tracker nav link ── */}
          <Link
            to="/injuries"
            className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 hover:text-orange-400 border border-gray-700 hover:border-orange-600 rounded-lg px-2.5 py-1.5 transition-colors"
            title="Injury Tracker"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Injuries</span>
          </Link>

          {/* ── Admin link ── */}
          <Link
            to="/admin"
            className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg px-2.5 py-1.5 transition-colors"
          >
            <Shield className="w-3.5 h-3.5" /> Admin
          </Link>

          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg px-2.5 py-1.5 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      {/* ── Stats bar ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-gray-800 border-b border-gray-800">
        {[
          { label: 'Games',           value: games.length,        icon: Activity,       color: 'text-blue-400' },
          { label: 'High Confidence', value: highEdge.length,     icon: Zap,            color: 'text-yellow-400' },
          { label: 'Injury Alerts',   value: injuryAlerts.length, icon: AlertTriangle,  color: 'text-orange-400' },
          { label: 'Last Refresh',    value: lastUpdate,          icon: Cloud,          color: 'text-purple-400' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-gray-900 px-4 py-3 flex items-center gap-3">
            <Icon className={`w-4 h-4 flex-shrink-0 ${color}`} />
            <div className="min-w-0">
              <div className="text-lg sm:text-2xl font-bold leading-tight">{value}</div>
              <div className="text-xs text-gray-400 truncate">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Edge alert banner ─────────────────────────────────────────────── */}
      {highEdge.length > 0 && (
        <div className="bg-yellow-500/10 border-b border-yellow-500/20 px-4 sm:px-6 py-2.5 flex items-center gap-2 text-sm">
          <Zap className="w-4 h-4 text-yellow-400 flex-shrink-0" />
          <span className="text-yellow-300 font-semibold">
            {highEdge.length} high-confidence edge{highEdge.length > 1 ? 's' : ''} this week
          </span>
          <span className="text-yellow-500 hidden sm:inline">— click a game card to see the breakdown</span>
        </div>
      )}

      {/* ── Injury alert banner ───────────────────────────────────────────── */}
      {injuryAlerts.length > 0 && (
        <div className="bg-orange-500/10 border-b border-orange-500/20 px-4 sm:px-6 py-2.5 flex items-center gap-2 text-sm">
          <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
          <span className="text-orange-300 font-semibold">
            {injuryAlerts.length} game{injuryAlerts.length > 1 ? 's' : ''} with significant injury concerns
          </span>
          <Link
            to="/injuries"
            className="text-orange-400 underline underline-offset-2 hidden sm:inline hover:text-orange-300 transition-colors"
          >
            View all injuries →
          </Link>
        </div>
      )}

      {/* ── Game grid ─────────────────────────────────────────────────────── */}
      <main className="p-4 sm:p-6">
        {isLoading && (
          <div className="text-center text-gray-400 py-20">
            <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4" />
            <p>Loading Week {week} games…</p>
          </div>
        )}
        {error && (
          <div className="text-center text-red-400 py-20">
            <p className="text-lg font-semibold mb-1">Failed to load games</p>
            <p className="text-sm text-red-500">
              Check that the backend is running at {import.meta.env.VITE_API_BASE_URL}
            </p>
          </div>
        )}
        {!isLoading && !error && games.length === 0 && (
          <div className="text-center text-gray-500 py-20">
            <p className="text-lg">No games found for Week {week}, {season}</p>
            <p className="text-sm mt-1">Odds data may not be available yet for this week.</p>
            <div className="mt-6 flex justify-center gap-3">
              <Link
                to="/rankings"
                className="flex items-center gap-2 text-sm text-emerald-400 border border-emerald-700 hover:border-emerald-500 rounded-lg px-3 py-2 transition-colors"
              >
                <TrendingUp className="w-4 h-4" /> View Power Rankings
              </Link>
              <Link
                to="/injuries"
                className="flex items-center gap-2 text-sm text-orange-400 border border-orange-700 hover:border-orange-500 rounded-lg px-3 py-2 transition-colors"
              >
                <AlertTriangle className="w-4 h-4" /> View Injury Tracker
              </Link>
            </div>
          </div>
        )}

        {/* Sort: high confidence first, then by game time */}
        <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
          {[...games]
            .sort((a: any, b: any) => {
              const confOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
              const aConf = confOrder[a.edge?.confidence ?? 'low'] ?? 2;
              const bConf = confOrder[b.edge?.confidence ?? 'low'] ?? 2;
              if (aConf !== bConf) return aConf - bConf;
              return new Date(a.game_time).getTime() - new Date(b.game_time).getTime();
            })
            .map((game: any) => (
              <GameCard key={game.id} game={game} />
            ))}
        </div>
      </main>

      {/* ── Mobile bottom nav ─────────────────────────────────────────────── */}
      <div className="sm:hidden border-t border-gray-800 px-4 py-3 flex justify-around">
        <Link
          to="/rankings"
          className="flex flex-col items-center gap-0.5 text-gray-400 hover:text-emerald-400 transition-colors"
        >
          <TrendingUp className="w-5 h-5" />
          <span className="text-xs">Rankings</span>
        </Link>
        <Link
          to="/injuries"
          className="flex flex-col items-center gap-0.5 text-gray-400 hover:text-orange-400 transition-colors"
        >
          <AlertTriangle className="w-5 h-5" />
          <span className="text-xs">Injuries</span>
        </Link>
        <Link
          to="/admin"
          className="flex flex-col items-center gap-0.5 text-gray-400 hover:text-white transition-colors"
        >
          <Shield className="w-5 h-5" />
          <span className="text-xs">Admin</span>
        </Link>
      </div>
    </div>
  );
}
