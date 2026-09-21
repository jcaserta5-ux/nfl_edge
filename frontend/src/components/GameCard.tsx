import clsx from 'clsx';
import { Wind, Thermometer, Droplets, Zap, AlertTriangle, Info } from 'lucide-react';
import { Link } from 'react-router-dom';

interface Props {
  game: any;
}

const confidenceColors: Record<string, string> = {
  high:   'border-yellow-500 bg-yellow-500/10',
  medium: 'border-blue-500 bg-blue-500/10',
  low:    'border-gray-700 bg-gray-900',
};

const recommendationLabels: Record<string, string> = {
  home_spread: '🏠 Home Spread',
  away_spread: '✈️ Away Spread',
  over:        '📈 Over',
  under:       '📉 Under',
  investigate: '🔍 Investigate',
  none:        '',
};

const SIGNAL_META: Record<string, { short: string; tooltip: string; color: string }> = {
  line_move_score:      { short: 'LINE',  color: 'text-blue-400',   tooltip: 'Line Movement — how much the spread has shifted since opening. Big moves signal sharp (professional) betting action.' },
  sharp_money_score:    { short: 'SHARP', color: 'text-purple-400', tooltip: 'Sharp Money — indicator of professional bettor activity. High scores mean pros are loading up heavily on one side.' },
  weather_impact_score: { short: 'WX',    color: 'text-cyan-400',   tooltip: 'Weather Impact — effect of wind, rain, or snow on the game. High scores favor unders or ground-heavy offenses.' },
  public_fade_score:    { short: 'FADE',  color: 'text-orange-400', tooltip: 'Public Fade — signal to bet against the public. High scores mean the crowd is lopsided on one side, a historically profitable spot to fade.' },
  power_ranking_score:  { short: 'PWR',   color: 'text-yellow-400', tooltip: 'Power Rankings Gap — talent mismatch between teams based on ESPN FPI scores. Higher = bigger capability difference.' },
  injury_impact_score:  { short: 'INJ',   color: 'text-red-400',    tooltip: 'Injury Impact — combined effect of key player absences on both sides. Higher = more impactful injuries affecting the line.' },
};

function rankBadge(rank?: number): string {
  return rank ? `#${rank}` : '';
}

function injuryDotColor(status?: string | null): string {
  if (!status) return '';
  if (status === 'Out' || status === 'IR') return 'bg-red-500';
  if (status === 'Doubtful') return 'bg-orange-500';
  if (status === 'Questionable') return 'bg-yellow-500';
  return 'bg-gray-500';
}

function espnLogo(abbr: string): string {
  return `https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/${abbr.toLowerCase()}.png&h=64&w=64`;
}

