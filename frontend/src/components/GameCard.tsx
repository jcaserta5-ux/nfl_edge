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
  home_spread: 'ðŸ  Home Spread',
  away_spread: 'âœˆï¸ Away Spread',
  over:        'ðŸ“ˆ Over',
  under:       'ðŸ“‰ Under',
  investigate: 'ðŸ” Investigate',
  none:        '',
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

  const isLive   = game.status === 'live';
  const isFinal  = game.status === 'final';
  const hasScore = game.home_score != null && game.away_score != null;

  return (
    <Link to={`/games/${game.id}`}>
      <div
        className={clsx(
          'rounded-xl border p-4 hover:scale-[1.01] transition-transform cursor-pointer',
          confidenceColors[confidence] ?? 'border-gray-700 bg-gray-900'
        )}
      >
        {/* Live / Final badge */}
        {(isLive || isFinal) && (
          <div className="flex justify-center mb-2">
            <span className={clsx(
              'text-xs font-bold px-2 py-0.5 rounded-full',
              isLive
                ? 'bg-green-500/20 text-green-400 border border-green-500/40 animate-pulse'
                : 'bg-gray-700 text-gray-400 border border-gray-600'
            )}>
              {isLive ? 'â— LIVE' : 'FINAL'}
            </span>
          </div>
        )}

        {/* Teams row */}
        <div className="flex items-center justify-between mb-3">
          <div className="text-center flex-1">
            <img
              src={espnLogo(game.away_team)}
              alt={game.away_team}
              className="w-12 h-12 mx-auto mb-1 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <div className="text-xl font-black">{game.away_team}</div>
            <div className="text-[10px] font-bold tracking-widest text-gray-500 uppercase bg-gray-800 rounded px-1.5 py-0.5 inline-block mt-0.5">Away</div>
            {awayRank.overall_rank && (
              <div className="text-xs text-cyan-400 font-semibold mt-0.5">
                {rankBadge(awayRank.overall_rank)} FPI
              </div>
            )}
          </div>

          <div className="text-center px-2 min-w-[80px]">
            {hasScore ? (
              <div className="flex items-center justify-center gap-2">
                <span className={clsx(
                  'text-2xl font-black tabular-nums',
                  isFinal && game.away_score > game.home_score ? 'text-white' : 'text-gray-400'
                )}>
                  {game.away_score}
                </span>
                <span className="text-gray-600 text-lg">â€“</span>
                <span className={clsx(
                  'text-2xl font-black tabular-nums',
                  isFinal && game.home_score > game.away_score ? 'text-white' : 'text-gray-400'
                )}>
                  {game.home_score}
                </span>
              </div>
            ) : (
              <div className="text-gray-500 text-sm font-semibold">@</div>
            )}
          </div>

          <div className="text-center flex-1">
            <img
              src={espnLogo(game.home_team)}
              alt={game.home_team}
              className="w-12 h-12 mx-auto mb-1 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <div className="text-xl font-black">{game.home_team}</div>
            <div className="text-[10px] font-bold tracking-widest text-gray-500 uppercase bg-gray-800 rounded px-1.5 py-0.5 inline-block mt-0.5">Home</div>
            {homeRank.overall_rank && (
              <div className="text-xs text-cyan-400 font-semibold mt-0.5">
                {rankBadge(homeRank.overall_rank)} FPI
              </div>
            )}
          </div>
        </div>

        {/* Injury alert row */}
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
                <span className="text-orange-400">{game.away_team} âˆ’{awayOutCount} starters</span>
              )}
              {!showHomeQbAlert && homeOutCount >= 2 && (
                <span className="text-orange-400">{game.home_team} âˆ’{homeOutCount} starters</span>
              )}
            </div>
          </div>
        )}

        {/* Odds row */}
        <div className="grid grid-cols-3 gap-2 text-center mb-3">
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1 flex items-center justify-center gap-1">
              Spread
              <span title="Point spread â€” negative = favorite must win by this margin; positive = underdog can lose by this much and still cover.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <div className="text-xs font-mono space-y-0.5">
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.away_team}</span>
                <span className="font-bold text-white">{odds.home_spread != null ? (odds.home_spread > 0 ? `â€“${odds.home_spread}` : `+${-odds.home_spread}`) : 'â€”'}</span>
              </div>
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.home_team}</span>
                <span className="font-bold text-white">{odds.home_spread != null ? `${odds.home_spread > 0 ? '+' : ''}${odds.home_spread}` : 'â€”'}</span>
              </div>
            </div>
          </div>
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-0.5 flex items-center justify-center gap-1">Total<span title="Over/Under â€” combined projected points. Bet whether actual total goes over or under this number."><Info className="w-3 h-3 text-gray-600 cursor-help" /></span></div>
            <div className="text-sm font-mono font-bold">{odds.total ?? 'â€”'}</div>
          </div>
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-xs text-gray-500 mb-1 flex items-center justify-center gap-1">
              ML
              <span title="Moneyline â€” bet on a team to win outright. Negative means you risk that amount to win $100. Positive means a $100 bet wins that amount.">
                <Info className="w-3 h-3 text-gray-600 cursor-help" />
              </span>
            </div>
            <div className="text-xs font-mono space-y-0.5">
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.away_team}</span>
                <span className="font-bold text-white">{odds.away_ml != null ? `${odds.away_ml > 0 ? '+' : ''}${odds.away_ml}` : 'â€”'}</span>
              </div>
              <div className="flex justify-between px-1">
                <span className="text-gray-500">{game.home_team}</span>
                <span className="font-bold text-white">{odds.home_ml != null ? `${odds.home_ml > 0 ? '+' : ''}${odds.home_ml}` : 'â€”'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Public money bar */}
        {odds.home_spread_pct != null && (
          <div className="mb-3">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>{game.away_team} {(100 - odds.home_spread_pct).toFixed(0)}%</span>
              <span className="text-gray-500">Bets</span>
              <span>{game.home_team} {odds.home_spread_pct.toFixed(0)}%</span>
            </div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden flex">
              <div className="bg-red-500 h-full" style={{ width: `${100 - odds.home_spread_pct}%` }} />
              <div className="bg-emerald-500 h-full" style={{ width: `${odds.home_spread_pct}%` }} />
            </div>
          </div>
        )}

        {/* Weather strip */}
        {weather.wind_mph != null && (
          <div className="flex gap-3 text-xs text-gray-400 mb-3">
            <span className="flex items-center gap-1">
              <Wind className="w-3 h-3" /> {weather.wind_mph?.toFixed(0)} mph
            </span>
            <span className="flex items-center gap-1">
              <Thermometer className="w-3 h-3" /> {weather.temp_f?.toFixed(0)}Â°F
            </span>
            {(weather.precip_mm ?? 0) > 0 && (
              <span className="flex items-center gap-1">
                <Droplets className="w-3 h-3" /> {weather.precip_mm?.toFixed(1)} mm
              </span>
            )}
            <span className="ml-auto text-gray-500">{weather.condition_desc}</span>
          </div>
        )}

        {/* Edge score + recommendation */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-bold text-yellow-300">
              {edge.composite_score?.toFixed(0) ?? 0}
            </span>
            <span className="text-xs text-gray-500 flex items-center gap-1">edge score<span title="Composite score 0â€“100 combining line movement, sharp money, public fade, weather, power rankings, and injuries."><Info className="w-3 h-3 text-gray-600 cursor-help" /></span></span>
          </div>
          {rec && rec !== 'none' && (
            <span className="text-xs font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full px-2 py-0.5">
              {recommendationLabels[rec] ?? rec}
            </span>
          )}
        </div>

        {/* Game time â€” forced ET */}
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
