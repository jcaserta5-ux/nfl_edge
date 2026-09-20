/**
 * Injury Tracker Page
 * League-wide view of all active NFL injury designations.
 * Filterable by status and position. Highlights QB situations.
 */
import { useQuery } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { gamesApi } from '../api/client';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Filter, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

const STATUS_OPTIONS = ['All', 'Out', 'Doubtful', 'Questionable', 'Probable', 'IR', 'PUP'];
const POSITION_GROUPS: Record<string, string[]> = {
  QB:  ['QB'],
  Skill: ['RB', 'WR', 'TE'],
  OL:  ['LT', 'LG', 'C', 'RG', 'RT', 'OT', 'OL'],
  DL:  ['DE', 'DT', 'NT', 'EDGE'],
  LB:  ['LB', 'MLB', 'ILB', 'OLB'],
  DB:  ['CB', 'S', 'SS', 'FS'],
  'K/P': ['K', 'P'],
};

const statusMeta: Record<string, { color: string; bg: string; weight: number }> = {
  Out:          { color: 'text-red-300',    bg: 'bg-red-900/40 border-red-700',         weight: 5 },
  IR:           { color: 'text-red-300',    bg: 'bg-red-900/40 border-red-700',         weight: 5 },
  PUP:          { color: 'text-purple-300', bg: 'bg-purple-900/40 border-purple-700',   weight: 4 },
  Doubtful:     { color: 'text-orange-300', bg: 'bg-orange-900/40 border-orange-700',   weight: 3 },
  Questionable: { color: 'text-yellow-300', bg: 'bg-yellow-900/40 border-yellow-700',   weight: 2 },
  Probable:     { color: 'text-emerald-400',bg: 'bg-emerald-900/30 border-emerald-800', weight: 1 },
  NFI:          { color: 'text-gray-400',   bg: 'bg-gray-800 border-gray-600',          weight: 0 },
};

function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta[status] ?? { color: 'text-gray-400', bg: 'bg-gray-800 border-gray-600', weight: 0 };
  return (
    <span className={clsx('text-xs font-bold px-2 py-0.5 rounded border', meta.bg, meta.color)}>
      {status}
    </span>
  );
}

function positionGroup(pos?: string | null): string {
  if (!pos) return 'Other';
  const upper = pos.toUpperCase();
  for (const [group, positions] of Object.entries(POSITION_GROUPS)) {
    if (positions.includes(upper)) return group;
  }
  return 'Other';
}