function SignalBar({ value }: { value: number }) {
  const pct   = Math.min(100, Math.abs(value));
  const color = value >= 60 ? 'bg-green-500' : value >= 30 ? 'bg-yellow-500' : 'bg-gray-600';
  return (
    <div className="h-1 w-full bg-gray-800 rounded-full mt-0.5 overflow-hidden">
      <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function GameCard({ game }: Props) {
  const edge       = game.edge ?? {};
  const odds       = game.odds ?? {};
  const weather    = game.weather ?? {};
  const homeRank   = game.home_ranking ?? {};
  const awayRank   = game.away_ranking ?? {};
  const injSummary = game.injury_summary ?? {};
  const homeInj    = injSummary.home ?? {};
  const awayInj    = injSummary.away ?? {};

  const confidence = edge.confidence ?? 'low';
  const rec        = edge.recommendation ?? 'none';

  const showHomeQbAlert = homeInj.qb_status && homeInj.qb_status !== 'Probable';
  const showAwayQbAlert = awayInj.qb_status && awayInj.qb_status !== 'Probable';
  const homeOutCount    = (homeInj.out ?? 0) + (homeInj.doubtful ?? 0);
  const awayOutCount    = (awayInj.out ?? 0) + (awayInj.doubtful ?? 0);

  const isLive        = game.status === 'live';
  const isFinal       = game.status === 'final';
  const hasScore      = game.home_score != null && game.away_score != null;
  const compositeScore = edge.composite_score ?? 0;

  const confidenceBadgeColor =
    confidence === 'high'   ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40' :
    confidence === 'medium' ? 'bg-blue-500/20 text-blue-300 border-blue-500/40' :
                              'bg-gray-700 text-gray-400 border-gray-600';

  return (
    <Link to={`/games/${game.id}`}>
      <div
        className={clsx(
          'rounded-xl border p-4 hover:scale-[1.01] transition-transform cursor-pointer',
          confidenceColors[confidence] ?? 'border-gray-700 bg-gray-900'
        )}
      >
        {/* ── Live / Final badge ───────────────────────────── */}
        <div style={{background:"red",color:"white",textAlign:"center",padding:"4px",fontWeight:"bold",fontSize:"12px",borderRadius:"6px",marginBottom:"8px"}}>NEW BUNDLE ACTIVE</div>
        {(isLive || isFinal) && (
          <div className="flex justify-center mb-2">
            <span className={clsx(
              'text-xs font-bold px-2 py-0.5 rounded-full border',
              isLive
                ? 'bg-green-500/20 text-green-400 border-green-500/40 animate-pulse'
                : 'bg-gray-700 text-gray-400 border-gray-600'
            )}>
              {isLive ? '● LIVE' : 'FINAL'}
            </span>
          </div>
        )}

        {/* ── Teams + Score ────────────────────────────────── */}
        <div className="flex items-center justify-between mb-3">
          {/* Away */}
          <div className="text-center flex-1">
            <img
              src={espnLogo(game.away_team)}
              alt={game.away_team}
              className="w-12 h-12 mx-auto mb-1 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <div className="text-xl font-black">{game.away_team}</div>
            <div className="text-[10px] font-bold tracking-widest text-white uppercase bg-blue-600 rounded px-1.5 py-0.5 inline-block mt-0.5">Away</div>
            {awayRank.overall_rank && (
              <div className="text-xs text-cyan-400 font-semibold mt-0.5">{rankBadge(awayRank.overall_rank)} FPI</div>
            )}
          </div>

          {/* Score / separator */}
          <div className="text-center px-2 min-w-[80px]">
            {hasScore ? (
              <div className="flex items-center justify-center gap-2">
                <span className={clsx('text-2xl font-black tabular-nums',
                  isFinal && game.away_score > game.home_score ? 'text-white' : 'text-gray-400')}>
                  {game.away_score}
                </span>
                <span className="text-gray-600 text-lg">–</span>
                <span className={clsx('text-2xl font-black tabular-nums',
                  isFinal && game.home_score > game.away_score ? 'text-white' : 'text-gray-400')}>
                  {game.home_score}
                </span>
              </div>
            ) : (
              <div className="text-gray-500 text-sm font-semibold">@</div>
            )}
          </div>

          {/* Home */}
          <div className="text-center flex-1">
            <img
              src={espnLogo(game.home_team)}
              alt={game.home_team}
              className="w-12 h-12 mx-auto mb-1 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <div className="text-xl font-black">{game.home_team}</div>
            <div className="text-[10px] font-bold tracking-widest text-white uppercase bg-blue-600 rounded px-1.5 py-0.5 inline-block mt-0.5">Home</div>
            {homeRank.overall_rank && (
              <div className="text-xs text-cyan-400 font-semibold mt-0.5">{rankBadge(homeRank.overall_rank)} FPI</div>
            )}
          </div>
        </div>

        {/* ── Injury alert ─────────────────────────────────── */}
        {(showAwayQbAlert || showHomeQbAlert || homeOutCount >= 2 || awayOutCount >= 2) && (
          <div className="flex items-center gap-2 text-xs mb-3 px-2 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
            <div className="flex gap-3 flex-wrap">
              {showAwayQbAlert && (
                <span className="flex items-center gap-1">
                  <span className={clsx('w-2 h-2 rounded-full', injuryDotColor(awayInj.qb_status))} />
                  <span className="text-gray-300">{game.away_team} QB: {awayInj.qb_status}</span>
                </span>
              )}
              {showHomeQbAlert && (
                <span className="flex items-center gap-1">
                  <span className={clsx('w-2 h-2 rounded-full', injuryDotColor(homeInj.qb_status))} />
                  <span className="text-gray-300">{game.home_team} QB: {homeInj.qb_status}</span>
                </span>
              )}
              {!showAwayQbAlert && awayOutCount >= 2 && (
                <span className="text-orange-400">{game.away_team} −{awayOutCount} starters</span>
              )}
              {!showHomeQbAlert && homeOutCount >= 2 && (
                <span className="text-orange-400">{game.home_team} −{homeOutCount} starters</span>
              )}
            </div>
          </div>
        )}

        {/* ── Odds ─────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-2 text-center mb-3">
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1 flex items-center justify-center gap-1">
              Spread
              <span title="Point spread — negative = favorite must win by this margin; positive = underdog can lose by this much and still cover.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <div className="text-xs font-mono space-y-0.5">
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.away_team}</span>
                <span className="font-bold text-white">
                  {odds.home_spread != null ? (odds.home_spread > 0 ? `–${odds.home_spread}` : `+${Math.abs(odds.home_spread)}`) : '–'}
                </span>
              </div>
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.home_team}</span>
                <span className="font-bold text-white">
                  {odds.home_spread != null ? `${odds.home_spread > 0 ? '+' : ''}${odds.home_spread}` : '–'}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-0.5 flex items-center justify-center gap-1">
              Total
              <span title="Over/Under — combined projected points scored by both teams. Bet whether the actual total goes over or under this number.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <div className="text-sm font-mono font-bold">{odds.total ?? '–'}</div>
          </div>

          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1 flex items-center justify-center gap-1">
              ML
              <span title="Moneyline — bet on a team to win outright. Negative = risk that amount to win $100. Positive = a $100 bet wins that amount.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <div className="text-xs font-mono space-y-0.5">
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.away_team}</span>
                <span className="font-bold text-white">{odds.away_ml != null ? `${odds.away_ml > 0 ? '+' : ''}${odds.away_ml}` : '–'}</span>
              </div>
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.home_team}</span>
                <span className="font-bold text-white">{odds.home_ml != null ? `${odds.home_ml > 0 ? '+' : ''}${odds.home_ml}` : '–'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Public money bar ─────────────────────────────── */}
        {odds.home_spread_pct != null && (
          <div className="mb-3">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>{game.away_team} {(100 - odds.home_spread_pct).toFixed(0)}%</span>
              <span className="text-gray-500 flex items-center gap-1">
                Public Bets
                <span title="Percentage of public spread bets on each team. Useful for identifying lopsided public action.">
                  <Info className="w-3 h-3 text-gray-600 cursor-help" />
                </span>
              </span>
              <span>{game.home_team} {odds.home_spread_pct.toFixed(0)}%</span>
            </div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden flex">
              <div className="bg-red-500 h-full" style={{ width: `${100 - odds.home_spread_pct}%` }} />
              <div className="bg-emerald-500 h-full" style={{ width: `${odds.home_spread_pct}%` }} />
            </div>
          </div>
        )}

        {/* ── Weather ──────────────────────────────────────── */}
        {weather.wind_mph != null && (
          <div className="flex gap-3 text-xs text-gray-400 mb-3">
            <span className="flex items-center gap-1"><Wind className="w-3 h-3" /> {weather.wind_mph?.toFixed(0)} mph</span>
            <span className="flex items-center gap-1"><Thermometer className="w-3 h-3" /> {weather.temp_f?.toFixed(0)}°F</span>
            {(weather.precip_mm ?? 0) > 0 && (
              <span className="flex items-center gap-1"><Droplets className="w-3 h-3" /> {weather.precip_mm?.toFixed(1)} mm</span>
            )}
            <span className="ml-auto text-gray-500">{weather.condition_desc}</span>
          </div>
        )}

        {/* ── Edge score ───────────────────────────────────── */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              <span className="text-2xl font-black text-red-400 tabular-nums">{compositeScore.toFixed(1)}</span>
              <div className="flex flex-col leading-none">
                <span className="text-[10px] text-gray-500 uppercase tracking-widest">Edge</span>
                <span className="text-[10px] text-gray-500 uppercase tracking-widest">Score</span>
              </div>
              <span title="Composite score 0–100 combining line movement, sharp money, public fade, weather, power rankings, and injuries.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <span className={clsx('text-xs font-bold px-2 py-0.5 rounded border uppercase tracking-wide', confidenceBadgeColor)}>
              {confidence}
            </span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={clsx('h-full rounded-full transition-all',
                compositeScore >= 60 ? 'bg-green-500' : compositeScore >= 30 ? 'bg-yellow-500' : 'bg-red-500')}
              style={{ width: `${Math.min(100, compositeScore)}%` }}
            />
          </div>
        </div>

        {/* ── Signal Breakdown ─────────────────────────────── */}
        <div className="border-t border-gray-800 pt-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-widest">Signal Breakdown</span>
            <span title="Each signal contributes to the overall Edge Score. Hover any label for an explanation.">
              <Info className="w-3 h-3 text-gray-600 cursor-help" />
            </span>
          </div>
          <div className="grid grid-cols-3 gap-x-4 gap-y-2">
            {Object.entries(SIGNAL_META).map(([key, meta]) => {
              const val = typeof edge[key] === 'number' ? edge[key] : 0;
              return (
                <div key={key}>
                  <div className="flex items-center gap-1">
                    <span
                      className={clsx('text-[10px] font-bold uppercase tracking-widest cursor-help', meta.color)}
                      title={meta.tooltip}
                    >
                      {meta.short}
                    </span>
                    <span title={meta.tooltip} className="cursor-help">
                      <Info className="w-2.5 h-2.5 text-gray-700" />
                    </span>
                    <span className={clsx('text-xs font-bold ml-auto tabular-nums', meta.color)}>
                      {val % 1 === 0 ? val.toFixed(0) : val.toFixed(1)}
                    </span>
                  </div>
                  <SignalBar value={val} />
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Notes ────────────────────────────────────────── */}
        {edge.notes && edge.notes.length > 0 && (
          <ul className="mt-3 space-y-0.5">
            {edge.notes.map((n: string, i: number) => (
              <li key={i} className="text-xs text-gray-400 flex gap-1.5">
                <span className="text-gray-600 flex-shrink-0">•</span>
                <span>{n}</span>
              </li>
            ))}
          </ul>
        )}

        {/* ── Recommendation ───────────────────────────────── */}
        {rec && rec !== 'none' && (
          <div className="mt-3 flex justify-end">
            <span className="text-xs font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full px-2 py-0.5">
              {recommendationLabels[rec] ?? rec}
            </span>
          </div>
        )}

        {/* ── Game time ────────────────────────────────────── */}
        <div className="mt-2 text-xs text-gray-600 text-right">
          {game.game_time
            ? new Date(game.game_time).toLocaleString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric',
                hour: 'numeric', minute: '2-digit',
                timeZone: 'America/New_York',
                timeZoneName: 'short',
              })
            : ''}
        </div>
      </div>
    </Link>
  );
}
