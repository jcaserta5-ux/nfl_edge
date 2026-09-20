import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { gamesApi } from '../api/client';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ArrowLeft, Wind, Thermometer, Droplets, TrendingUp, AlertTriangle, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

// ── Status badge helper ────────────────────────────────────────────────────────
const statusColors: Record<string, string> = {
  Out:          'bg-red-900/60 text-red-300 border-red-700',
  IR:           'bg-red-900/60 text-red-300 border-red-700',
  Doubtful:     'bg-orange-900/60 text-orange-300 border-orange-700',
  Questionable: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  Probable:     'bg-emerald-900/40 text-emerald-400 border-emerald-700',
  PUP:          'bg-purple-900/60 text-purple-300 border-purple-700',
  NFI:          'bg-gray-800 text-gray-400 border-gray-600',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={clsx(
      'text-xs font-semibold px-1.5 py-0.5 rounded border',
      statusColors[status] ?? 'bg-gray-800 text-gray-400 border-gray-600'
    )}>
      {status}
    </span>
  );
}

// ── Rank display helper ────────────────────────────────────────────────────────
function RankDot({ rank }: { rank?: number }) {
  if (!rank) return null;
  const color =
    rank <= 8  ? 'text-emerald-400' :
    rank <= 16 ? 'text-yellow-400' :
    rank <= 24 ? 'text-orange-400' : 'text-red-400';
  return <span className={clsx('font-bold', color)}>#{rank}</span>;
}

