/**
 * Power Rankings Page
 * Displays all 32 NFL teams sorted by ESPN FPI / standings-derived rank.
 * Supports week selection and sortable columns.
 */
import { useQuery } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { gamesApi } from '../api/client';
import { Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import clsx from 'clsx';

type SortKey =
  | 'overall_rank'
  | 'offensive_rank'
  | 'defensive_rank'
  | 'fpi_score'
  | 'win_pct'
  | 'point_diff';

const SEASON = 2026;

const rankColor = (rank?: number | null): string => {
  if (!rank) return 'text-gray-500';
  if (rank <= 8)  return 'text-emerald-400 font-bold';
  if (rank <= 16) return 'text-yellow-400 font-semibold';
  if (rank <= 24) return 'text-orange-400';
  return 'text-red-400';
};

const diffColor = (diff?: number | null): string => {
  if (diff == null) return 'text-gray-500';
  if (diff > 7)  return 'text-emerald-400 font-bold';
  if (diff > 0)  return 'text-emerald-600';
  if (diff > -7) return 'text-red-400';
  return 'text-red-500 font-bold';
};

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <ChevronsUpDown className="w-3 h-3 text-gray-600 inline ml-1" />;
  return dir === 'asc'
    ? <ChevronUp className="w-3 h-3 text-yellow-400 inline ml-1" />
    : <ChevronDown className="w-3 h-3 text-yellow-400 inline ml-1" />;
}