export default function InjuryTracker() {
  const [statusFilter, setStatusFilter] = useState('All');
  const [posFilter, setPosFilter] = useState('All');
  const [search, setSearch] = useState('');

  const apiStatus = statusFilter === 'All' ? undefined : statusFilter;

  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['injuries', statusFilter],
    queryFn: () => gamesApi.injuries(apiStatus).then((r) => r.data),
    staleTime: 3 * 60 * 1000,
  });

  const allInjuries: any[] = data?.injuries ?? [];
  const lastUpdate = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : '—';

  // Client-side position + search filter
  const filtered = useMemo(() => {
    return allInjuries.filter((inj) => {
      if (posFilter !== 'All' && positionGroup(inj.position) !== posFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          inj.athlete_name?.toLowerCase().includes(q) ||
          inj.team_abbreviation?.toLowerCase().includes(q) ||
          inj.injury_type?.toLowerCase().includes(q) ||
          inj.position?.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [allInjuries, posFilter, search]);

  // Summary counts
  const counts = useMemo(() => {
    const c: Record<string, number> = { Out: 0, Doubtful: 0, Questionable: 0, Probable: 0, IR: 0 };
    for (const inj of allInjuries) {
      if (inj.status in c) c[inj.status]++;
    }
    return c;
  }, [allInjuries]);

  const qbAlerts = allInjuries.filter(
    (i) => i.is_qb && ['Out', 'Doubtful', 'IR'].includes(i.status)
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4 sm:p-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-gray-400 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <AlertTriangle className="w-5 h-5 text-orange-400" />
          <div>
            <h1 className="text-xl font-bold">Injury Tracker</h1>
            <p className="text-xs text-gray-500">
              {allInjuries.length} active designations · Updated {lastUpdate}
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg px-2.5 py-1.5 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* ── QB alert banner ───────────────────────────────────────────────── */}
      {qbAlerts.length > 0 && (
        <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 flex flex-wrap gap-3 items-center">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span className="text-sm font-semibold text-red-300">QB Alerts:</span>
          {qbAlerts.map((q: any) => (
            <span key={q.id} className="text-xs bg-red-900/40 text-red-200 border border-red-700 rounded-full px-2 py-0.5">
              {q.team_abbreviation} — {q.athlete_name} ({q.status})
            </span>
          ))}
        </div>
      )}

      {/* ── Status summary strip ──────────────────────────────────────────── */}
      <div className="grid grid-cols-5 gap-2 mb-5">
        {(['Out', 'IR', 'Doubtful', 'Questionable', 'Probable'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(statusFilter === s ? 'All' : s)}
            className={clsx(
              'rounded-xl border p-2.5 text-center transition-all hover:scale-[1.02]',
              statusFilter === s
                ? (statusMeta[s]?.bg ?? 'bg-gray-800 border-gray-600') + ' ring-1 ring-white/20'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            )}
          >
            <div className={clsx('text-lg font-black', statusMeta[s]?.color ?? 'text-gray-400')}>
              {counts[s] ?? 0}
            </div>
            <div className="text-xs text-gray-500">{s}</div>
          </button>
        ))}
      </div>

      {/* ── Filters bar ───────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 mb-5">
        {/* Status filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-gray-500" />
          <div className="flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={clsx(
                  'text-xs px-2 py-1 rounded-lg border transition-colors',
                  statusFilter === s
                    ? 'bg-orange-500 border-orange-500 text-black font-bold'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Position group filter */}
        <div className="flex gap-1 flex-wrap ml-auto">
          {['All', ...Object.keys(POSITION_GROUPS), 'Other'].map((g) => (
            <button
              key={g}
              onClick={() => setPosFilter(g)}
              className={clsx(
                'text-xs px-2 py-1 rounded-lg border transition-colors',
                posFilter === g
                  ? 'bg-blue-500 border-blue-500 text-black font-bold'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
              )}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* ── Search ────────────────────────────────────────────────────────── */}
      <input
        type="text"
        placeholder="Search by player, team, or injury type…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full mb-5 bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-colors"
      />

      {/* ── Results count ─────────────────────────────────────────────────── */}
      <div className="text-xs text-gray-500 mb-3">
        Showing {filtered.length} of {allInjuries.length} injury records
      </div>

      {/* ── Injury table ──────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-400">
          <div className="animate-spin w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p>Loading injury reports…</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg">
            {allInjuries.length === 0
              ? 'No injury data yet — run the injury ingestion task'
              : 'No injuries match your filters'}
          </p>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-3">Team</th>
                <th className="text-left px-4 py-3">Player</th>
                <th className="text-left px-4 py-3">Pos</th>
                <th className="text-left px-4 py-3">Injury</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Reported</th>
                <th className="text-left px-4 py-3">Impact</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((inj: any, idx: number) => (
                <tr
                  key={inj.id ?? idx}
                  className={clsx(
                    'border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors',
                    inj.is_qb && 'bg-blue-500/5'
                  )}
                >
                  {/* Team */}
                  <td className="px-4 py-3">
                    <span className="font-bold text-white">{inj.team_abbreviation}</span>
                    <div className="text-xs text-gray-500 hidden sm:block truncate max-w-[90px]">
                      {inj.team_name}
                    </div>
                  </td>

                  {/* Player name + jersey */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {inj.is_qb && (
                        <span className="text-xs bg-blue-800 text-blue-200 rounded px-1 py-0.5 font-bold flex-shrink-0">
                          QB
                        </span>
                      )}
                      <span className="font-medium text-white">{inj.athlete_name}</span>
                      {inj.jersey_number && (
                        <span className="text-gray-600 text-xs">#{inj.jersey_number}</span>
                      )}
                    </div>
                  </td>

                  {/* Position */}
                  <td className="px-4 py-3">
                    <span className="text-xs bg-gray-800 text-gray-300 rounded px-1.5 py-0.5">
                      {inj.position ?? '—'}
                    </span>
                  </td>

                  {/* Injury type */}
                  <td className="px-4 py-3 text-gray-400 text-xs">{inj.injury_type || '—'}</td>

                  {/* Status badge */}
                  <td className="px-4 py-3">
                    <StatusBadge status={inj.status} />
                  </td>

                  {/* Reported date */}
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {inj.reported_at
                      ? new Date(inj.reported_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })
                      : '—'}
                  </td>

                  {/* Impact indicator */}
                  <td className="px-4 py-3">
                    {inj.is_key_player ? (
                      <span className={clsx(
                        'text-xs font-semibold',
                        inj.is_qb ? 'text-blue-400' : 'text-orange-400'
                      )}>
                        {inj.is_qb ? '🚨 QB' : '⚠️ Key'}
                      </span>
                    ) : (
                      <span className="text-gray-700 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Footer legend ─────────────────────────────────────────────────── */}
      <div className="mt-4 text-xs text-gray-600 flex flex-wrap gap-4">
        <span><span className="text-blue-400">QB</span> = Quarterback alert (5× impact weight)</span>
        <span><span className="text-orange-400">⚠️ Key</span> = Starting-caliber player at impact position</span>
        <span>Data sourced from ESPN Injuries API · refreshed every 3 hours</span>
      </div>
    </div>
  );
}