export default function GameDetail() {
  const { id } = useParams<{ id: string }>();
  const gameId = Number(id);

  const { data } = useQuery({
    queryKey: ['game', gameId],
    queryFn: () => gamesApi.get(gameId).then((r) => r.data),
  });

  const { data: historyData } = useQuery({
    queryKey: ['game-odds-history', gameId],
    queryFn: () => gamesApi.oddsHistory(gameId).then((r) => r.data),
  });

  const game        = data?.game ?? {};
  const odds        = data?.odds ?? {};
  const edge        = data?.edge ?? {};
  const weather     = data?.weather ?? {};
  const homeRank    = data?.home_ranking ?? {};
  const awayRank    = data?.away_ranking ?? {};
  const homeInjuries: any[] = data?.home_injuries ?? [];
  const awayInjuries: any[] = data?.away_injuries ?? [];
  const history     = historyData?.snapshots ?? [];

  const chartData = [...history].reverse().map((s: any, i: number) => ({
    name: `T-${history.length - i}`,
    spread: s.home_spread,
    total: s.total,
    homePct: s.home_spread_pct,
    overPct: s.over_pct,
  }));

  const scoreItems = [
    { label: 'Line Movement',      score: edge.line_move_score,         color: '#3b82f6' },
    { label: 'Sharp Money',        score: edge.sharp_money_score,        color: '#f59e0b' },
    { label: 'Weather Impact',     score: edge.weather_impact_score,     color: '#06b6d4' },
    { label: 'Kalshi Divergence',  score: edge.kalshi_divergence_score,  color: '#a855f7' },
    { label: 'Public Fade',        score: edge.public_fade_score,        color: '#ef4444' },
    { label: 'Power Rankings',     score: edge.power_ranking_score,      color: '#10b981' },   // NEW
    { label: 'Injury Impact',      score: edge.injury_impact_score,      color: '#f97316' },   // NEW
  ];

  const notableHomeInj = homeInjuries.filter(
    (i) => i.is_key_player && ['Out', 'IR', 'Doubtful', 'Questionable'].includes(i.status)
  );
  const notableAwayInj = awayInjuries.filter(
    (i) => i.is_key_player && ['Out', 'IR', 'Doubtful', 'Questionable'].includes(i.status)
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-white mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </Link>

      {/* ── Matchup header ──────────────────────────────────────────────────── */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8 mb-6 text-center">
        <div className="flex items-center justify-center gap-8">
          <div>
            <div className="text-5xl font-black">{game.away_team}</div>
            <div className="text-gray-400 mt-1">AWAY</div>
            {awayRank.overall_rank && (
              <div className="text-sm text-gray-400 mt-1">
                Power rank <RankDot rank={awayRank.overall_rank} />
              </div>
            )}
          </div>
          <div className="text-gray-600 text-2xl font-bold">@</div>
          <div>
            <div className="text-5xl font-black">{game.home_team}</div>
            <div className="text-gray-400 mt-1">HOME</div>
            {homeRank.overall_rank && (
              <div className="text-sm text-gray-400 mt-1">
                Power rank <RankDot rank={homeRank.overall_rank} />
              </div>
            )}
          </div>
        </div>
        <div className="mt-4 text-gray-500 text-sm">
          {game.game_time ? new Date(game.game_time).toLocaleString('en-US', {
            weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
            hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
          }) : ''}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* ── Current odds ──────────────────────────────────────────────────── */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="font-bold mb-4 text-gray-300">Current Odds (DraftKings)</h2>
          <div className="space-y-3">
            {[
              ['Home Spread', odds.home_spread != null ? `${odds.home_spread > 0 ? '+' : ''}${odds.home_spread} (${odds.home_spread_juice})` : '—'],
              ['Away Spread', odds.away_spread != null ? `${odds.away_spread > 0 ? '+' : ''}${odds.away_spread} (${odds.away_spread_juice})` : '—'],
              ['Home ML', odds.home_ml != null ? (odds.home_ml > 0 ? `+${odds.home_ml}` : String(odds.home_ml)) : '—'],
              ['Away ML', odds.away_ml != null ? (odds.away_ml > 0 ? `+${odds.away_ml}` : String(odds.away_ml)) : '—'],
              ['Total', odds.total != null ? `${odds.total} (O${odds.over_juice} / U${odds.under_juice})` : '—'],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between items-center">
                <span className="text-sm text-gray-400">{label}</span>
                <span className="text-sm font-mono font-bold">{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Public money ──────────────────────────────────────────────────── */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="font-bold mb-4 text-gray-300">Public Money Split</h2>
          {[
            { label: 'Spread Bets', home: odds.home_spread_pct, away: odds.away_spread_pct },
            { label: 'Money %', home: odds.home_money_pct, away: odds.away_money_pct },
            { label: 'Total Bets', home: odds.over_pct, away: odds.under_pct, labels: ['Over', 'Under'] },
          ].map(({ label, home, away, labels }) => (
            <div key={label} className="mb-4">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{labels?.[0] ?? game.away_team} {away?.toFixed(0) ?? '—'}%</span>
                <span className="text-gray-600">{label}</span>
                <span>{labels?.[1] ?? game.home_team} {home?.toFixed(0) ?? '—'}%</span>
              </div>
              {home != null && (
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden flex">
                  <div className="bg-red-500 h-full" style={{ width: `${away}%` }} />
                  <div className="bg-emerald-500 h-full" style={{ width: `${home}%` }} />
                </div>
              )}
            </div>
          ))}
          {odds.total_bet_count && (
            <div className="text-xs text-gray-500 mt-2">
              {odds.total_bet_count.toLocaleString()} total bets tracked
            </div>
          )}
        </div>

        {/* ── Weather ───────────────────────────────────────────────────────── */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="font-bold mb-4 text-gray-300">Game Weather</h2>
          {weather.temp_f != null ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Thermometer className="w-5 h-5 text-orange-400" />
                <span className="text-xl font-bold">{weather.temp_f?.toFixed(0)}°F</span>
                <span className="text-gray-500 text-sm">{weather.condition_desc}</span>
              </div>
              <div className="flex items-center gap-3">
                <Wind className="w-5 h-5 text-blue-400" />
                <span className="font-bold">{weather.wind_mph?.toFixed(0)} mph</span>
                <span className="text-gray-500 text-sm">from {weather.wind_dir_deg}°</span>
              </div>
              {(weather.precip_mm ?? 0) > 0 && (
                <div className="flex items-center gap-3">
                  <Droplets className="w-5 h-5 text-sky-400" />
                  <span className="font-bold">{weather.precip_mm?.toFixed(1)} mm</span>
                  <span className="text-gray-500 text-sm">precipitation</span>
                </div>
              )}
              <div className="mt-4 p-3 rounded-lg bg-gray-800 text-sm text-gray-300">
                <span className="font-semibold text-gray-200">Weather impact: </span>
                {weather.wind_mph >= 20
                  ? '⚠️ High wind — consider under'
                  : weather.temp_f <= 25
                  ? '🥶 Extreme cold — totals suppressed'
                  : '✅ No significant weather factor'}
              </div>
            </div>
          ) : (
            <div className="text-gray-500 text-sm">🏟️ Indoor stadium — no weather impact</div>
          )}
        </div>
      </div>

      {/* ── Power Rankings comparison (NEW) ────────────────────────────────── */}
      {(homeRank.overall_rank || awayRank.overall_rank) && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mt-6">
          <h2 className="font-bold text-gray-300 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Power Rankings Comparison
          </h2>
          <div className="grid grid-cols-2 gap-6">
            {[
              { label: game.away_team, ranking: awayRank },
              { label: game.home_team, ranking: homeRank },
            ].map(({ label, ranking }) => (
              <div key={label} className="space-y-2">
                <div className="text-sm font-bold text-gray-200">{label}</div>
                {[
                  { name: 'Overall',   rank: ranking.overall_rank,   color: '#10b981' },
                  { name: 'Offense',   rank: ranking.offensive_rank,  color: '#3b82f6' },
                  { name: 'Defense',   rank: ranking.defensive_rank,  color: '#ef4444' },
                ].map(({ name, rank, color }) => (
                  rank && (
                    <div key={name}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-gray-400">{name}</span>
                        <RankDot rank={rank} />
                      </div>
                      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.max(5, 100 - ((rank - 1) / 31) * 100)}%`,
                            backgroundColor: color,
                          }}
                        />
                      </div>
                    </div>
                  )
                ))}
                {ranking.fpi_score != null && (
                  <div className="text-xs text-gray-500 mt-1">
                    FPI: <span className="text-white font-mono">{ranking.fpi_score?.toFixed(1)}</span>
                  </div>
                )}
                {ranking.win_pct != null && (
                  <div className="text-xs text-gray-500">
                    Record: <span className="text-white">{ranking.wins}–{ranking.losses}</span>
                    <span className="text-gray-600 ml-1">({(ranking.win_pct * 100).toFixed(0)}%)</span>
                  </div>
                )}
                {ranking.point_diff != null && (
                  <div className={clsx(
                    'text-xs font-semibold',
                    ranking.point_diff > 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    Pt Diff: {ranking.point_diff > 0 ? '+' : ''}{ranking.point_diff?.toFixed(1)} / game
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Injury Reports panel (NEW) ─────────────────────────────────────── */}
      {(notableHomeInj.length > 0 || notableAwayInj.length > 0) && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mt-6">
          <h2 className="font-bold text-gray-300 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            Injury Report
          </h2>
          <div className="grid sm:grid-cols-2 gap-6">
            {[
              { teamLabel: game.away_team, injuries: notableAwayInj },
              { teamLabel: game.home_team, injuries: notableHomeInj },
            ].map(({ teamLabel, injuries }) => (
              <div key={teamLabel}>
                <div className="text-sm font-semibold text-gray-300 mb-2">{teamLabel}</div>
                {injuries.length === 0 ? (
                  <div className="text-xs text-gray-500 italic">No notable injuries</div>
                ) : (
                  <div className="space-y-1.5">
                    {injuries.map((inj: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={clsx(
                            'text-xs font-bold rounded px-1 py-0.5 flex-shrink-0',
                            inj.is_qb ? 'bg-blue-800 text-blue-200' : 'bg-gray-800 text-gray-400'
                          )}>
                            {inj.position ?? '?'}
                          </span>
                          <span className="text-sm text-gray-200 truncate">{inj.athlete_name}</span>
                          {inj.injury_type && (
                            <span className="text-xs text-gray-500 hidden sm:inline truncate">
                              {inj.injury_type}
                            </span>
                          )}
                        </div>
                        <StatusBadge status={inj.status} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Edge score breakdown ───────────────────────────────────────────── */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mt-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-300">Edge Score Breakdown</h2>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-black text-yellow-400">{edge.composite_score?.toFixed(0) ?? 0}</span>
            <span className="text-gray-500">/ 100</span>
            {edge.confidence && (
              <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${
                edge.confidence === 'high'   ? 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30' :
                edge.confidence === 'medium' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                'bg-gray-700 text-gray-400'
              }`}>
                {edge.confidence?.toUpperCase()} CONFIDENCE
              </span>
            )}
          </div>
        </div>
        <div className="space-y-3">
          {scoreItems.map(({ label, score, color }) => (
            <div key={label}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">{label}</span>
                <span className="font-mono font-bold">{score?.toFixed(0) ?? 0}</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${score ?? 0}%`, backgroundColor: color }}
                />
              </div>
            </div>
          ))}
        </div>
        {edge.notes?.length > 0 && (
          <div className="mt-4 space-y-1">
            {edge.notes.map((note: string, i: number) => (
              <div key={i} className="text-sm text-gray-300 flex gap-2">
                <span className="text-yellow-400">→</span> {note}
              </div>
            ))}
          </div>
        )}
        {edge.recommendation && edge.recommendation !== 'none' && (
          <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 font-semibold text-sm">
            📊 Recommendation: {edge.recommendation.replace('_', ' ').toUpperCase()}
          </div>
        )}
      </div>

      {/* ── Line movement chart ────────────────────────────────────────────── */}
      {chartData.length > 1 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 mt-6">
          <h2 className="font-bold text-gray-300 mb-4">Line Movement History</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <XAxis dataKey="name" stroke="#6b7280" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#fff' }} />
              <Legend />
              <Line type="monotone" dataKey="spread" stroke="#3b82f6" strokeWidth={2} dot={false} name="Home Spread" />
              <Line type="monotone" dataKey="total"  stroke="#10b981" strokeWidth={2} dot={false} name="Total" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