export default function PowerRankings() {
  const [week, setWeek] = useState(3);
  const [sortKey, setSortKey] = useState<SortKey>('overall_rank');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const { data, isLoading } = useQuery({
    queryKey: ['rankings', SEASON, week],
    queryFn: () => gamesApi.rankings(SEASON, week).then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const rankings: any[] = data?.rankings ?? [];

  const sorted = useMemo(() => {
    return [...rankings].sort((a, b) => {
      const av = a[sortKey] ?? (sortDir === 'asc' ? 9999 : -9999);
      const bv = b[sortKey] ?? (sortDir === 'asc' ? 9999 : -9999);
      if (sortKey === 'fpi_score' || sortKey === 'win_pct' || sortKey === 'point_diff') {
        // Higher is better â€” reverse for ascending = best first
        return sortDir === 'asc' ? bv - av : av - bv;
      }
      // Ranks: lower number = better team
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [rankings, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sourceLabel = data?.rankings?.[0]?.source === 'fpi' ? 'ESPN FPI' : 'Standings';

  const cols: { label: string; key: SortKey; title: string }[] = [
    { label: 'Overall',  key: 'overall_rank',   title: 'Overall power rank' },
    { label: 'Offense',  key: 'offensive_rank',  title: 'Offensive rank' },
    { label: 'Defense',  key: 'defensive_rank',  title: 'Defensive rank' },
    { label: 'FPI',      key: 'fpi_score',       title: 'Football Power Index score' },
    { label: 'Win %',    key: 'win_pct',         title: 'Win percentage' },
    { label: 'Pt Diff',  key: 'point_diff',      title: 'Points per game differential' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4 sm:p-6">
      {/* â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-gray-400 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          <div>
            <h1 className="text-xl font-bold">Power Rankings</h1>
            <p className="text-xs text-gray-500">
              Season {SEASON} Â· Week {data?.week ?? week} Â· Source: {sourceLabel}
            </p>
          </div>
        </div>

        {/* Week selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Week</span>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5, 6].map((w) => (
              <button
                key={w}
                onClick={() => setWeek(w)}
                className={clsx(
                  'w-8 h-8 rounded-lg text-sm font-bold transition-colors',
                  week === w
                    ? 'bg-emerald-500 text-black'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                )}
              >
                {w}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* â”€â”€ Stats strip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: 'Teams ranked', value: rankings.length || 'â€”' },
          { label: 'Data source', value: sourceLabel },
          { label: 'Week', value: data?.week ?? 'â€”' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-900 rounded-xl border border-gray-800 p-3 text-center">
            <div className="text-lg font-bold text-emerald-400">{value}</div>
            <div className="text-xs text-gray-500">{label}</div>
          </div>
        ))}
      </div>

      {/* â”€â”€ Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-400">
          <div className="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p>Loading power rankingsâ€¦</p>
        </div>
      ) : rankings.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <TrendingUp className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg">No power rankings data yet</p>
          <p className="text-sm mt-1">
            Run the power rankings ingestion task to populate this page.
          </p>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
                <th className="text-left px-4 py-3 w-8">#</th>
                <th className="text-left px-4 py-3">Team</th>
                <th className="text-left px-4 py-3">Record</th>
                {cols.map(({ label, key, title }) => (
                  <th
                    key={key}
                    className="px-3 py-3 text-right cursor-pointer hover:text-white select-none"
                    title={title}
                    onClick={() => handleSort(key)}
                  >
                    {label}
                    <SortIcon active={sortKey === key} dir={sortDir} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r: any, idx: number) => (
                <tr
                  key={r.team_id ?? idx}
                  className={clsx(
                    'border-b border-gray-800/50 hover:bg-gray-800/40 transition-colors',
                    idx < 3 && 'bg-emerald-500/5'
                  )}
                >
                  {/* Rank number badge */}
                  <td className="px-4 py-3">
                    <span className={clsx(
                      'text-sm font-black w-7 h-7 rounded-full flex items-center justify-center',
                      idx === 0 ? 'bg-yellow-500 text-black' :
                      idx === 1 ? 'bg-gray-400 text-black' :
                      idx === 2 ? 'bg-amber-700 text-black' :
                      'text-gray-500'
                    )}>
                      {idx + 1}
                    </span>
                  </td>

                  {/* Team name */}
                  <td className="px-4 py-3">
                    <div className="font-bold text-white">{r.abbreviation}</div>
                    <div className="text-xs text-gray-500 hidden sm:block">{r.city} {r.team_name}</div>
                  </td>

                  {/* Record */}
                  <td className="px-4 py-3 text-gray-300 font-mono text-xs">
                    {r.wins != null && r.losses != null
                      ? `${r.wins}â€“${r.losses}`
                      : <span className="text-gray-600">â€”</span>}
                  </td>

                  {/* Overall rank */}
                  <td className="px-3 py-3 text-right">
                    <span className={rankColor(r.overall_rank)}>
                      {r.overall_rank ? `#${r.overall_rank}` : 'â€”'}
                    </span>
                  </td>

                  {/* Offensive rank */}
                  <td className="px-3 py-3 text-right">
                    <span className={rankColor(r.offensive_rank)}>
                      {r.offensive_rank ? `#${r.offensive_rank}` : 'â€”'}
                    </span>
                  </td>

                  {/* Defensive rank */}
                  <td className="px-3 py-3 text-right">
                    <span className={rankColor(r.defensive_rank)}>
                      {r.defensive_rank ? `#${r.defensive_rank}` : 'â€”'}
                    </span>
                  </td>

                  {/* FPI score */}
                  <td className="px-3 py-3 text-right font-mono">
                    {r.fpi_score != null ? (
                      <span className={r.fpi_score > 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {r.fpi_score > 0 ? '+' : ''}{r.fpi_score.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-gray-600">â€”</span>
                    )}
                  </td>

                  {/* Win pct */}
                  <td className="px-3 py-3 text-right font-mono">
                    {r.win_pct != null ? (
                      <span className={r.win_pct >= 0.6 ? 'text-emerald-400' : r.win_pct < 0.4 ? 'text-red-400' : 'text-gray-300'}>
                        {(r.win_pct * 100).toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-gray-600">â€”</span>
                    )}
                  </td>

                  {/* Point diff */}
                  <td className="px-3 py-3 text-right font-mono">
                    {r.point_diff != null ? (
                      <span className={diffColor(r.point_diff)}>
                        {r.point_diff > 0 ? '+' : ''}{r.point_diff.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-gray-600">â€”</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* â”€â”€ Legend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-500">
        <span><span className="text-emerald-400 font-bold">Green</span> = Top 8 / positive</span>
        <span><span className="text-yellow-400">Yellow</span> = 9â€“16</span>
        <span><span className="text-orange-400">Orange</span> = 17â€“24</span>
        <span><span className="text-red-400">Red</span> = Bottom 8 / negative</span>
        <span className="ml-auto">
          FPI = Football Power Index (ESPN). Higher is better.
          Pt Diff = points scored minus points allowed per game.
        </span>
      </div>
    </div>
  );
}
